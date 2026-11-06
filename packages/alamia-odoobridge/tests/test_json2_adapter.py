"""
Contract and unit tests for Json2Adapter.
Verifies named-parameter payload contracts, Bearer token headers, and typed error translations.
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


def test_json2_headers_and_auth_context(json2_adapter, monkeypatch):
    assert json2_adapter.client.headers["Authorization"] == "Bearer sec_token_json2_123"
    assert json2_adapter.client.headers["X-Odoo-Database"] == "odoo_test"

    # Mock context probe
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"uid": 7, "user": "api_user"}
    monkeypatch.setattr(json2_adapter.client, "get", lambda url: mock_resp)

    uid = json2_adapter.authenticate()
    assert uid == 7


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
    
    # Contract verification: payload must use named keys (not positional execute_kw tuple lists)
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
        resp.json.return_value = 99 if "create" in endpoint else True
        return resp

    monkeypatch.setattr(json2_adapter.client, "post", mock_post)

    # Test create
    new_id = json2_adapter.create("vet.patient", {"name": "Buddy", "species": "canine"})
    assert new_id == 99
    assert captured[0] == ("/json/2/vet.patient/create", {"values": {"name": "Buddy", "species": "canine"}})

    # Test write
    res_w = json2_adapter.write("vet.patient", [99], {"weight": 14.5})
    assert res_w is True
    assert captured[1] == ("/json/2/vet.patient/write", {"ids": [99], "values": {"weight": 14.5}})


def test_json2_named_parameters_execute_method(json2_adapter, monkeypatch):
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
        args=[101],
        kwargs={"validate": True},
    )

    assert result == {"status": "confirmed"}
    assert captured["endpoint"] == "/json/2/sale.order/action_confirm"
    assert captured["payload"] == {"args": [101], "kwargs": {"validate": True}}


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

    # Timeout
    def mock_timeout(*a, **kw):
        raise httpx.TimeoutException("Connection timed out")
    monkeypatch.setattr(json2_adapter.client, "post", mock_timeout)
    with pytest.raises(ConnectionError):
        json2_adapter.create("res.partner", {})
