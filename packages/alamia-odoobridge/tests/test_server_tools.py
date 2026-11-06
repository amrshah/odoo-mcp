"""
Integration and contract tests for the FastMCP tool registry in Alamia OdooBridge.
Verifies proper ToolError propagation and exact successful response contracts.
"""

import pytest
from unittest.mock import MagicMock
from fastmcp.exceptions import ToolError
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
        BRIDGE_ALLOWED_METHODS=["sale.order:action_confirm", "account.move:action_post"],
        BRIDGE_DISALLOWED_MODELS=["ir.model", "ir.model.fields", "ir.rule"],
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


async def test_odoo_unlink_record_raises_tool_error(mock_settings):
    server = create_bridge_server(mock_settings)
    tool = await server.get_tool("odoo_unlink_record")

    # Unlink is disabled in mock_settings; must raise ToolError (MCP isError: True)
    with pytest.raises(ToolError) as exc_info:
        tool.fn(model="res.partner", ids=[1, 2])
    assert "Destructive record deletion" in str(exc_info.value)
    assert "unlink_disabled" in str(exc_info.value) or "disabled by default" in str(exc_info.value)


async def test_odoo_execute_method_unlisted_pair_raises_tool_error(mock_settings):
    server = create_bridge_server(mock_settings)
    tool = await server.get_tool("odoo_execute_method")

    # Unlisted model:method pair must raise ToolError
    with pytest.raises(ToolError) as exc_info:
        tool.fn(model="res.partner", method="dangerous_method")
    assert "not in the permitted model:method allowlist" in str(exc_info.value)


async def test_odoo_search_read_disallowed_model_raises_tool_error(mock_settings):
    server = create_bridge_server(mock_settings)
    tool = await server.get_tool("odoo_search_read")

    # Administrative model access must raise ToolError
    with pytest.raises(ToolError) as exc_info:
        tool.fn(model="ir.rule")
    assert "prohibited by security policy" in str(exc_info.value)


async def test_odoo_list_models_filters_disallowed_models(mock_settings, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.list_models.return_value = [
        {"model": "res.partner", "name": "Contact"},
        {"model": "ir.rule", "name": "Access Rule"},
        {"model": "vet.patient", "name": "Patient"},
    ]

    monkeypatch.setattr("alamia_odoobridge.mcp.server.get_adapter", lambda s: mock_adapter)
    server = create_bridge_server(mock_settings)

    tool = await server.get_tool("odoo_list_models")
    res = tool.fn(filter_term="")

    # ir.rule is in disallowed_models and must be filtered out
    models = [m["model"] for m in res]
    assert "res.partner" in models
    assert "vet.patient" in models
    assert "ir.rule" not in models
