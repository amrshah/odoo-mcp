"""Reference Application Demonstration Runner.

Demonstrates end-to-end Alamia AI Copilot workflows:
- Customer 360 lookup
- Payment follow-up analysis and ActionProposal generation
- Human confirmation and authoritative execution
- Zero dependency on specific frameworks or cloud services
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from adapters.ai.providers.mock_provider import MockAIModelProvider
from adapters.application.reference.in_memory_adapter import InMemoryApplicationAdapter
from core.actions.proposal import ActionProposal, ActionStatus
from core.ai.router import AIModelRouter
from core.policies.engine import PolicyEngine
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
from skills.examples.daily_briefing import DailyBriefingSkill
from skills.examples.payment_followup import PaymentFollowupSkill


def build_copilot_system() -> tuple[CopilotEngine, InMemoryApplicationAdapter]:
    """Wire together the reference Copilot runtime with sample data."""
    adapter = InMemoryApplicationAdapter()

    # Populate generic business entities
    adapter.create("customer", {
        "id": "cust_101",
        "name": "Acme Global Industries",
        "email": "finance@acmeglobal.com",
        "tier": "enterprise",
        "balance": 8400.0,
    })
    adapter.create("invoice", {
        "id": "inv_801",
        "customer_id": "cust_101",
        "amount": 5400.0,
        "status": "overdue",
    })
    adapter.create("invoice", {
        "id": "inv_802",
        "customer_id": "cust_101",
        "amount": 3000.0,
        "status": "paid",
    })
    adapter.create("task", {
        "id": "task_501",
        "title": "Prepare Q3 enterprise summary",
        "priority": "high",
        "status": "pending",
    })

    skills = SkillRegistry()
    skills.register(Customer360Skill())
    skills.register(PaymentFollowupSkill())
    skills.register(DailyBriefingSkill())

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
        id="executive_assistant",
        name="Executive Assistant",
        skills=["daily_briefing"],
        permissions=["tasks.read"],
    ))

    ai_router = AIModelRouter(default_provider=MockAIModelProvider())

    engine = CopilotEngine(
        skill_registry=skills,
        tool_registry=tools,
        role_registry=roles,
        ai_router=ai_router,
        application_adapter=adapter,
    )

    return engine, adapter


def main() -> None:
    print("=" * 70)
    print("Alamia AI Copilot Boilerplate — Reference Application Runner")
    print("=" * 70)

    engine, adapter = build_copilot_system()

    # 1. Customer 360 View
    print("\n--- 1. Executing Skill: Customer 360 View ---")
    context = EmployeeContext(
        user_id="usr_finance_mgr",
        role="finance_assistant",
        permissions=["customers.read", "invoices.read", "tasks.read", "tasks.create"],
    )
    res_c360 = engine.execute_skill("customer_360", context, customer_id="cust_101")
    print(f"Status: {'SUCCESS' if res_c360.success else 'FAILED'}")
    print(f"Customer Name: {res_c360.output['customer']['name']}")
    print(f"Total Invoices: {res_c360.output['total_invoices']}")

    # 2. Payment Followup Skill (Generates ActionProposal)
    print("\n--- 2. Executing Skill: Payment Follow-up (Generates ActionProposal) ---")
    res_followup = engine.execute_skill("payment_followup", context, customer_id="cust_101")
    print(f"Status: {'SUCCESS' if res_followup.success else 'FAILED'}")
    print(f"Overdue Invoices: {res_followup.output['overdue_count']}")
    print(f"Total Overdue: ${res_followup.output['total_overdue']:.2f}")

    if res_followup.proposed_actions:
        raw_prop = res_followup.proposed_actions[0]
        proposal = ActionProposal.model_validate(raw_prop)
        print(f"\nProposed Action: {proposal.action_type}")
        print(f"Idempotency Key: {proposal.idempotency_key}")
        print(f"Requires Confirmation: {proposal.requires_confirmation}")
        print(f"Status: {proposal.status.value}")

        # 3. Executing Action
        print("\n--- 3. Executing Confirmed ActionProposal ---")
        exec_result = engine.execute_action(proposal, context)
        print(f"Action Status: {exec_result.status.value}")
        print(f"Result: {exec_result.result}")
        print(f"Total tasks in adapter: {len(adapter.tasks)}")

    print("\n" + "=" * 70)
    print("Reference Application completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
