"""
External JSON-2 Adapter for Odoo 19+ and 20.x.
Communicates with Odoo's modern HTTP JSON-2 API using HTTP client and API keys.
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from ...core.interfaces import BaseOdooAdapter
from ...core.exceptions import (
    AuthenticationError,
    ConnectionError,
    ModelNotFoundError,
    PermissionDeniedError,
    OdooBridgeError,
)

logger = logging.getLogger("alamia_odoobridge.adapter.json2")


class Json2Adapter(BaseOdooAdapter):
    """Modern Odoo External JSON-2 HTTP API adapter."""

    def __init__(self, url: str, db: str, api_key: str, timeout: float = 30.0):
        self.url = url.rstrip("/")
        self.db = db
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.Client(
            base_url=self.url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Odoo-Database": self.db,
            },
        )

    def authenticate(self) -> int:
        """Verify API key validity via context probe."""
        try:
            res = self.client.get("/json/2/context")
            if res.status_code in (401, 403):
                raise AuthenticationError("JSON-2 API key refused by Odoo")
            res.raise_for_status()
            data = res.json()
            return data.get("uid", 1)
        except AuthenticationError:
            raise
        except Exception as e:
            raise ConnectionError(f"Could not connect to Odoo JSON-2 endpoint at {self.url}: {e}")

    def get_version(self) -> Dict[str, Any]:
        try:
            res = self.client.get("/web/webclient/version_info")
            if res.status_code == 200:
                return res.json().get("result", {})
            return {"server_version": "19.0+", "protocol": "json-2"}
        except Exception as e:
            raise ConnectionError(f"Failed to query Odoo version via JSON-2: {e}")

    def _call(self, endpoint: str, payload: Dict[str, Any]) -> Any:
        try:
            res = self.client.post(endpoint, json=payload)
            if res.status_code == 403:
                raise PermissionDeniedError(f"Forbidden: {res.text}")
            if res.status_code == 404:
                raise ModelNotFoundError(endpoint)
            res.raise_for_status()
            data = res.json()
            if "error" in data:
                raise OdooBridgeError(f"JSON-2 API error: {data['error']}")
            return data.get("result", data)
        except (PermissionDeniedError, ModelNotFoundError, OdooBridgeError):
            raise
        except Exception as e:
            raise OdooBridgeError(f"HTTP call to {endpoint} failed: {e}")

    def list_models(self, filter_term: str = "") -> List[Dict[str, Any]]:
        domain = [("transient", "=", False)]
        if filter_term:
            domain = ["&", ("transient", "=", False), "|", ("name", "ilike", filter_term), ("model", "ilike", filter_term)]
        return self.search_read("ir.model", domain=domain, fields=["id", "name", "model", "info"], limit=100)

    def get_model_fields(self, model: str, attributes: Optional[List[str]] = None) -> Dict[str, Any]:
        attrs = attributes or ["string", "type", "required", "readonly", "relation", "help", "selection"]
        return self._call(f"/json/2/{model}/fields_get", {"attributes": attrs})

    def search(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        offset: int = 0,
        limit: Optional[int] = 50,
        order: Optional[str] = None,
    ) -> List[int]:
        payload: Dict[str, Any] = {"domain": domain or [], "offset": offset}
        if limit is not None:
            payload["limit"] = limit
        if order:
            payload["order"] = order
        return self._call(f"/json/2/{model}/search", payload)

    def search_read(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        offset: int = 0,
        limit: int = 20,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "domain": domain or [],
            "offset": offset,
            "limit": limit,
        }
        if fields:
            payload["fields"] = fields
        if order:
            payload["order"] = order
        return self._call(f"/json/2/{model}/search_read", payload)

    def read(self, model: str, ids: List[int], fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {"ids": ids}
        if fields:
            payload["fields"] = fields
        return self._call(f"/json/2/{model}/read", payload)

    def create(self, model: str, values: Dict[str, Any]) -> int:
        return self._call(f"/json/2/{model}/create", {"values": values})

    def write(self, model: str, ids: List[int], values: Dict[str, Any]) -> bool:
        return bool(self._call(f"/json/2/{model}/write", {"ids": ids, "values": values}))

    def unlink(self, model: str, ids: List[int]) -> bool:
        return bool(self._call(f"/json/2/{model}/unlink", {"ids": ids}))

    def execute_method(
        self,
        model: str,
        method: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        return self._call(f"/json/2/{model}/{method}", kwargs or {})

    def list_modules(self, state: str = "installed") -> List[Dict[str, Any]]:
        domain = [("state", "=", state)] if state else []
        return self.search_read("ir.module.module", domain=domain, fields=["id", "name", "shortdesc", "state", "installed_version"])
