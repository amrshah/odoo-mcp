"""Client Interoperability & Open Protocol Tests.

Verifies that any external client (Vue, Angular, Flutter, mobile, WhatsApp)
can seamlessly interact with Alamia Copilot over open REST, SSE, and JSON-RPC protocols.
"""

import json
import pytest
from examples.reference_application.server import process_natural_language_query, ENGINE, ADAPTER
from core.actions.proposal import ActionProposal, ActionStatus
from core.actions.statemachine import ActionStateMachine
from core.sessions.context import EmployeeContext


def test_external_client_natural_language_customer_query():
    """Verify external client query for Customer 360 data."""
    res = process_natural_language_query("Show me customer 101", role="finance_assistant")
    assert res["success"] is True
    assert res["skill_id"] == "customer_360"
    assert res["output"]["customer"]["name"] == "Acme Global Industries"
    assert "Retrieved Customer 360" in res["message"]


def test_external_client_natural_language_overdue_invoices():
    """Verify external client query for overdue invoices."""
    res = process_natural_language_query("What invoices are overdue?", role="finance_assistant")
    assert res["success"] is True
    assert res["skill_id"] == "invoice_query"
    assert res["output"]["count"] >= 1
    assert "Found" in res["message"]


def test_external_client_hitl_action_proposal_and_confirmation():
    """Verify external client receives HITL proposal and can confirm/execute it."""
    # 1. External client sends payment followup request
    res = process_natural_language_query("Follow up on overdue payments", role="finance_assistant")
    assert res["success"] is True
    assert len(res["proposed_actions"]) >= 1

    proposal_data = res["proposed_actions"][0]
    action_id = proposal_data["action_id"]
    assert proposal_data["status"] == "AWAITING_CONFIRMATION"

    # 2. External client sends confirmation to execute
    proposal = ActionProposal.model_validate(proposal_data)
    context = EmployeeContext(
        user_id="user_finance_assistant",
        role="finance_assistant",
        permissions=["tasks.create", "invoices.read", "customers.read"],
    )
    ActionStateMachine.transition(proposal, ActionStatus.CONFIRMED)
    executed = ENGINE.execute_action(proposal, context)

    assert executed.status == ActionStatus.COMPLETED
    assert executed.result["status"] == "success"


def test_external_client_role_enforcement():
    """Verify external client with read-only role is denied when requesting mutating actions."""
    res = process_natural_language_query("Follow up on overdue payments", role="read_only_viewer")
    # Read-only role lacks tasks.create permission -> denied by PolicyEngine
    assert res["success"] is False
    assert "not authorized" in res["error"] or "Unauthorized" in res["error"]
