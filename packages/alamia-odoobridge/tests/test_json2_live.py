"""
Live Integration Tests for Json2Adapter against real Odoo 19 instance.
Exercises real HTTP JSON-2 endpoints, named parameters, Bearer authentication,
and full lifecycle (create, read, write, unlink, fields_get, version_info).
"""

import pytest
import httpx
from alamia_odoobridge.adapters.odoo.json2 import Json2Adapter
from alamia_odoobridge.core.exceptions import OdooBridgeError

LIVE_ODOO_URL = "http://localhost:8069"
LIVE_ODOO_DB = "odoo_hospital"
LIVE_ODOO_API_KEY = "c4f6ce9cbf49849cc832a377fbd96c6c8d4cd39c"


def is_live_odoo_available() -> bool:
    try:
        r = httpx.post(f"{LIVE_ODOO_URL}/web/webclient/version_info", json={}, timeout=1.5)
        return r.status_code == 200
    except Exception:
        return False


live_odoo_required = pytest.mark.skipif(
    not is_live_odoo_available(),
    reason="Live Odoo 19 container is not reachable on localhost:8069",
)


@pytest.fixture
def live_adapter():
    return Json2Adapter(
        url=LIVE_ODOO_URL,
        db=LIVE_ODOO_DB,
        api_key=LIVE_ODOO_API_KEY,
        timeout=10.0,
    )


@live_odoo_required
def test_live_json2_authentication_and_version(live_adapter):
    uid = live_adapter.authenticate()
    # In Odoo 19+ JSON-2 Bearer key auth, authenticate verifies access without manufacturing an artificial UID
    assert uid is None

    version_info = live_adapter.get_version()
    assert "server_version" in version_info
    assert "19" in version_info["server_version"]


@live_odoo_required
def test_live_json2_fields_and_search_read(live_adapter):
    fields = live_adapter.get_model_fields("res.partner", attributes=["string", "type"])
    assert "name" in fields
    assert fields["name"]["type"] in ("char", "varchar")

    records = live_adapter.search_read(
        "res.partner",
        domain=[],
        fields=["id", "name"],
        limit=3,
    )
    assert isinstance(records, list)
    assert len(records) > 0
    assert "name" in records[0]


@live_odoo_required
def test_live_json2_crud_lifecycle(live_adapter):
    # 1. Create with named vals_list contract
    created_id = live_adapter.create("res.partner", {
        "name": "Live Json2 CRUD Verification Partner",
        "is_company": False,
    })
    assert isinstance(created_id, int)
    assert created_id > 0

    try:
        # 2. Read
        read_res = live_adapter.read("res.partner", [created_id], fields=["id", "name", "comment"])
        assert len(read_res) == 1
        assert read_res[0]["id"] == created_id
        assert read_res[0]["name"] == "Live Json2 CRUD Verification Partner"

        # 3. Write with named ids and vals contract
        write_success = live_adapter.write("res.partner", [created_id], {
            "comment": "Verified via live JSON-2 test suite",
        })
        assert write_success is True

        # Verify update
        read_updated = live_adapter.read("res.partner", [created_id], fields=["comment"])
        assert "Verified via live JSON-2" in str(read_updated[0]["comment"])

    finally:
        # 4. Unlink with named ids contract
        delete_success = live_adapter.unlink("res.partner", [created_id])
        assert delete_success is True

        # Verify deletion
        remaining = live_adapter.search("res.partner", domain=[("id", "=", created_id)])
        assert len(remaining) == 0


@live_odoo_required
def test_live_json2_positional_args_rejection(live_adapter):
    """Verifies that arbitrary positional args fail explicitly under JSON-2."""
    with pytest.raises(OdooBridgeError) as exc_info:
        live_adapter.execute_method(
            model="res.partner",
            method="check_access_rights",
            args=["read"],
        )
    assert "does not support arbitrary positional arguments" in str(exc_info.value)
