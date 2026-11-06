"""
Unit tests for Alamia OdooBridge Configuration.
"""

from alamia_odoobridge.config import BridgeSettings, ExecutionPolicy, TransportType


def test_default_settings():
    settings = BridgeSettings(_env_file=None, ODOO_PASSWORD="secret_password")
    assert settings.odoo_url == "http://localhost:8069"
    assert settings.odoo_db == "odoo_hospital"
    assert settings.odoo_username == "zelix_service"
    assert settings.odoo_password == "secret_password"
    assert settings.execution_policy == ExecutionPolicy.READ_ONLY
    assert settings.allow_unlink is False
    assert "sale.order:action_confirm" in settings.allowed_methods
    assert "ir.model.access" in settings.disallowed_models


def test_custom_overrides():
    settings = BridgeSettings(
        _env_file=None,
        ODOO_URL="https://prod.myclinic.com",
        ODOO_DB="clinic_prod",
        ODOO_USERNAME="custom_user",
        ODOO_PASSWORD="custom_pass",
        MCP_TRANSPORT=TransportType.STDIO,
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.WORKFLOW_EXECUTION,
        BRIDGE_ALLOW_UNLINK=True,
    )
    assert settings.odoo_url == "https://prod.myclinic.com"
    assert settings.odoo_db == "clinic_prod"
    assert settings.mcp_transport == TransportType.STDIO
    assert settings.execution_policy == ExecutionPolicy.WORKFLOW_EXECUTION
    assert settings.allow_unlink is True
