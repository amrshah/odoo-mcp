"""Tests for AG-UI Protocol Server and Stream Handler."""

import json
import pytest
from adapters.ag_ui.events import AGUIEventType
from adapters.ag_ui.serializer import AGUISerializer
from adapters.ag_ui.server import AGUIHandler
from adapters.application.reference.in_memory_adapter import InMemoryApplicationAdapter
from core.actions.proposal import ActionStatus
from core.runtime.engine import CopilotEngine
from core.sessions.context import EmployeeContext
from core.skills.registry import SkillRegistry
from core.tools.reference_tools import GetCustomerInvoicesTool, GetCustomerTool
from core.tools.registry import ToolRegistry
from skills.examples.customer_360 import Customer360Skill
from skills.examples.payment_followup import PaymentFollowupSkill


@pytest.fixture
def ag_ui_setup():
    adapter = InMemoryApplicationAdapter()
    adapter.create("customer", {"id": "cust_1", "name": "Acme Corp", "email": "contact@acme.com"})
    adapter.create("invoice", {"id": "inv_1", "customer_id": "cust_1", "amount": 2500.0, "status": "overdue"})

    skills = SkillRegistry()
    skills.register(Customer360Skill())
    skills.register(PaymentFollowupSkill())

    tools = ToolRegistry()
    tools.register(GetCustomerTool(adapter))
    tools.register(GetCustomerInvoicesTool(adapter))

    engine = CopilotEngine(
        skill_registry=skills,
        tool_registry=tools,
        application_adapter=adapter,
    )

    handler = AGUIHandler(engine=engine)
    return handler, engine, adapter


def test_ag_ui_event_stream_customer_360(ag_ui_setup):
    handler, _, _ = ag_ui_setup
    context = EmployeeContext(user_id="usr_1", role="sales_assistant", permissions=["customers.read", "invoices.read"])

    events_stream = list(handler.handle_agent_turn(
        skill_id="customer_360",
        context=context,
        inputs={"customer_id": "cust_1"},
        run_id="run_101",
    ))

    assert len(events_stream) >= 4  # RUN_STARTED, STATE_UPDATE, TEXT_DELTA, RUN_FINISHED

    # Parse and verify event types
    event_types = []
    for chunk in events_stream:
        lines = chunk.strip().split("\n")
        data_line = [l for l in lines if l.startswith("data: ")][0]
        event = AGUISerializer.decode_sse(data_line.replace("data: ", ""))
        event_types.append(event.event_type)

    assert AGUIEventType.RUN_STARTED in event_types
    assert AGUIEventType.STATE_UPDATE in event_types
    assert AGUIEventType.TEXT_DELTA in event_types
    assert AGUIEventType.RUN_FINISHED in event_types


def test_ag_ui_hitl_interrupt_and_resolution(ag_ui_setup):
    handler, engine, adapter = ag_ui_setup
    context = EmployeeContext(
        user_id="usr_1",
        role="finance_assistant",
        permissions=["customers.read", "invoices.read", "tasks.create"],
    )

    # PaymentFollowupSkill proposes an action; if we force confirmation on it:
    engine.policies.confirmation_policy.always_require_confirmation_actions.add("create_followup")

    events_stream = list(handler.handle_agent_turn(
        skill_id="payment_followup",
        context=context,
        inputs={"customer_id": "cust_1"},
        run_id="run_102",
    ))

    # Verify INTERRUPT event was emitted
    interrupt_events = []
    for chunk in events_stream:
        lines = chunk.strip().split("\n")
        data_line = [l for l in lines if l.startswith("data: ")][0]
        event = AGUISerializer.decode_sse(data_line.replace("data: ", ""))
        if event.event_type == AGUIEventType.INTERRUPT:
            interrupt_events.append(event)

    assert len(interrupt_events) == 1
    int_data = interrupt_events[0].data
    interrupt_id = int_data["interrupt_id"]
    assert "Confirm action 'create_followup'" in int_data["prompt"]

    # Test resolving interrupt with approval
    resolved_action = handler.resolve_interrupt(interrupt_id, "Approve")
    assert resolved_action is not None
    assert resolved_action.status == ActionStatus.COMPLETED
    assert len(adapter.tasks) == 1
