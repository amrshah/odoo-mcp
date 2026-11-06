"""
Integration and contract tests for the FastMCP tool registry in Alamia OdooBridge.
"""

import pytest
from alamia_odoobridge.config import BridgeSettings, ExecutionPolicy
from alamia_odoobridge.mcp.server import create_bridge_server


@pytest.fixture
def mock_settings():
    return BridgeSettings(
        _env_file=None,
        ODOO_URL="http://test-odoo:8069",
        ODOO_DB="test_db",
        ODOO_USERNAME="test_user",
        ODOO_PASSWORD="test_password",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.CONTROLLED_WRITES,
        BRIDGE_ALLOW_UNLINK=False,
    )


async def test_tool_registration(mock_settings):
    server = create_bridge_server(mock_settings)
    registered_tools = await server.list_tools()
    tools = [t.name for t in registered_tools]
    expected_tools = [
        "odoo_status",
        "odoo_list_models",
        "odoo_get_model_fields",
        "odoo_search_read",
        "odoo_read_records",
        "odoo_create_record",
        "odoo_write_record",
        "odoo_unlink_record",
        "odoo_execute_method",
        "odoo_list_modules",
    ]
    for exp in expected_tools:
        assert exp in tools, f"Missing expected tool: {exp}"
    assert len(tools) == 10


async def test_odoo_unlink_record_policy_denial(mock_settings):
    server = create_bridge_server(mock_settings)
    tool = await server.get_tool("odoo_unlink_record")

    # Unlink is disabled in mock_settings
    res = tool.fn(model="res.partner", ids=[1, 2])
    assert res["success"] is False
    assert "disabled by default" in res["error"]


async def test_odoo_execute_method_unvetted_denial(mock_settings):
    server = create_bridge_server(mock_settings)
    tool = await server.get_tool("odoo_execute_method")

    # Call arbitrary unvetted method
    res = tool.fn(model="sale.order", method="drop_all_tables")
    assert res["success"] is False
    assert "not in the permitted business methods allowlist" in res["error"]


async def test_odoo_write_disallowed_model_denial(mock_settings):
    server = create_bridge_server(mock_settings)
    tool = await server.get_tool("odoo_write_record")

    # Call write on administrative model
    res = tool.fn(model="ir.model.access", ids=[1], values={"perm_write": True})
    assert res["success"] is False
    assert "prohibited by security policy" in res["error"]
