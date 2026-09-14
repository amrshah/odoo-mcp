"""Automated tests for Raw Wire-Level Protocol Boundary.

Verifies:
1. Low-level HTTP requests and SSE stream parsing without UI libraries.
2. Handling of RUN_STARTED, STATE_UPDATE, TEXT_DELTA, INTERRUPT, and RUN_FINISHED events.
3. HITL interrupt approval and state mutation.
"""

import json
import pytest
from core.runtime.engine import CopilotEngine
from core.skills.registry import SkillRegistry
from core.tools.registry import ToolRegistry
from core.tools.reference_tools import GetCustomerTool, GetCustomerInvoicesTool
from core.sessions.context import EmployeeContext
from core.actions.proposal import ActionStatus
from adapters.application.reference.in_memory_adapter import InMemoryApplicationAdapter
from adapters.ag_ui.server import AGUIHandler
from adapters.ag_ui.serializer import AGUISerializer
from adapters.ag_ui.events import AGUIEventType
from skills.examples.customer_360 import Customer360Skill
from skills.examples.payment_followup import PaymentFollowupSkill


@pytest.fixture
def wire_protocol_engine():
    adapter = InMemoryApplicationAdapter()
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
    # Require confirmation for payment follow-up
    engine.policies.confirmation_policy.always_require_confirmation_actions.add("create_followup")
    
    handler = AGUIHandler(engine=engine)
    return handler, engine, adapter


def test_wire_sse_event_stream_parsing(wire_protocol_engine):
    """Verify that raw SSE chunks are formatted correctly and can be parsed line-by-line."""
    handler, _, _ = wire_protocol_engine
    context = EmployeeContext(
        user_id="user_fin",
        role="finance_assistant",
        permissions=["customers.read", "invoices.read"],
    )

    chunks = list(handler.handle_agent_turn(
        skill_id="customer_360",
        context=context,
        inputs={"customer_id": "cust_101"},
        run_id="run_wire_001",
    ))

    assert len(chunks) >= 4
    
    parsed_events = []
    for chunk in chunks:
        # Verify strict SSE wire format: 'event: <type>\ndata: <json>\n\n'
        assert "\ndata: " in chunk
        lines = chunk.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        json_data = data_line[len("data: "):]
        event = AGUISerializer.decode_sse(json_data)
        parsed_events.append(event)

    types = [e.event_type for e in parsed_events]
    assert types[0] == AGUIEventType.RUN_STARTED
    assert types[1] == AGUIEventType.STATE_UPDATE
    assert types[2] == AGUIEventType.TEXT_DELTA
    assert types[-1] == AGUIEventType.RUN_FINISHED


def test_wire_hitl_interrupt_and_mutation_lifecycle(wire_protocol_engine):
    """Verify the entire wire-level lifecycle of an interrupt from emission to approval and backend mutation."""
    handler, engine, adapter = wire_protocol_engine
    context = EmployeeContext(
        user_id="user_fin",
        role="finance_assistant",
        permissions=["customers.read", "invoices.read", "tasks.create"],
    )

    chunks = list(handler.handle_agent_turn(
        skill_id="payment_followup",
        context=context,
        inputs={"customer_id": "cust_101"},
        run_id="run_wire_002",
    ))

    interrupt_event = None
    for chunk in chunks:
        lines = chunk.strip().split("\n")
        data_line = next((line for line in lines if line.startswith("data: ")), None)
        if data_line:
            event = AGUISerializer.decode_sse(data_line[len("data: "):])
            if event.event_type == AGUIEventType.INTERRUPT:
                interrupt_event = event

    assert interrupt_event is not None
    int_data = interrupt_event.data
    interrupt_id = int_data["interrupt_id"]
    assert interrupt_id.startswith("int_")
    assert "create_followup" in int_data["prompt"]

    # Initial tasks count in adapter
    initial_tasks = len(adapter.tasks)

    # Resolve interrupt via handler
    executed_action = handler.resolve_interrupt(interrupt_id, "Approve")
    assert executed_action is not None
    assert executed_action.status == ActionStatus.COMPLETED
    assert executed_action.result["status"] == "success"

    # Verify adapter state mutated
    assert len(adapter.tasks) == initial_tasks + 1
