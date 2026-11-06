"""
XML-RPC Adapter for Odoo 14, 15, 16, 17, 18, 19, and 20.
Implements the BaseOdooAdapter contract over Odoo's external XML-RPC endpoints.
"""

import logging
from typing import Any, Dict, List, Optional

from ...core.interfaces import BaseOdooAdapter
from ...core.exceptions import (
    AuthenticationError,
    ConnectionError,
    ModelNotFoundError,
    PermissionDeniedError,
    RecordNotFoundError,
    OdooBridgeError,
)
from .connection import SafeServerProxy

logger = logging.getLogger("alamia_odoobridge.adapter.xmlrpc")


class XmlRpcAdapter(BaseOdooAdapter):
    """Robust, thread-safe XML-RPC adapter for Odoo."""

    def __init__(self, url: str, db: str, username: str, password: str, timeout: float = 30.0):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password
        self.timeout = timeout
        self.uid: Optional[int] = None

        self.common_endpoint = f"{self.url}/xmlrpc/2/common"
        self.object_endpoint = f"{self.url}/xmlrpc/2/object"

    def _get_common_proxy(self):
        return SafeServerProxy.create(self.common_endpoint, timeout=self.timeout)

    def _get_object_proxy(self):
        return SafeServerProxy.create(self.object_endpoint, timeout=self.timeout)

    def authenticate(self) -> int:
        """Authenticate and cache the user ID."""
        if not self.username or not self.password:
            raise AuthenticationError("Odoo credentials missing: username and password are required")

        try:
            proxy = self._get_common_proxy()
            uid = proxy.authenticate(self.db, self.username, self.password, {})
            if not uid:
                raise AuthenticationError(
                    f"Authentication failed for user '{self.username}' on database '{self.db}'"
                )
            self.uid = uid
            logger.debug("Successfully authenticated UID: %s", self.uid)
            return self.uid
        except AuthenticationError:
            raise
        except Exception as e:
            raise ConnectionError(f"Could not connect to Odoo XML-RPC service at {self.url}: {e}")

    def _ensure_authenticated(self) -> int:
        if self.uid is None:
            return self.authenticate()
        return self.uid

    def get_version(self) -> Dict[str, Any]:
        """Fetch Odoo version information."""
        try:
            proxy = self._get_common_proxy()
            return proxy.version()
        except Exception as e:
            raise ConnectionError(f"Failed to query Odoo version: {e}")

    def execute_kw(self, model: str, method: str, args: Optional[List[Any]] = None, kwargs: Optional[Dict[str, Any]] = None) -> Any:
        """Low-level execution proxy with standardized exception handling."""
        uid = self._ensure_authenticated()
        args = args or []
        kwargs = kwargs or {}

        try:
            proxy = self._get_object_proxy()
            return proxy.execute_kw(self.db, uid, self.password, model, method, args, kwargs)
        except Exception as e:
            err_str = str(e)
            if "Access Denied" in err_str or "AccessError" in err_str:
                raise PermissionDeniedError(f"Odoo permission denied on {model}.{method}: {err_str}")
            if "KeyError" in err_str or "does not exist" in err_str:
                raise ModelNotFoundError(model)
            raise OdooBridgeError(f"Odoo RPC error on {model}.{method}: {err_str}", details={"model": model, "method": method})

    def list_models(self, filter_term: str = "") -> List[Dict[str, Any]]:
        domain = [("transient", "=", False)]
        if filter_term:
            domain = ["&", ("transient", "=", False), "|", ("name", "ilike", filter_term), ("model", "ilike", filter_term)]
        return self.execute_kw("ir.model", "search_read", [domain], {"fields": ["id", "name", "model", "info"], "limit": 100})

    def get_model_fields(self, model: str, attributes: Optional[List[str]] = None) -> Dict[str, Any]:
        attrs = attributes or ["string", "type", "required", "readonly", "relation", "help", "selection"]
        return self.execute_kw(model, "fields_get", [], {"attributes": attrs})

    def search(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        offset: int = 0,
        limit: Optional[int] = 50,
        order: Optional[str] = None,
    ) -> List[int]:
        domain = domain or []
        kwargs: Dict[str, Any] = {"offset": offset}
        if limit is not None:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order
        return self.execute_kw(model, "search", [domain], kwargs)

    def search_read(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        offset: int = 0,
        limit: int = 20,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        domain = domain or []
        kwargs: Dict[str, Any] = {"offset": offset, "limit": limit}
        if fields:
            kwargs["fields"] = fields
        if order:
            kwargs["order"] = order
        return self.execute_kw(model, "search_read", [domain], kwargs)

    def read(self, model: str, ids: List[int], fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        res = self.execute_kw(model, "read", [ids], kwargs)
        if not res and ids:
            raise RecordNotFoundError(model, ids)
        return res

    def create(self, model: str, values: Dict[str, Any]) -> int:
        return self.execute_kw(model, "create", [values])

    def write(self, model: str, ids: List[int], values: Dict[str, Any]) -> bool:
        return bool(self.execute_kw(model, "write", [ids, values]))

    def unlink(self, model: str, ids: List[int]) -> bool:
        return bool(self.execute_kw(model, "unlink", [ids]))

    def execute_method(
        self,
        model: str,
        method: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        return self.execute_kw(model, method, args, kwargs)

    def list_modules(self, state: str = "installed") -> List[Dict[str, Any]]:
        domain = []
        if state:
            domain.append(("state", "=", state))
        return self.execute_kw("ir.module.module", "search_read", [domain], {"fields": ["id", "name", "shortdesc", "state", "installed_version"]})
