"""
FastMCP Server implementation for Alamia OdooBridge.
Exposes guarded Odoo ERP tools to AI assistants with 100% backward-compatible contracts
and strict MCP ToolError propagation on policy or adapter failures.
"""

import time
import logging
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..config import BridgeSettings, get_settings
from ..core.policies import PolicyEngine
from ..core.audit import AuditLogger
from ..core.cache import SchemaCache
from ..core.context import current_principal
from ..adapters.odoo import get_adapter

logger = logging.getLogger("alamia_odoobridge.mcp")


def create_bridge_server(settings: Optional[BridgeSettings] = None) -> FastMCP:
    """Create and configure the Alamia OdooBridge FastMCP instance."""
    cfg = settings or get_settings()
    adapter = get_adapter(cfg)
    policy = PolicyEngine(cfg)
    audit = AuditLogger(enabled=cfg.enable_audit_log)
    cache = SchemaCache(
        default_ttl=cfg.schema_cache_ttl_seconds,
        enabled=cfg.enable_schema_cache,
    )

    mcp = FastMCP("alamia-odoobridge")

    @mcp.tool()
    def odoo_status() -> Dict[str, Any]:
        """
        Check connection status and server info for the connected Odoo instance.
        Returns server version, database name, and authenticated user ID.
        """
        start = time.time()
        try:
            version_info = adapter.get_version()
            uid = adapter.authenticate()
            principal = current_principal.get()
            res = {
                "status": "connected",
                "url": cfg.odoo_url,
                "database": cfg.odoo_db,
                "user": cfg.odoo_username,
                "uid": uid,
                "server_version": version_info.get("server_version"),
                "server_version_info": version_info.get("server_version_info"),
                "protocol_version": version_info.get("protocol_version"),
                "execution_policy": cfg.execution_policy.value,
                "allow_unlink": cfg.allow_unlink,
                "schema_cache": cache.stats,
                "caller": principal.to_dict() if principal else {"sub": "service_account", "is_service_only": True},
            }
            audit.log_event("odoo_status", status="success", duration_ms=(time.time() - start) * 1000)
            return res
        except Exception as e:
            audit.log_event("odoo_status", status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            raise ToolError(f"Connection check failed: {e}")

    @mcp.tool()
    def odoo_list_models(filter_term: str = "") -> List[Dict[str, Any]]:
        """
        List available models in Odoo (e.g. res.partner, res.users, vet.patient, hms.patient).
        Filters out restricted administrative models according to security policy.
        :param filter_term: Optional keyword to filter models by name or technical identifier.
        """
        start = time.time()
        try:
            cache_key = f"models:list:{filter_term}"
            cached = cache.get(cache_key)
            if cached is not None:
                audit.log_event(
                    "odoo_list_models",
                    details={"filter_term": filter_term, "cached": True},
                    duration_ms=(time.time() - start) * 1000,
                )
                return cached

            raw_models = adapter.list_models(filter_term=filter_term)
            # Enforce authorization: sanitize and omit disallowed administrative models
            filtered_models = [
                m for m in raw_models
                if m.get("model") not in cfg.disallowed_models
            ]
            cache.set(cache_key, filtered_models)
            audit.log_event(
                "odoo_list_models",
                details={"filter_term": filter_term, "cached": False, "count": len(filtered_models)},
                duration_ms=(time.time() - start) * 1000,
            )
            return filtered_models
        except Exception as e:
            audit.log_event("odoo_list_models", status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            raise ToolError(f"Failed to list models: {e}")

    @mcp.tool()
    def odoo_get_model_fields(model: str, attributes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Inspect the schema and fields of an Odoo model.
        Returns field definitions, types, required flags, and relation targets.
        :param model: Technical model name (e.g., 'res.partner', 'crm.lead', 'vet.patient').
        :param attributes: Optional list of field attributes to fetch.
        """
        start = time.time()
        try:
            policy.check_read(model)
            attrs_key = ",".join(sorted(attributes)) if attributes else "all"
            cache_key = f"model:fields:{model}:{attrs_key}"
            cached = cache.get(cache_key)
            if cached is not None:
                audit.log_event(
                    "odoo_get_model_fields",
                    model=model,
                    details={"cached": True},
                    duration_ms=(time.time() - start) * 1000,
                )
                return cached

            res = adapter.get_model_fields(model=model, attributes=attributes)
            cache.set(cache_key, res)
            audit.log_event(
                "odoo_get_model_fields",
                model=model,
                details={"cached": False},
                duration_ms=(time.time() - start) * 1000,
            )
            return res
        except Exception as e:
            audit.log_event("odoo_get_model_fields", model=model, status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            raise ToolError(f"Failed to get fields for model '{model}': {e}")

    @mcp.tool()
    def odoo_search_read(
        model: str,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        offset: int = 0,
        limit: int = 20,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search and read records matching domain conditions in Odoo.
        :param model: Technical model name (e.g., 'res.partner', 'crm.lead', 'vet.patient').
        :param domain: Odoo domain filter list, e.g. [["is_company", "=", true]].
        :param fields: List of specific field names to return.
        :param offset: Number of records to skip (for pagination).
        :param limit: Maximum number of records to return (default 20).
        :param order: Sort criteria string, e.g. "create_date desc".
        """
        start = time.time()
        try:
            policy.check_read(model)
            res = adapter.search_read(
                model=model, domain=domain, fields=fields, offset=offset, limit=limit, order=order
            )
            audit.log_event("odoo_search_read", model=model, details={"count": len(res)}, duration_ms=(time.time() - start) * 1000)
            return res
        except Exception as e:
            audit.log_event("odoo_search_read", model=model, status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            raise ToolError(f"Failed to search_read on model '{model}': {e}")

    @mcp.tool()
    def odoo_read_records(model: str, ids: List[int], fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Read specific records by their integer IDs.
        :param model: Technical model name (e.g., 'res.partner').
        :param ids: List of record integer IDs.
        :param fields: Optional list of field names to read.
        """
        start = time.time()
        try:
            policy.check_read(model)
            res = adapter.read(model=model, ids=ids, fields=fields)
            audit.log_event("odoo_read_records", model=model, target_ids=ids, duration_ms=(time.time() - start) * 1000)
            return res
        except Exception as e:
            audit.log_event("odoo_read_records", model=model, target_ids=ids, status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            raise ToolError(f"Failed to read {model} IDs {ids}: {e}")

    @mcp.tool()
    def odoo_create_record(model: str, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new record in an Odoo model.
        :param model: Technical model name (e.g., 'res.partner', 'calendar.event', 'vet.patient').
        :param values: Dictionary containing field names and their corresponding values.
        """
        start = time.time()
        try:
            policy.check_write(model)
            record_id = adapter.create(model=model, values=values)
            audit.log_event("odoo_create_record", model=model, target_ids=[record_id], duration_ms=(time.time() - start) * 1000)
            return {"success": True, "model": model, "id": record_id}
        except Exception as e:
            audit.log_event("odoo_create_record", model=model, status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            raise ToolError(f"Failed to create record in '{model}': {e}")

    @mcp.tool()
    def odoo_write_record(model: str, ids: List[int], values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update one or more existing records in an Odoo model.
        :param model: Technical model name (e.g., 'res.partner').
        :param ids: List of record integer IDs to update.
        :param values: Dictionary containing the fields and updated values.
        """
        start = time.time()
        try:
            policy.check_write(model)
            result = adapter.write(model=model, ids=ids, values=values)
            audit.log_event("odoo_write_record", model=model, target_ids=ids, duration_ms=(time.time() - start) * 1000)
            return {"success": bool(result), "model": model, "ids": ids}
        except Exception as e:
            audit.log_event("odoo_write_record", model=model, target_ids=ids, status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            raise ToolError(f"Failed to write to '{model}' IDs {ids}: {e}")

    @mcp.tool()
    def odoo_unlink_record(model: str, ids: List[int]) -> Dict[str, Any]:
        """
        Delete one or more records from an Odoo model by ID.
        NOTE: Disabled by default for security. Requires BRIDGE_ALLOW_UNLINK=True.
        :param model: Technical model name (e.g., 'res.partner').
        :param ids: List of record integer IDs to delete.
        """
        start = time.time()
        try:
            policy.check_unlink(model=model, ids=ids)
            result = adapter.unlink(model=model, ids=ids)
            audit.log_event("odoo_unlink_record", model=model, target_ids=ids, duration_ms=(time.time() - start) * 1000)
            return {"success": bool(result), "model": model, "ids": ids}
        except Exception as e:
            audit.log_event("odoo_unlink_record", model=model, target_ids=ids, status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            raise ToolError(f"Failed to unlink '{model}' IDs {ids}: {e}")

    @mcp.tool()
    def odoo_execute_method(
        model: str,
        method: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an allowlisted business logic method on an Odoo model.
        Restricted to explicit model:method pairs in BRIDGE_ALLOWED_METHODS.
        :param model: Technical model name (e.g., 'account.move', 'sale.order').
        :param method: Business method name (e.g., 'action_post', 'action_confirm').
        :param args: Optional positional arguments list.
        :param kwargs: Optional keyword arguments dictionary.
        """
        start = time.time()
        try:
            policy.check_method_execution(model=model, method=method)
            res = adapter.execute_method(model=model, method=method, args=args, kwargs=kwargs)
            audit.log_event("odoo_execute_method", model=model, details={"method": method}, duration_ms=(time.time() - start) * 1000)
            return {"success": True, "model": model, "method": method, "result": res}
        except Exception as e:
            audit.log_event("odoo_execute_method", model=model, details={"method": method}, status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            raise ToolError(f"Failed to execute method '{model}:{method}': {e}")

    @mcp.tool()
    def odoo_list_modules(state: str = "installed") -> List[Dict[str, Any]]:
        """
        List Odoo modules to inspect installed capabilities and verify extensions.
        :param state: Module state filter ('installed', 'uninstalled', or '' for all).
        """
        start = time.time()
        try:
            policy.check_module_inspection()
            res = adapter.list_modules(state=state)
            audit.log_event("odoo_list_modules", details={"state": state, "count": len(res)}, duration_ms=(time.time() - start) * 1000)
            return res
        except Exception as e:
            audit.log_event("odoo_list_modules", status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            raise ToolError(f"Failed to list modules: {e}")

    return mcp
