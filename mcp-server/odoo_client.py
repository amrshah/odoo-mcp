"""
Odoo XML-RPC Client helper for MCP Server
Supports Odoo 14, 15, 16, 17, 18, 19
"""

import os
import xmlrpc.client
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger("odoo_mcp.client")


class OdooClient:
    def __init__(
        self,
        url: Optional[str] = None,
        db: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        default_url = os.getenv("ODOO_LOCAL_URL") or os.getenv("ODOO_URL", "http://localhost:8069")
        if "web:" in default_url and not os.path.exists("/.dockerenv"):
            default_url = "http://localhost:8069"
        self.url = (url or default_url).rstrip("/")
        self.db = db or os.getenv("ODOO_DB", "odoo_hospital")
        self.username = username or os.getenv("ODOO_USERNAME", "admin")
        self.password = password or os.getenv("ODOO_PASSWORD", "admin")
        self.uid: Optional[int] = None
        
        self.common_endpoint = f"{self.url}/xmlrpc/2/common"
        self.object_endpoint = f"{self.url}/xmlrpc/2/object"
        
        self._common_proxy: Optional[xmlrpc.client.ServerProxy] = None
        self._object_proxy: Optional[xmlrpc.client.ServerProxy] = None

    @property
    def common(self) -> xmlrpc.client.ServerProxy:
        if self._common_proxy is None:
            self._common_proxy = xmlrpc.client.ServerProxy(
                self.common_endpoint, allow_none=True
            )
        return self._common_proxy

    @property
    def object(self) -> xmlrpc.client.ServerProxy:
        if self._object_proxy is None:
            self._object_proxy = xmlrpc.client.ServerProxy(
                self.object_endpoint, allow_none=True
            )
        return self._object_proxy

    def version(self) -> Dict[str, Any]:
        """Get Odoo server version and information."""
        try:
            return self.common.version()
        except Exception as e:
            logger.error(f"Error getting Odoo version: {e}")
            raise

    def authenticate(self, force_refresh: bool = False) -> int:
        """Authenticate with Odoo and return the User ID (UID)."""
        if self.uid is not None and not force_refresh:
            return self.uid

        try:
            uid = self.common.authenticate(
                self.db, self.username, self.password, {}
            )
            if not uid:
                raise ValueError(
                    f"Authentication failed for user '{self.username}' on database '{self.db}' at {self.url}."
                )
            self.uid = uid
            logger.info(f"Authenticated as user {self.username} (UID: {self.uid})")
            return self.uid
        except Exception as e:
            logger.error(f"Authentication exception: {e}")
            raise

    def execute_kw(
        self,
        model: str,
        method: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a model method on Odoo."""
        uid = self.authenticate()
        args = args or []
        kwargs = kwargs or {}
        try:
            return self.object.execute_kw(
                self.db,
                uid,
                self.password,
                model,
                method,
                args,
                kwargs,
            )
        except Exception as e:
            logger.error(f"Error executing {model}.{method}: {e}")
            raise

    def list_models(self, filter_term: str = "") -> List[Dict[str, Any]]:
        """Search available models in Odoo ir.model."""
        domain = []
        if filter_term:
            domain = ["|", ("model", "ilike", filter_term), ("name", "ilike", filter_term)]
        
        return self.execute_kw(
            "ir.model",
            "search_read",
            [domain],
            {"fields": ["id", "name", "model", "info", "state"], "limit": 100},
        )

    def get_model_fields(
        self, model: str, attributes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get field definitions and metadata for a model."""
        attrs = attributes or ["string", "type", "required", "readonly", "relation", "help"]
        return self.execute_kw(
            model,
            "fields_get",
            [],
            {"attributes": attrs},
        )

    def search(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        offset: int = 0,
        limit: Optional[int] = 50,
        order: Optional[str] = None,
    ) -> List[int]:
        """Search for record IDs matching domain filter."""
        domain = domain or []
        kwargs: Dict[str, Any] = {"offset": offset}
        if limit is not None:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order
        return self.execute_kw(model, "search", [domain], kwargs)

    def read(
        self,
        model: str,
        ids: List[int],
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Read specific fields for a list of record IDs."""
        kwargs = {}
        if fields:
            kwargs["fields"] = fields
        return self.execute_kw(model, "read", [ids], kwargs)

    def search_read(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        offset: int = 0,
        limit: Optional[int] = 50,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search and read records matching domain filter in one call."""
        domain = domain or []
        kwargs: Dict[str, Any] = {"offset": offset}
        if fields:
            kwargs["fields"] = fields
        if limit is not None:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order
        return self.execute_kw(model, "search_read", [domain], kwargs)

    def create(self, model: str, values: Dict[str, Any]) -> int:
        """Create a new record with the provided field-value mapping."""
        return self.execute_kw(model, "create", [values])

    def write(self, model: str, ids: List[int], values: Dict[str, Any]) -> bool:
        """Update existing record(s) with new field values."""
        return self.execute_kw(model, "write", [ids, values])

    def unlink(self, model: str, ids: List[int]) -> bool:
        """Delete record(s) by IDs."""
        return self.execute_kw(model, "unlink", [ids])

    def list_modules(self, state: str = "installed") -> List[Dict[str, Any]]:
        """List Odoo modules with their current state (installed, uninstalled, to upgrade)."""
        domain = []
        if state:
            domain = [("state", "=", state)]
        return self.execute_kw(
            "ir.module.module",
            "search_read",
            [domain],
            {"fields": ["name", "shortdesc", "state", "installed_version", "author"], "limit": 150},
        )
