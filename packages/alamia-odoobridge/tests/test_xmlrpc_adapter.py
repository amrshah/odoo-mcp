"""
Unit and concurrency tests for XmlRpcAdapter and SafeServerProxy,
including connection timeouts, HTTPS transport selection, and multi-threaded concurrency.
"""

import socket
import pytest
from unittest.mock import MagicMock
from concurrent.futures import ThreadPoolExecutor

from alamia_odoobridge.adapters.odoo.xmlrpc import XmlRpcAdapter
from alamia_odoobridge.adapters.odoo.connection import SafeServerProxy, TimeoutTransport, TimeoutSafeTransport
from alamia_odoobridge.core.exceptions import AuthenticationError, ConnectionError, PermissionDeniedError


def test_transport_selection_http_vs_https():
    proxy_http = SafeServerProxy.create("http://localhost:8069/xmlrpc/2/common", timeout=15.0)
    assert isinstance(proxy_http._ServerProxy__transport, TimeoutTransport)
    assert proxy_http._ServerProxy__transport.timeout == 15.0

    proxy_https = SafeServerProxy.create("https://secure.erp.com/xmlrpc/2/common", timeout=25.0)
    assert isinstance(proxy_https._ServerProxy__transport, TimeoutSafeTransport)
    assert proxy_https._ServerProxy__transport.timeout == 25.0


def test_xmlrpc_timeout_raises_connection_error(monkeypatch):
    adapter = XmlRpcAdapter(
        url="http://localhost:8069",
        db="odoo_test",
        username="admin",
        password="secret_password",
        timeout=2.0,
    )

    mock_proxy = MagicMock()
    mock_proxy.authenticate.side_effect = socket.timeout("timed out")
    monkeypatch.setattr(adapter, "_get_common_proxy", lambda: mock_proxy)

    with pytest.raises(ConnectionError) as exc:
        adapter.authenticate()
    assert "timed out after 2.0s" in str(exc.value)


def test_xmlrpc_thread_safe_concurrency(monkeypatch):
    adapter = XmlRpcAdapter(
        url="http://localhost:8069",
        db="odoo_test",
        username="admin",
        password="secret_password",
        timeout=10.0,
    )

    auth_calls = 0
    def mock_auth_fn(*args, **kwargs):
        nonlocal auth_calls
        auth_calls += 1
        return 42

    mock_common = MagicMock()
    mock_common.authenticate.side_effect = mock_auth_fn
    monkeypatch.setattr(adapter, "_get_common_proxy", lambda: mock_common)

    mock_object = MagicMock()
    mock_object.execute_kw.return_value = [{"id": 1, "name": "Test Record"}]
    monkeypatch.setattr(adapter, "_get_object_proxy", lambda: mock_object)

    # Execute concurrent calls across 10 threads
    def worker(idx):
        return adapter.search_read("res.partner", domain=[("id", "=", idx)])

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, i) for i in range(20)]
        results = [f.result() for f in futures]

    assert len(results) == 20
    for r in results:
        assert r == [{"id": 1, "name": "Test Record"}]

    # Due to thread-safe double-check locking, authenticate should only have run once
    assert auth_calls == 1
    assert adapter.uid == 42


def test_xmlrpc_permission_denied_handling(monkeypatch):
    adapter = XmlRpcAdapter(
        url="http://localhost:8069",
        db="odoo_test",
        username="test_user",
        password="password",
    )
    adapter.uid = 10

    mock_object = MagicMock()
    mock_object.execute_kw.side_effect = Exception("Access Denied by Odoo Access Rules")
    monkeypatch.setattr(adapter, "_get_object_proxy", lambda: mock_object)

    with pytest.raises(PermissionDeniedError) as exc:
        adapter.execute_kw("account.move", "unlink", [[1]])
    assert "permission denied" in str(exc.value).lower()
