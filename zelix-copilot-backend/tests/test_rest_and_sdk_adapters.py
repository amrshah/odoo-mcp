"""Tests for REST and Native SDK Application Adapters."""

import pytest
from typing import Any, Dict
from adapters.application.rest.adapter import RESTApplicationAdapter
from adapters.application.sdk.adapter import SDKApplicationAdapter
from core.runtime.engine import CopilotEngine
from core.sessions.context import EmployeeContext
from core.skills.registry import SkillRegistry
from core.tools.reference_tools import GetCustomerTool
from core.tools.registry import ToolRegistry
from skills.examples.customer_360 import Customer360Skill


class FakeSDKClient:
    """Mock external Python SDK class."""

    def __init__(self) -> None:
        self.customers = {"cust_sdk_1": {"id": "cust_sdk_1", "name": "SDK Fast Logistics"}}

    def get_customer(self, entity_id: str) -> Dict[str, Any]:
        return self.customers.get(entity_id, {})

    def get_customer_invoices(self, entity_id: str) -> list:
        return [{"id": "inv_sdk_1", "amount": 420.0, "status": "paid"}]

    def get_customer_tasks(self, entity_id: str) -> list:
        return []

    def execute_action(self, action_type: str, target: Dict[str, Any], changes: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "SDK_MUTATION_APPLIED", "action": action_type}


def fake_http_client(method: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Mock HTTP client for RESTApplicationAdapter."""
    if path == "/customer/cust_rest_1":
        return {"status": 200, "data": {"id": "cust_rest_1", "name": "REST Global Transport"}}
    elif path == "/customer/cust_rest_1/invoices":
        return {"status": 200, "data": [{"id": "inv_rest_1", "amount": 1200.0, "status": "paid"}]}
    elif path == "/customer/cust_rest_1/tasks":
        return {"status": 200, "data": []}
    return {"status": 200, "data": {}}


def test_rest_application_adapter():
    adapter = RESTApplicationAdapter(http_client=fake_http_client)
    cust = adapter.get("customer", "cust_rest_1")
    assert cust["name"] == "REST Global Transport"

    invoices = adapter.relationships("customer", "cust_rest_1", "invoices")
    assert len(invoices) == 1
    assert invoices[0]["amount"] == 1200.0


def test_sdk_application_adapter_in_engine():
    sdk_client = FakeSDKClient()
    adapter = SDKApplicationAdapter(sdk_client=sdk_client)

    skills = SkillRegistry()
    skills.register(Customer360Skill())

    tools = ToolRegistry()
    tools.register(GetCustomerTool(adapter))

    engine = CopilotEngine(
        skill_registry=skills,
        tool_registry=tools,
        application_adapter=adapter,
    )

    context = EmployeeContext(user_id="usr_sdk", role="sales_assistant", permissions=["customers.read"])
    res = engine.execute_skill("customer_360", context, customer_id="cust_sdk_1")

    assert res.success is True
    assert res.output["customer"]["name"] == "SDK Fast Logistics"
