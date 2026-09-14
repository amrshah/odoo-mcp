"""Tests for Model Context Protocol (MCP) Client and MCPApplicationAdapter."""

import json
import pytest
from typing import Any, Dict
from adapters.application.mcp.adapter import MCPApplicationAdapter
from adapters.application.mcp.client import MCPClient
from core.runtime.engine import CopilotEngine
from core.sessions.context import EmployeeContext
from core.skills.registry import SkillRegistry
from core.tools.reference_tools import GetCustomerTool
from core.tools.registry import ToolRegistry
from skills.examples.customer_360 import Customer360Skill


def mock_mcp_server_dispatcher(req: Dict[str, Any]) -> Dict[str, Any]:
    """Mock external MCP server processing JSON-RPC 2.0 requests."""
    req_id = req.get("id", 1)
    method = req.get("method", "")
    params = req.get("params", {})

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {"name": "get_customer", "description": "Fetch customer profile", "inputSchema": {}},
                    {"name": "execute_action_mark_paid", "description": "Mark invoice paid", "inputSchema": {}},
                ]
            },
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "get_customer":
            cust_id = args.get("id") or args.get("customer_id")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"id": cust_id, "name": "MCP Client Enterprise", "tier": "platinum"})}]
                },
            }
        elif tool_name == "get_customer_relationships":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps([{"id": "inv_mcp_1", "amount": 999.0, "status": "paid"}])}]
                },
            }
        elif tool_name == "execute_action_mark_paid":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"status": "SUCCESS", "mcp_tx_id": "tx_999"})}]
                },
            }

    return {"jsonrpc": "2.0", "id": req_id, "result": {"content": []}}


def test_mcp_client_tool_listing_and_calling():
    client = MCPClient(transport_handler=mock_mcp_server_dispatcher)
    tools = client.list_tools()

    assert len(tools) == 2
    assert tools[0].name == "get_customer"

    res = client.call_tool("get_customer", {"id": "cust_mcp_1"})
    assert res.isError is False
    assert len(res.content) == 1
    data = json.loads(res.content[0]["text"])
    assert data["name"] == "MCP Client Enterprise"


def test_mcp_application_adapter_in_engine():
    client = MCPClient(transport_handler=mock_mcp_server_dispatcher)
    adapter = MCPApplicationAdapter(mcp_client=client)

    # Validate adapter operations
    cust = adapter.get("customer", "cust_100")
    assert cust["name"] == "MCP Client Enterprise"

    rels = adapter.relationships("customer", "cust_100", "invoices")
    assert len(rels) == 1
    assert rels[0]["id"] == "inv_mcp_1"

    # Validate MCP adapter bound to engine executing skill
    skills = SkillRegistry()
    skills.register(Customer360Skill())

    tools = ToolRegistry()
    tools.register(GetCustomerTool(adapter))

    engine = CopilotEngine(
        skill_registry=skills,
        tool_registry=tools,
        application_adapter=adapter,
    )

    context = EmployeeContext(user_id="usr_mcp", role="sales_assistant", permissions=["customers.read"])
    result = engine.execute_skill("customer_360", context, customer_id="cust_100")

    assert result.success is True
    assert result.output["customer"]["name"] == "MCP Client Enterprise"
