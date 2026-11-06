"""
Unit tests for Alamia OdooBridge PolicyEngine and Guardrails,
including explicit model:method allowlist pairs, service-account scopes,
and comprehensive explicit-allowlist role/action/model permission matrices.
"""

import pytest
from alamia_odoobridge.config import BridgeSettings, ExecutionPolicy
from alamia_odoobridge.core.policies import PolicyEngine
from alamia_odoobridge.core.context import PrincipalClaims, current_principal
from alamia_odoobridge.core.exceptions import PolicyViolationError, PermissionDeniedError


def test_disallowed_model_blocks_read_and_write():
    settings = BridgeSettings(
        _env_file=None,
        ODOO_PASSWORD="dummy",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.CONTROLLED_WRITES,
    )
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
    settings = BridgeSettings(
        _env_file=None,
        ODOO_PASSWORD="dummy",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.CONTROLLED_WRITES,
        BRIDGE_ALLOW_UNLINK=False,
    )
    engine = PolicyEngine(settings)

    with pytest.raises(PolicyViolationError) as exc_info:
        engine.check_unlink("crm.lead", [1, 2])
    assert "disabled by default" in str(exc_info.value)


def test_unlink_permitted_when_explicitly_enabled():
    settings = BridgeSettings(
        _env_file=None,
        ODOO_PASSWORD="dummy",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.CONTROLLED_WRITES,
        BRIDGE_ALLOW_UNLINK=True,
    )
    engine = PolicyEngine(settings)

    engine.check_unlink("crm.lead", [1, 2])

    with pytest.raises(PolicyViolationError):
        engine.check_unlink("ir.rule", [1])


def test_model_method_pair_allowlist():
    settings = BridgeSettings(
        _env_file=None,
        ODOO_PASSWORD="dummy",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.CONTROLLED_WRITES,
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


def test_service_account_restricted_to_read_only_by_default():
    """Default service account scopes are ['read'], rejecting writes and methods."""
    settings = BridgeSettings(
        _env_file=None,
        ODOO_PASSWORD="dummy",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.CONTROLLED_WRITES,
        BRIDGE_SERVICE_SCOPES=["read"],
        BRIDGE_DISALLOWED_MODELS=[],
        BRIDGE_ALLOW_UNLINK=True,
    )
    engine = PolicyEngine(settings)

    svc = PrincipalClaims(sub="service_account", is_service_only=True)
    token = current_principal.set(svc)
    try:
        # Reads succeed
        engine.check_read("res.partner")
        engine.check_module_inspection()

        # Writes fail
        with pytest.raises(PermissionDeniedError) as exc_w:
            engine.check_write("res.partner")
        assert "restricted to read-only access" in str(exc_w.value)

        # Methods fail
        with pytest.raises(PermissionDeniedError) as exc_m:
            engine.check_method_execution("sale.order", "action_confirm")
        assert "not permitted to execute business methods" in str(exc_m.value)

        # Unlink fails
        with pytest.raises(PermissionDeniedError) as exc_u:
            engine.check_unlink("res.partner", [1])
        assert "not permitted to delete records" in str(exc_u.value)
    finally:
        current_principal.reset(token)


def test_service_account_with_configured_write_scope():
    """Configuring BRIDGE_SERVICE_SCOPES allows service writes."""
    settings = BridgeSettings(
        _env_file=None,
        ODOO_PASSWORD="dummy",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.CONTROLLED_WRITES,
        BRIDGE_SERVICE_SCOPES=["read", "write", "execute"],
        BRIDGE_ALLOWED_METHODS=["sale.order:action_confirm"],
    )
    engine = PolicyEngine(settings)

    svc = PrincipalClaims(sub="service_account", is_service_only=True)
    token = current_principal.set(svc)
    try:
        engine.check_read("res.partner")
        engine.check_write("res.partner")
        engine.check_method_execution("sale.order", "action_confirm")
    finally:
        current_principal.reset(token)


def test_doctor_role_matrix_boundaries():
    """Doctors can manage clinical models and methods, but not accounting or company settings."""
    settings = BridgeSettings(
        _env_file=None,
        ODOO_PASSWORD="dummy",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.CONTROLLED_WRITES,
        BRIDGE_ALLOW_UNLINK=True,
        BRIDGE_ALLOWED_METHODS=["vet.appointment:action_confirm", "account.move:action_post"],
    )
    engine = PolicyEngine(settings)

    doctor = PrincipalClaims(sub="dr_smith", role="doctor", is_service_only=False)
    token = current_principal.set(doctor)
    try:
        # Clinical access passes
        engine.check_read("vet.patient")
        engine.check_write("vet.patient")
        engine.check_write("res.partner")
        engine.check_method_execution("vet.appointment", "action_confirm")

        # Accounting and unlisted models are denied
        with pytest.raises(PermissionDeniedError) as exc_acc:
            engine.check_read("account.move")
        assert "is not permitted to read 'account.move'" in str(exc_acc.value)

        with pytest.raises(PermissionDeniedError) as exc_acc_w:
            engine.check_write("account.move")
        assert "is not permitted to write to 'account.move'" in str(exc_acc_w.value)

        # Deletion is denied to doctors
        with pytest.raises(PermissionDeniedError):
            engine.check_unlink("vet.patient", [1])
    finally:
        current_principal.reset(token)


def test_receptionist_role_matrix_boundaries():
    """Receptionists can manage appointments and partners, but not clinical cases or inventory."""
    settings = BridgeSettings(
        _env_file=None,
        ODOO_PASSWORD="dummy",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.CONTROLLED_WRITES,
        BRIDGE_ALLOWED_METHODS=["vet.appointment:action_confirm"],
    )
    engine = PolicyEngine(settings)

    receptionist = PrincipalClaims(sub="frontdesk_amy", role="receptionist", is_service_only=False)
    token = current_principal.set(receptionist)
    try:
        engine.check_read("vet.appointment")
        engine.check_write("vet.appointment")
        engine.check_write("res.partner")
        engine.check_method_execution("vet.appointment", "action_confirm")

        # Clinical case write is denied
        with pytest.raises(PermissionDeniedError):
            engine.check_write("vet.cm.case")

        # Stock write is denied
        with pytest.raises(PermissionDeniedError):
            engine.check_write("stock.picking")
    finally:
        current_principal.reset(token)


def test_viewer_role_explicit_business_allowlist():
    """Viewer role is restricted to explicit business models and strictly cannot write."""
    settings = BridgeSettings(
        _env_file=None,
        ODOO_PASSWORD="dummy",
        BRIDGE_EXECUTION_POLICY=ExecutionPolicy.CONTROLLED_WRITES,
    )
    engine = PolicyEngine(settings)

    viewer = PrincipalClaims(sub="auditor_jane", role="viewer", is_service_only=False)
    token = current_principal.set(viewer)
    try:
        # Permitted business models succeed
        engine.check_read("res.partner")
        engine.check_read("vet.patient")

        # Unpermitted models (such as res.company or account.move) fail explicitly
        with pytest.raises(PermissionDeniedError) as exc_comp:
            engine.check_read("res.company")
        assert "is not permitted to read 'res.company'" in str(exc_comp.value)

        with pytest.raises(PermissionDeniedError) as exc_w:
            engine.check_write("res.partner")
        assert "is not authorized to write" in str(exc_w.value)

        with pytest.raises(PermissionDeniedError) as exc_m:
            engine.check_method_execution("account.move", "action_post")
        assert "cannot execute business method" in str(exc_m.value)
    finally:
        current_principal.reset(token)
