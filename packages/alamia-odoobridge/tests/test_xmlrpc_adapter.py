"""
Unit tests for Alamia OdooBridge XmlRpcAdapter using mocks.
"""

from unittest.mock import MagicMock, patch
import pytest
from alamia_odoobridge.adapters.odoo.xmlrpc import XmlRpcAdapter
from alamia_odoobridge.core.exceptions import AuthenticationError, RecordNotFoundError


def test_missing_credentials_raises_authentication_error():
    adapter = XmlRpcAdapter(
        url="http://localhost:8069",
        db="odoo_test",
        username="",
        password="",
    )
    with pytest.raises(AuthenticationError):
        adapter.authenticate()


@patch("alamia_odoobridge.adapters.odoo.xmlrpc.SafeServerProxy.create")
def test_authenticate_success(mock_proxy_create):
    mock_common = MagicMock()
    mock_common.authenticate.return_value = 42
    mock_proxy_create.return_value = mock_common

    adapter = XmlRpcAdapter(
        url="http://localhost:8069",
        db="odoo_test",
        username="test_user",
        password="test_password",
    )

    uid = adapter.authenticate()
    assert uid == 42
    assert adapter.uid == 42


@patch("alamia_odoobridge.adapters.odoo.xmlrpc.SafeServerProxy.create")
def test_read_nonexistent_record_raises_error(mock_proxy_create):
    mock_proxy = MagicMock()
    mock_proxy.authenticate.return_value = 42
    mock_proxy.execute_kw.return_value = []
    mock_proxy_create.return_value = mock_proxy

    adapter = XmlRpcAdapter(
        url="http://localhost:8069",
        db="odoo_test",
        username="test_user",
        password="test_password",
    )

    with pytest.raises(RecordNotFoundError):
        adapter.read("res.partner", ids=[99999])
