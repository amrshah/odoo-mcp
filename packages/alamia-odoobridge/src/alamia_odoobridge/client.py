"""
Canonical OdooClient for Alamia OdooBridge.
Provides backward-compatible drop-in replacement for existing odoo_client.py implementations
across Zelix Copilot and scripts, routing all connectivity through the robust adapter layer.
"""

import os
from typing import Any, Dict, List, Optional
from .config import BridgeSettings, get_settings
from .adapters.odoo import get_adapter, XmlRpcAdapter
from .core.interfaces import BaseOdooAdapter


class OdooClient:
    """Canonical client for external Odoo connectivity with connection pooling and timeouts."""

    def __init__(
        self,
        url: Optional[str] = None,
        db: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 30.0,
    ):
        cfg = get_settings()
        default_url = os.getenv("ODOO_LOCAL_URL") or os.getenv("ODOO_URL") or cfg.odoo_url
        if "web:" in default_url and not os.path.exists("/.dockerenv"):
            default_url = "http://localhost:8069"

        self.url = (url or default_url).rstrip("/")
        self.db = db or os.getenv("ODOO_DB") or cfg.odoo_db
        self.username = username or os.getenv("ODOO_USERNAME") or cfg.odoo_username
        self.password = password or os.getenv("ODOO_PASSWORD") or cfg.odoo_password
        self.timeout = timeout

        self.adapter: BaseOdooAdapter = XmlRpcAdapter(
            url=self.url,
            db=self.db,
            username=self.username,
            password=self.password,
            timeout=self.timeout,
        )

    @property
    def uid(self) -> Optional[int]:
        if hasattr(self.adapter, "uid"):
            return self.adapter.uid
        return None

    def version(self) -> Dict[str, Any]:
        """Get Odoo server version and information."""
        return self.adapter.get_version()

    def authenticate(self, force_refresh: bool = False) -> int:
        """Authenticate with Odoo and return UID."""
        if force_refresh and hasattr(self.adapter, "uid"):
            self.adapter.uid = None
        return self.adapter.authenticate()

    def execute_kw(
        self,
        model: str,
        method: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        return self.adapter.execute_method(model, method, args, kwargs)

    def search(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        offset: int = 0,
        limit: Optional[int] = 50,
        order: Optional[str] = None,
    ) -> List[int]:
        return self.adapter.search(model, domain, offset, limit, order)

    def search_read(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        offset: int = 0,
        limit: int = 20,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self.adapter.search_read(model, domain, fields, offset, limit, order)

    def read(
        self,
        model: str,
        ids: List[int],
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        return self.adapter.read(model, ids, fields)

    def create(self, model: str, values: Dict[str, Any]) -> int:
        return self.adapter.create(model, values)

    def write(self, model: str, ids: List[int], values: Dict[str, Any]) -> bool:
        return self.adapter.write(model, ids, values)

    def unlink(self, model: str, ids: List[int]) -> bool:
        return self.adapter.unlink(model, ids)

    def list_models(self, filter_term: str = "") -> List[Dict[str, Any]]:
        return self.adapter.list_models(filter_term)

    def get_model_fields(
        self,
        model: str,
        attributes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self.adapter.get_model_fields(model, attributes)

    def list_modules(self, state: str = "installed") -> List[Dict[str, Any]]:
        return self.adapter.list_modules(state)
