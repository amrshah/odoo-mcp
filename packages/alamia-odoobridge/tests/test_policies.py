"""
Unit tests for Alamia OdooBridge PolicyEngine and Guardrails.
"""

import pytest
from alamia_odoobridge.config import BridgeSettings, ExecutionPolicy
from alamia_odoobridge.core.policies import PolicyEngine
from alamia_odoobridge.core.exceptions import PolicyViolationError


def test_disallowed_model_blocks_read():
    settings = BridgeSettings(ODOO_PASSWORD="dummy")
    engine = PolicyEngine(settings)

    # Should raise for administrative model
    with pytest.raises(PolicyViolationError) as exc_info:
        engine.check_read("ir.model.access")
    assert "prohibited by security policy" in str(exc_info.value)

    # Normal model should pass
    engine.check_read("res.partner")
    engine.check_read("vet.patient")


def test_read_only_policy_blocks_writes():
    settings = BridgeSettings(
        ODOO_PASSWORD="dummy",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.READ_ONLY,
    )
    engine = PolicyEngine(settings)

    with pytest.raises(PolicyViolationError) as exc_info:
        engine.check_write("res.partner")
    assert "READ_ONLY mode" in str(exc_info.value)


def test_unlink_disabled_by_default():
    settings = BridgeSettings(ODOO_PASSWORD="dummy", BRIDGE_ALLOW_UNLINK=False)
    engine = PolicyEngine(settings)

    with pytest.raises(PolicyViolationError) as exc_info:
        engine.check_unlink("crm.lead", [1, 2])
    assert "disabled by default" in str(exc_info.value)


def test_unlink_permitted_when_explicitly_enabled():
    settings = BridgeSettings(ODOO_PASSWORD="dummy", BRIDGE_ALLOW_UNLINK=True)
    engine = PolicyEngine(settings)

    # Should not raise for standard model
    engine.check_unlink("crm.lead", [1, 2])

    # But still forbidden on disallowed models
    with pytest.raises(PolicyViolationError):
        engine.check_unlink("ir.rule", [1])


def test_business_method_allowlist():
    settings = BridgeSettings(
        ODOO_PASSWORD="dummy",
        BRIDGE_ALLOWED_METHODS=["action_confirm", "button_validate"],
    )
    engine = PolicyEngine(settings)

    # Allowed methods pass
    engine.check_method_execution("sale.order", "action_confirm")
    engine.check_method_execution("stock.picking", "button_validate")

    # Unvetted methods fail
    with pytest.raises(PolicyViolationError) as exc_info:
        engine.check_method_execution("account.move", "arbitrary_dangerous_method")
    assert "not in the permitted business methods allowlist" in str(exc_info.value)
