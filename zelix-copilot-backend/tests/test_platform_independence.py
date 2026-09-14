"""Platform Independence & Behavioral Acceptance Tests (Tests 1 to 8).

Validates that Alamia AI Copilot operates with complete framework neutrality,
pluggable adapters, bulletproof authorization, idempotency, and confirmation policies.
"""

import pytest
from typing import Any, Dict, List, Optional
from adapters.ai.providers.mock_provider import MockAIModelProvider
from adapters.application.base.adapter import ApplicationAdapter
from adapters.application.reference.in_memory_adapter import InMemoryApplicationAdapter
from core.actions.executor import ActionExecutionError, ActionExecutor
from core.actions.proposal import ActionProposal, ActionStatus
from core.actions.statemachine import ActionStateMachine
from core.ai.models import ChatMessage, ChatRole
from core.ai.router import AIModelRouter
from core.policies.confirmation import ConfirmationPolicy
from core.policies.engine import PolicyEngine
from core.policies.permission import PermissionPolicy
from core.policies.risk import RiskLevel, RiskPolicy
from core.roles.manifest import RoleManifest
from core.roles.registry import RoleRegistry
from core.runtime.engine import CopilotEngine
from core.sessions.context import EmployeeContext
from core.skills.registry import SkillRegistry
from core.tools.reference_tools import (
    GetCustomerInvoicesTool,
    GetCustomerTasksTool,
    GetCustomerTool,
    GetWorkItemsTool,
)
from core.tools.registry import ToolRegistry
from skills.examples.customer_360 import Customer360Skill
from skills.examples.payment_followup import PaymentFollowupSkill


class MockLegacyApplicationAdapter(ApplicationAdapter):
    """A second mock adapter with completely different internal key naming and storage."""

    def __init__(self) -> None:
        # Uses legacy format: tbl_clients and tbl_bills with camelCase fields
        self.tbl_clients: Dict[str, Dict[str, Any]] = {
            "CUST-99": {
                "clientId": "CUST-99",
                "clientFullName": "Legacy Global Corp",
                "contactEmail": "legacy@global.org",
            }
        }
        self.tbl_bills: List[Dict[str, Any]] = [
            {"billId": "B-1", "clientIdRef": "CUST-99", "totalDue": 5000.0, "billStatus": "OVERDUE"},
            {"billId": "B-2", "clientIdRef": "CUST-99", "totalDue": 1200.0, "billStatus": "PAID"},
        ]
        self.executed_mutations: List[Dict[str, Any]] = []

    def identity(self, user_id: str) -> Optional[Dict[str, Any]]:
        return {"id": user_id, "name": "Legacy User"}

    def permissions(self, user_id: str) -> List[str]:
        return ["customers.read", "invoices.read", "tasks.read", "tasks.create"]

    def search(self, entity_type: str, query: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return []

    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        if entity_type == "customer":
            raw = self.tbl_clients.get(entity_id)
            if raw:
                return {"id": raw["clientId"], "name": raw["clientFullName"], "email": raw["contactEmail"]}
        return None

    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return data

    def update(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return data

    def delete(self, entity_type: str, entity_id: str) -> bool:
        return True

    def execute(self, action_type: str, target: Dict[str, Any], proposed_changes: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Any:
        record = {"action": action_type, "target": target, "changes": proposed_changes}
        self.executed_mutations.append(record)
        return {"status": "SUCCESS", "legacy_ref": "LEGACY-MUT-123"}

    def relationships(self, entity_type: str, entity_id: str, relation_name: str) -> List[Dict[str, Any]]:
        if relation_name == "invoices" and entity_type == "customer":
            matched = [b for b in self.tbl_bills if b["clientIdRef"] == entity_id]
            return [
                {"id": b["billId"], "amount": b["totalDue"], "status": b["billStatus"].lower(), "customer_id": b["clientIdRef"]}
                for b in matched
            ]
        return []

    def audit(self, entry: Dict[str, Any]) -> None:
        pass


@pytest.fixture
def base_engine_setup():
    """Build a fully wired runtime engine with default reference adapter and test data."""
    adapter = InMemoryApplicationAdapter()
    adapter.create("customer", {"id": "cust_1", "name": "Acme Corp", "email": "contact@acme.com", "tier": "gold"})
    adapter.create("invoice", {"id": "inv_1", "customer_id": "cust_1", "amount": 1500.0, "status": "overdue"})
    adapter.create("invoice", {"id": "inv_2", "customer_id": "cust_1", "amount": 300.0, "status": "paid"})
    adapter.create("task", {"id": "task_1", "title": "Review Q3 Report", "priority": "high", "status": "pending"})

    skills = SkillRegistry()
    skills.register(Customer360Skill())
    skills.register(PaymentFollowupSkill())

    tools = ToolRegistry()
    tools.register(GetCustomerTool(adapter))
    tools.register(GetCustomerInvoicesTool(adapter))
    tools.register(GetCustomerTasksTool(adapter))
    tools.register(GetWorkItemsTool(adapter))

    roles = RoleRegistry()
    roles.register(RoleManifest(
        id="finance_assistant",
        name="Finance Assistant",
        skills=["customer_360", "payment_followup"],
        permissions=["customers.read", "invoices.read", "tasks.read", "tasks.create", "financial.write"],
    ))
    roles.register(RoleManifest(
        id="read_only_viewer",
        name="Read Only Viewer",
        skills=["customer_360"],
        permissions=["customers.read", "invoices.read"],
    ))

    ai_provider = MockAIModelProvider(name="mock-default", canned_response="Summary generated successfully.")
    router = AIModelRouter(default_provider=ai_provider)

    engine = CopilotEngine(
        skill_registry=skills,
        tool_registry=tools,
        role_registry=roles,
        ai_router=router,
        application_adapter=adapter,
    )

    return engine, adapter, tools, skills, roles


# =========================================================================
# TEST 1: Generic Skill operates against reference adapter
# =========================================================================
def test_skill_operates_against_reference_adapter(base_engine_setup):
    engine, adapter, _, _, _ = base_engine_setup
    context = EmployeeContext(
        user_id="usr_finance_1",
        role="finance_assistant",
        permissions=["customers.read", "invoices.read", "tasks.read"],
    )

    result = engine.execute_skill("customer_360", context, customer_id="cust_1")

    assert result.success is True
    assert result.output["customer"]["name"] == "Acme Corp"
    assert result.output["total_invoices"] == 2
    assert len(result.output["invoices"]) == 2


# =========================================================================
# TEST 2: Same Skill operates against second mock adapter with different data structure
# =========================================================================
def test_same_skill_operates_against_second_mock_adapter():
    legacy_adapter = MockLegacyApplicationAdapter()

    skills = SkillRegistry()
    skills.register(Customer360Skill())

    tools = ToolRegistry()
    tools.register(GetCustomerTool(legacy_adapter))
    tools.register(GetCustomerInvoicesTool(legacy_adapter))
    tools.register(GetCustomerTasksTool(legacy_adapter))

    roles = RoleRegistry()
    roles.register(RoleManifest(id="sales_assistant", name="Sales Assistant", skills=["customer_360"]))

    engine = CopilotEngine(
        skill_registry=skills,
        tool_registry=tools,
        role_registry=roles,
        application_adapter=legacy_adapter,
    )

    context = EmployeeContext(user_id="usr_legacy", role="sales_assistant", permissions=["customers.read"])
    result = engine.execute_skill("customer_360", context, customer_id="CUST-99")

    assert result.success is True
    assert result.output["customer"]["name"] == "Legacy Global Corp"
    assert result.output["total_invoices"] == 2
    assert result.output["invoices"][0]["amount"] == 5000.0


# =========================================================================
# TEST 3: Replacing the AI provider does not change the Skill
# =========================================================================
def test_replacing_ai_provider_does_not_change_skill(base_engine_setup):
    engine, _, _, _, _ = base_engine_setup

    provider_a = MockAIModelProvider(name="provider-alpha", canned_response="Alpha output")
    provider_b = MockAIModelProvider(name="provider-beta", canned_response="Beta output")

    # Run with Provider A
    engine.ai_router = AIModelRouter(default_provider=provider_a)
    context = EmployeeContext(user_id="usr_1", role="finance_assistant", permissions=["customers.read", "invoices.read"])
    result_a = engine.execute_skill("customer_360", context, customer_id="cust_1")

    # Run with Provider B
    engine.ai_router = AIModelRouter(default_provider=provider_b)
    result_b = engine.execute_skill("customer_360", context, customer_id="cust_1")

    assert result_a.success is True
    assert result_b.success is True
    assert result_a.output == result_b.output


# =========================================================================
# TEST 4: The LLM cannot bypass authorization
# =========================================================================
def test_llm_cannot_bypass_authorization(base_engine_setup):
    engine, _, _, _, _ = base_engine_setup
    
    # User only has read permission
    unauthorized_context = EmployeeContext(
        user_id="usr_attacker",
        role="read_only_viewer",
        permissions=["customers.read"],
    )

    # Malicious proposal claiming no confirmation is needed and permission is already granted
    fake_proposal = ActionProposal(
        action_id="act_exploit_1",
        action_type="mark_invoice_paid",
        idempotency_key="exploit_key_1",
        target={"type": "invoice", "id": "inv_1"},
        reason="Attacker claiming direct bypass",
        risk_level="LOW",  # LLM lies that it is low risk
        requires_confirmation=False,  # LLM lies that confirmation is disabled
        required_permission="financial.write",
        created_by="usr_attacker",
    )

    result_proposal = engine.execute_action(fake_proposal, unauthorized_context)

    assert result_proposal.status == ActionStatus.REJECTED
    assert "Unauthorized" in result_proposal.error


# =========================================================================
# TEST 5: Repeated ActionProposal with same idempotency key does not duplicate mutation
# =========================================================================
def test_idempotency_key_enforcement(base_engine_setup):
    engine, adapter, _, _, _ = base_engine_setup
    context = EmployeeContext(
        user_id="usr_fin",
        role="finance_assistant",
        permissions=["financial.write", "tasks.create"],
    )

    proposal = ActionProposal(
        action_id="act_followup_101",
        action_type="create_followup",
        idempotency_key="idemp_unique_key_abc",
        target={"type": "customer", "id": "cust_1"},
        reason="Overdue payment notice",
        proposed_changes={"title": "Follow up payment", "description": "$1500 overdue"},
        requires_confirmation=False,
        required_permission="tasks.create",
        created_by=context.user_id,
    )

    # Initial execution
    exec1 = engine.execute_action(proposal, context)
    assert exec1.status == ActionStatus.COMPLETED
    assert len(adapter.executed_actions) == 1

    # Second execution with identical idempotency key
    duplicate_proposal = ActionProposal(
        action_id="act_followup_102",
        action_type="create_followup",
        idempotency_key="idemp_unique_key_abc",  # Duplicate key
        target={"type": "customer", "id": "cust_1"},
        reason="Overdue payment notice again",
        proposed_changes={"title": "Follow up payment", "description": "$1500 overdue"},
        requires_confirmation=False,
        required_permission="tasks.create",
        created_by=context.user_id,
    )

    exec2 = engine.execute_action(duplicate_proposal, context)
    assert exec2.status == ActionStatus.COMPLETED
    # Mutation must NOT be executed a second time
    assert len(adapter.executed_actions) == 1


# =========================================================================
# TEST 6: Read-only role cannot execute financial action
# =========================================================================
def test_readonly_role_cannot_execute_financial_action(base_engine_setup):
    engine, _, _, _, _ = base_engine_setup
    readonly_context = EmployeeContext(
        user_id="usr_readonly",
        role="read_only_viewer",
        permissions=["customers.read", "invoices.read"],
    )

    financial_proposal = ActionProposal(
        action_id="act_fin_999",
        action_type="mark_invoice_paid",
        idempotency_key="fin_idemp_999",
        target={"type": "invoice", "id": "inv_1"},
        reason="Attempting to mark paid",
        required_permission="financial.write",
        created_by="usr_readonly",
    )

    result = engine.execute_action(financial_proposal, readonly_context)
    assert result.status == ActionStatus.REJECTED
    assert "Unauthorized" in result.error


# =========================================================================
# TEST 7: Confirmation-required action cannot execute before confirmation
# =========================================================================
def test_confirmation_required_action_cannot_execute_before_confirmation(base_engine_setup):
    engine, _, _, _, _ = base_engine_setup
    context = EmployeeContext(
        user_id="usr_fin",
        role="finance_assistant",
        permissions=["financial.write", "tasks.create"],
    )

    # High-risk action evaluated by PolicyEngine
    high_risk_proposal = ActionProposal(
        action_id="act_del_inv_1",
        action_type="delete",
        idempotency_key="del_inv_1_key",
        target={"type": "invoice", "id": "inv_1"},
        reason="Delete corrupted invoice",
        required_permission="financial.write",
        created_by=context.user_id,
    )

    # Evaluated by backend policies
    evaluated = engine.policies.evaluate_proposal(context, high_risk_proposal)
    assert evaluated.requires_confirmation is True
    assert evaluated.status == ActionStatus.AWAITING_CONFIRMATION

    # Attempting to execute while still AWAITING_CONFIRMATION must fail
    with pytest.raises(ActionExecutionError) as excinfo:
        engine.actions.execute(evaluated, engine.adapter)
    assert "requires confirmation before execution" in str(excinfo.value)

    # Once explicitly confirmed by user, it succeeds
    ActionStateMachine.transition(evaluated, ActionStatus.CONFIRMED)
    executed = engine.actions.execute(evaluated, engine.adapter)
    assert executed.status == ActionStatus.COMPLETED


# =========================================================================
# TEST 8: Application adapter can be replaced without modifying core runtime
# =========================================================================
def test_application_adapter_replaced_without_modifying_core(base_engine_setup):
    engine, adapter1, _, _, _ = base_engine_setup
    context = EmployeeContext(
        user_id="usr_1",
        role="finance_assistant",
        permissions=["customers.read", "invoices.read", "tasks.read"],
    )

    # 1. Run against adapter 1
    res1 = engine.execute_skill("customer_360", context, customer_id="cust_1")
    assert res1.success is True
    assert res1.output["customer"]["name"] == "Acme Corp"

    # 2. Swap adapter to MockLegacyApplicationAdapter without modifying any core class
    adapter2 = MockLegacyApplicationAdapter()
    engine.set_application_adapter(adapter2)
    engine.tools.register(GetCustomerTool(adapter2))
    engine.tools.register(GetCustomerInvoicesTool(adapter2))
    engine.tools.register(GetCustomerTasksTool(adapter2))

    # 3. Run against adapter 2 with identical engine and skills
    res2 = engine.execute_skill("customer_360", context, customer_id="CUST-99")
    assert res2.success is True
    assert res2.output["customer"]["name"] == "Legacy Global Corp"
