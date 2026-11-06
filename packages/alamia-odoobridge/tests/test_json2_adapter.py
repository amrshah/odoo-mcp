"""
Contract and unit tests for Json2Adapter.
Verifies named-parameter payload contracts, Bearer token headers, explicit args rejection,
and typed error translations according to Odoo 19 WebJson2Controller.
"""

import pytest
import httpx
from unittest.mock import MagicMock

from alamia_odoobridge.adapters.odoo.json2 import Json2Adapter
from alamia_odoobridge.core.exceptions import (
    AuthenticationError,
    ConnectionError,
    ModelNotFoundError,
    PermissionDeniedError,
    OdooBridgeError,
)


@pytest.fixture
def json2_adapter():
    return Json2Adapter(
        url="http://test-odoo:8069",
        db="odoo_test",
        api_key="sec_token_json2_123",
        timeout=5.0,
    )


def test_json2_headers_and_auth_probe(json2_adapter, monkeypatch):
    assert json2_adapter.client.headers["Authorization"] == "Bearer sec_token_json2_123"
    assert json2_adapter.client.headers["X-Odoo-Database"] == "odoo_test"

    # Mock authenticate probe via check_access_rights
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = None
    monkeypatch.setattr(json2_adapter.client, "post", lambda endpoint, json: mock_resp)

    auth_result = json2_adapter.authenticate()
    # Explicitly returns None for Bearer API-key authentication
    assert auth_result is None


def test_json2_authenticate_invalid_api_key_raises_authentication_error(json2_adapter, monkeypatch):
    """HTTP 401 must raise AuthenticationError, indicating invalid/revoked credentials."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    monkeypatch.setattr(json2_adapter.client, "post", lambda endpoint, json: mock_resp)

    with pytest.raises(AuthenticationError) as exc:
        json2_adapter.authenticate()
    assert "Invalid API key" in str(exc.value)


def test_json2_authenticate_insufficient_permissions_raises_permission_denied(json2_adapter, monkeypatch):
    """HTTP 403 must raise PermissionDeniedError (NOT ConnectionError)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "User lacks read permission on res.users"
    monkeypatch.setattr(json2_adapter.client, "post", lambda endpoint, json: mock_resp)

    with pytest.raises(PermissionDeniedError) as exc:
        json2_adapter.authenticate()
    assert "lacks model permissions" in str(exc.value)


def test_json2_authenticate_network_failure_raises_connection_error(json2_adapter, monkeypatch):
    """Network/timeout failure must raise ConnectionError."""
    def mock_net_fail(*args, **kwargs):
        raise httpx.ConnectError("Connection refused by host")

    monkeypatch.setattr(json2_adapter.client, "post", mock_net_fail)

    with pytest.raises(ConnectionError) as exc:
        json2_adapter.authenticate()
    assert "timed out or failed" in str(exc.value)



def test_json2_named_parameters_search_read(json2_adapter, monkeypatch):
    captured_call = {}

    def mock_post(endpoint, json):
        captured_call["endpoint"] = endpoint
        captured_call["payload"] = json
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [{"id": 10, "name": "Hospital Partner"}]
        return resp

    monkeypatch.setattr(json2_adapter.client, "post", mock_post)

    records = json2_adapter.search_read(
        model="res.partner",
        domain=[("is_company", "=", True)],
        fields=["id", "name"],
        offset=5,
        limit=10,
        order="id desc",
    )

    assert records == [{"id": 10, "name": "Hospital Partner"}]
    assert captured_call["endpoint"] == "/json/2/res.partner/search_read"

    payload = captured_call["payload"]
    assert payload["domain"] == [("is_company", "=", True)]
    assert payload["fields"] == ["id", "name"]
    assert payload["offset"] == 5
    assert payload["limit"] == 10
    assert payload["order"] == "id desc"


def test_json2_named_parameters_create_and_write(json2_adapter, monkeypatch):
    captured = []

    def mock_post(endpoint, json):
        captured.append((endpoint, json))
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [99] if "create" in endpoint else True
        return resp

    monkeypatch.setattr(json2_adapter.client, "post", mock_post)

    # Test create: must use vals_list contract
    new_id = json2_adapter.create("vet.patient", {"name": "Buddy", "species": "canine"})
    assert new_id == 99
    assert captured[0] == ("/json/2/vet.patient/create", {"vals_list": [{"name": "Buddy", "species": "canine"}]})

    # Test write: must use ids and vals contract
    res_w = json2_adapter.write("vet.patient", [99], {"weight": 14.5})
    assert res_w is True
    assert captured[1] == ("/json/2/vet.patient/write", {"ids": [99], "vals": {"weight": 14.5}})


def test_json2_explicit_positional_args_rejection(json2_adapter):
    """Positional args must fail explicitly under JSON-2."""
    with pytest.raises(OdooBridgeError) as exc_info:
        json2_adapter.execute_method(
            model="sale.order",
            method="action_confirm",
            args=[101],
            kwargs={"validate": True},
        )
    assert "does not support arbitrary positional arguments" in str(exc_info.value)


def test_json2_named_kwargs_execute_method(json2_adapter, monkeypatch):
    captured = {}

    def mock_post(endpoint, json):
        captured["endpoint"] = endpoint
        captured["payload"] = json
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"status": "confirmed"}
        return resp

    monkeypatch.setattr(json2_adapter.client, "post", mock_post)

    result = json2_adapter.execute_method(
        model="sale.order",
        method="action_confirm",
        kwargs={"ids": [101], "validate": True},
    )

    assert result == {"status": "confirmed"}
    assert captured["endpoint"] == "/json/2/sale.order/action_confirm"
    assert captured["payload"] == {"ids": [101], "validate": True}


def test_json2_http_error_translations(json2_adapter, monkeypatch):
    # 401 Unauthorized
    resp_401 = MagicMock()
    resp_401.status_code = 401
    monkeypatch.setattr(json2_adapter.client, "post", lambda *a, **kw: resp_401)
    with pytest.raises(AuthenticationError):
        json2_adapter.create("res.partner", {"name": "Test"})

    # 403 Forbidden
    resp_403 = MagicMock()
    resp_403.status_code = 403
    resp_403.text = "ACL Access Denied"
    monkeypatch.setattr(json2_adapter.client, "post", lambda *a, **kw: resp_403)
    with pytest.raises(PermissionDeniedError):
        json2_adapter.create("res.partner", {"name": "Test"})

    # 404 Model Not Found
    resp_404 = MagicMock()
    resp_404.status_code = 404
    monkeypatch.setattr(json2_adapter.client, "post", lambda *a, **kw: resp_404)
    with pytest.raises(ModelNotFoundError):
        json2_adapter.create("nonexistent.model", {})

    # 422 Parameter Binding Error
    resp_422 = MagicMock()
    resp_422.status_code = 422
    resp_422.text = "missing a required argument: 'vals'"
    monkeypatch.setattr(json2_adapter.client, "post", lambda *a, **kw: resp_422)
    with pytest.raises(OdooBridgeError) as exc_422:
        json2_adapter.write("res.partner", [1], {})
    assert "parameter binding error" in str(exc_422.value)

    # Timeout
    def mock_timeout(*a, **kw):
        raise httpx.TimeoutException("Connection timed out")
    monkeypatch.setattr(json2_adapter.client, "post", mock_timeout)
    with pytest.raises(ConnectionError):
        json2_adapter.create("res.partner", {})


def test_json2_cross_company_isolation_enforced(json2_adapter, monkeypatch):
    """Enforces that a caller cannot escape their verified principal company context."""
    from alamia_odoobridge.core.context import PrincipalClaims, current_principal

    captured_payloads = []

    def mock_post(endpoint, json):
        captured_payloads.append(json)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"status": "ok"}
        return resp

    monkeypatch.setattr(json2_adapter.client, "post", mock_post)

    # Principal is authenticated strictly for Company ID 1
    principal = PrincipalClaims(sub="dr_tenant1", role="doctor", company_id=1)
    token = current_principal.set(principal)
    try:
        # Case 1: Caller passes matching company context -> succeeds and executes with company 1
        json2_adapter.execute_method(
            model="crm.lead",
            method="action_set_won",
            kwargs={"context": {"allowed_company_ids": [1]}},
        )
        assert captured_payloads[0]["context"]["allowed_company_ids"] == [1]

        # Case 2: Caller passes no context -> automatically injected with company 1
        json2_adapter.execute_method(
            model="crm.lead",
            method="action_set_won",
            kwargs={"status": "won"},
        )
        assert captured_payloads[1]["context"]["allowed_company_ids"] == [1]

        # Case 3: Caller attempts to override context to escape to Company 2 -> REJECTED
        with pytest.raises(PermissionDeniedError) as exc_info:
            json2_adapter.execute_method(
                model="crm.lead",
                method="action_set_won",
                kwargs={"context": {"allowed_company_ids": [2]}},
            )
        assert "Company context violation" in str(exc_info.value)
        assert "violates verified principal company_id=1" in str(exc_info.value)

        # Case 4: Caller attempts to expand to multiple companies [1, 2] -> REJECTED
        with pytest.raises(PermissionDeniedError) as exc_info2:
            json2_adapter.execute_method(
                model="crm.lead",
                method="action_set_won",
                kwargs={"context": {"allowed_company_ids": [1, 2]}},
            )
        assert "Company context violation" in str(exc_info2.value)
    finally:
        current_principal.reset(token)

