"""
Unit tests for Alamia OdooBridge PolicyEngine and Guardrails,
including explicit model:method allowlist pairs, disallowed models,
read-only mode, and human principal role enforcement.
"""

import pytest
from alamia_odoobridge.config import BridgeSettings, ExecutionPolicy
from alamia_odoobridge.core.policies import PolicyEngine
from alamia_odoobridge.core.context import PrincipalClaims, current_principal
from alamia_odoobridge.core.exceptions import PolicyViolationError, PermissionDeniedError


def test_disallowed_model_blocks_read_and_write():
    settings = BridgeSettings(_env_file=None, ODOO_PASSWORD="dummy")
    engine = PolicyEngine(settings)

    with pytest.raises(PolicyViolationError) as exc_info:
        engine.check_read("ir.model.access")
    assert "prohibited by security policy" in str(exc_info.value)

    with pytest.raises(PolicyViolationError) as exc_w:
        engine.check_write("ir.rule")
    assert "prohibited by security policy" in str(exc_w.value)

    # Standard business models pass
    engine.check_read("res.partner")
    engine.check_read("vet.patient")


def test_read_only_policy_blocks_writes_and_methods():
    settings = BridgeSettings(
        _env_file=None,
        ODOO_PASSWORD="dummy",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.READ_ONLY,
    )
    engine = PolicyEngine(settings)

    with pytest.raises(PolicyViolationError) as exc_w:
        engine.check_write("res.partner")
    assert "READ_ONLY mode" in str(exc_w.value)

    with pytest.raises(PolicyViolationError) as exc_m:
        engine.check_method_execution("account.move", "action_post")
    assert "READ_ONLY mode" in str(exc_m.value)


def test_unlink_disabled_by_default():
    settings = BridgeSettings(_env_file=None, ODOO_PASSWORD="dummy", BRIDGE_ALLOW_UNLINK=False)
    engine = PolicyEngine(settings)

    with pytest.raises(PolicyViolationError) as exc_info:
        engine.check_unlink("crm.lead", [1, 2])
    assert "disabled by default" in str(exc_info.value)


def test_unlink_permitted_when_explicitly_enabled():
    settings = BridgeSettings(_env_file=None, ODOO_PASSWORD="dummy", BRIDGE_ALLOW_UNLINK=True)
    engine = PolicyEngine(settings)

    engine.check_unlink("crm.lead", [1, 2])

    with pytest.raises(PolicyViolationError):
        engine.check_unlink("ir.rule", [1])


def test_model_method_pair_allowlist():
    settings = BridgeSettings(
        _env_file=None,
        ODOO_PASSWORD="dummy",
        BRIDGE_ALLOWED_METHODS=["account.move:action_post", "sale.order:action_confirm"],
    )
    engine = PolicyEngine(settings)

    # Exact model:method match passes
    engine.check_method_execution("sale.order", "action_confirm")
    engine.check_method_execution("account.move", "action_post")

    # Calling action_confirm on unlisted model fails
    with pytest.raises(PolicyViolationError) as exc_wrong_model:
        engine.check_method_execution("crm.lead", "action_confirm")
    assert "not in the permitted model:method allowlist" in str(exc_wrong_model.value)

    # Calling unlisted method fails
    with pytest.raises(PolicyViolationError) as exc_wrong_method:
        engine.check_method_execution("account.move", "dangerous_method")
    assert "not in the permitted model:method allowlist" in str(exc_wrong_method.value)


def test_human_principal_role_enforcement():
    settings = BridgeSettings(_env_file=None, ODOO_PASSWORD="dummy")
    engine = PolicyEngine(settings)

    # Human principal with read-only viewer role
    viewer = PrincipalClaims(sub="auditor_jane", role="viewer", is_service_only=False)
    token = current_principal.set(viewer)
    try:
        # Read should succeed
        engine.check_read("res.partner")

        # Write must be denied based on human role
        with pytest.raises(PermissionDeniedError) as exc:
            engine.check_write("res.partner")
        assert "is not authorized to write" in str(exc.value)

        # Method execution must be denied
        with pytest.raises(PermissionDeniedError) as exc_m:
            engine.check_method_execution("account.move", "action_post")
        assert "cannot execute business method" in str(exc_m.value)
    finally:
        current_principal.reset(token)
