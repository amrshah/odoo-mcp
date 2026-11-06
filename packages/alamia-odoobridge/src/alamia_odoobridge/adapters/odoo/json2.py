"""
External JSON-2 Adapter for Odoo 19+ and 20.x.
Communicates with Odoo's modern HTTP JSON-2 API using HTTP client, Bearer API keys,
and explicit named-parameter payload contracts (not positional execute_kw translation).
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from ...core.interfaces import BaseOdooAdapter
from ...core.context import current_principal
from ...core.exceptions import (
    AuthenticationError,
    ConnectionError,
    ModelNotFoundError,
    PermissionDeniedError,
    OdooBridgeError,
)

logger = logging.getLogger("alamia_odoobridge.adapter.json2")


class Json2Adapter(BaseOdooAdapter):
    """
    Modern Odoo External JSON-2 HTTP API adapter.
    Operates strictly via named parameter contracts matching Odoo 19 WebJson2Controller.
    """

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

    def authenticate(self) -> Optional[int]:
        """
        Verify API key validity against Odoo JSON-2 endpoint.
        Under Odoo 19+ Bearer key authentication, credential validity is verified
        directly via res.users check_access_rights. Numeric UID is server-managed and not
        exposed as an artificial user ID; returns None to indicate verified Bearer credentials.
        """
        if not self.api_key:
            raise AuthenticationError("Odoo JSON-2 credentials missing: API key is required")

        try:
            self._call("/json/2/res.users/check_access_rights", {"operation": "read"})
            return None
        except AuthenticationError:
            raise
        except httpx.TimeoutException:
            raise ConnectionError(f"Connection to Odoo JSON-2 endpoint at {self.url} timed out after {self.timeout}s")
        except Exception as e:
            raise ConnectionError(f"Could not connect to Odoo JSON-2 endpoint at {self.url}: {e}")

    def get_version(self) -> Dict[str, Any]:
        """Fetch Odoo version information via webclient endpoint."""
        try:
            res = self.client.post("/web/webclient/version_info", json={})
            if res.status_code == 200:
                result = res.json().get("result", {})
                if result:
                    return result
            return {"server_version": "unknown", "protocol": "json-2"}
        except httpx.TimeoutException:
            raise ConnectionError(f"JSON-2 version check timed out after {self.timeout}s")
        except Exception as e:
            raise ConnectionError(f"Failed to query Odoo version via JSON-2: {e}")

    def _call(self, endpoint: str, payload: Dict[str, Any]) -> Any:
        """
        Execute a named-parameter POST call to an Odoo JSON-2 endpoint.
        Automatically injects caller context (allowed_company_ids) if available from principal.
        """
        body = dict(payload)

        # Strictly enforce verified company context against caller overrides
        principal = current_principal.get()
        if principal and principal.company_id:
            ctx = dict(body.get("context", {})) if isinstance(body.get("context"), dict) else {}
            caller_companies = ctx.get("allowed_company_ids")
            if caller_companies:
                if not all(cid == principal.company_id for cid in caller_companies):
                    raise PermissionDeniedError(
                        f"Company context violation: Caller attempted to specify allowed_company_ids={caller_companies}, "
                        f"which violates verified principal company_id={principal.company_id}"
                    )
            ctx["allowed_company_ids"] = [principal.company_id]
            body["context"] = ctx

        try:
            res = self.client.post(endpoint, json=body)
            if res.status_code == 401:
                raise AuthenticationError(f"Unauthorized: JSON-2 key rejected at {endpoint}")
            if res.status_code == 403:
                raise PermissionDeniedError(f"Forbidden: {res.text}")
            if res.status_code == 404:
                raise ModelNotFoundError(f"Model or endpoint not found: {endpoint}")
            if res.status_code == 422:
                raise OdooBridgeError(
                    f"JSON-2 parameter binding error (HTTP 422): {res.text}",
                    details={"endpoint": endpoint, "payload_keys": list(body.keys())},
                )
            res.raise_for_status()

            data = res.json()
            if isinstance(data, dict) and "error" in data:
                err_info = data["error"]
                msg = err_info.get("message", str(err_info)) if isinstance(err_info, dict) else str(err_info)
                raise OdooBridgeError(f"JSON-2 API error: {msg}", details={"endpoint": endpoint, "error": err_info})

            return data.get("result", data) if isinstance(data, dict) else data
        except (AuthenticationError, PermissionDeniedError, ModelNotFoundError, OdooBridgeError):
            raise
        except httpx.TimeoutException:
            raise ConnectionError(f"HTTP call to {endpoint} timed out after {self.timeout}s")
        except Exception as e:
            raise OdooBridgeError(f"HTTP call to {endpoint} failed: {e}")

    def list_models(self, filter_term: str = "") -> List[Dict[str, Any]]:
        domain: List[Any] = [("transient", "=", False)]
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
        """
        Create a new record in Odoo via JSON-2.
        Odoo 19 WebJson2Controller maps create to BaseModel.create(vals_list).
        Returns the integer ID of the created record.
        """
        result = self._call(f"/json/2/{model}/create", {"vals_list": [values]})
        if isinstance(result, list) and len(result) > 0:
            return int(result[0])
        return int(result)

    def write(self, model: str, ids: List[int], values: Dict[str, Any]) -> bool:
        """
        Update records in Odoo via JSON-2.
        Odoo 19 WebJson2Controller maps write to BaseModel.write(vals).
        """
        return bool(self._call(f"/json/2/{model}/write", {"ids": ids, "vals": values}))

    def unlink(self, model: str, ids: List[int]) -> bool:
        """
        Delete records in Odoo via JSON-2.
        Odoo 19 WebJson2Controller maps unlink to BaseModel.unlink().
        """
        return bool(self._call(f"/json/2/{model}/unlink", {"ids": ids}))

    def execute_method(
        self,
        model: str,
        method: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a business method via Odoo JSON-2.
        Odoo 19 WebJson2Controller binds named kwargs directly to the method signature.
        Positional 'args' are not supported by the JSON-2 RPC protocol and must fail explicitly.
        """
        if args and len(args) > 0:
            raise OdooBridgeError(
                f"Odoo JSON-2 protocol does not support arbitrary positional arguments for '{model}:{method}'. "
                "Provide named parameters via kwargs instead.",
                details={"model": model, "method": method, "unsupported_args": args},
            )
        payload = dict(kwargs) if kwargs else {}
        return self._call(f"/json/2/{model}/{method}", payload)

    def list_modules(self, state: str = "installed") -> List[Dict[str, Any]]:
        domain = [("state", "=", state)] if state else []
        return self.search_read(
            "ir.module.module",
            domain=domain,
            fields=["id", "name", "shortdesc", "state", "installed_version"],
            limit=500,
        )
