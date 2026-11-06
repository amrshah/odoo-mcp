"""
Thread-safe connection manager for Odoo XML-RPC endpoints with explicit timeouts
supporting both HTTP and HTTPS transports.
"""

import socket
import xmlrpc.client
from typing import Optional
from ...core.exceptions import ConnectionError


class TimeoutTransport(xmlrpc.client.Transport):
    """Custom HTTP XML-RPC Transport supporting explicit socket timeouts."""

    def __init__(self, timeout: float = 30.0, use_datetime: bool = False):
        super().__init__(use_datetime=use_datetime)
        self.timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self.timeout
        return conn


class TimeoutSafeTransport(xmlrpc.client.SafeTransport):
    """Custom HTTPS XML-RPC Transport supporting explicit socket timeouts."""

    def __init__(self, timeout: float = 30.0, use_datetime: bool = False, context=None):
        super().__init__(use_datetime=use_datetime, context=context)
        self.timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self.timeout
        return conn


class SafeServerProxy:
    """Creates isolated, thread-safe XML-RPC ServerProxy instances with explicit transport timeouts."""

    @staticmethod
    def create(endpoint_url: str, timeout: float = 30.0) -> xmlrpc.client.ServerProxy:
        if endpoint_url.lower().startswith("https://"):
            transport = TimeoutSafeTransport(timeout=timeout)
        else:
            transport = TimeoutTransport(timeout=timeout)

        try:
            return xmlrpc.client.ServerProxy(endpoint_url, transport=transport, allow_none=True)
        except Exception as e:
            raise ConnectionError(f"Failed to create XML-RPC proxy for {endpoint_url}: {e}")
