"""
FastMCP Server implementation for Alamia OdooBridge.
Exposes guarded Odoo ERP tools to AI assistants with 100% backward-compatible contracts.
"""

import time
import logging
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

from ..config import BridgeSettings, get_settings
from ..core.policies import PolicyEngine
from ..core.audit import AuditLogger
from ..adapters.odoo import get_adapter

logger = logging.getLogger("alamia_odoobridge.mcp")


def create_bridge_server(settings: Optional[BridgeSettings] = None) -> FastMCP:
    """Create and configure the Alamia OdooBridge FastMCP instance."""
    cfg = settings or get_settings()
    adapter = get_adapter(cfg)
    policy = PolicyEngine(cfg)
    audit = AuditLogger(enabled=cfg.enable_audit_log)

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
            }
            audit.log_event("odoo_status", status="success", duration_ms=(time.time() - start) * 1000)
            return res
        except Exception as e:
            audit.log_event("odoo_status", status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            return {
                "status": "error",
                "url": cfg.odoo_url,
                "database": cfg.odoo_db,
                "user": cfg.odoo_username,
                "error": str(e),
            }

    @mcp.tool()
    def odoo_list_models(filter_term: str = "") -> List[Dict[str, Any]]:
        """
        List available models in Odoo (e.g. res.partner, res.users, vet.patient, hms.patient).
        :param filter_term: Optional keyword to filter models by name or technical identifier.
        """
        start = time.time()
        try:
            res = adapter.list_models(filter_term=filter_term)
            audit.log_event("odoo_list_models", details={"filter_term": filter_term}, duration_ms=(time.time() - start) * 1000)
            return res
        except Exception as e:
            audit.log_event("odoo_list_models", status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            return [{"error": f"Failed to list models: {str(e)}"}]

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
            res = adapter.get_model_fields(model=model, attributes=attributes)
            audit.log_event("odoo_get_model_fields", model=model, duration_ms=(time.time() - start) * 1000)
            return res
        except Exception as e:
            audit.log_event("odoo_get_model_fields", model=model, status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            return {"error": f"Failed to get fields for {model}: {str(e)}"}

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
            return [{"error": f"Failed to search_read on {model}: {str(e)}"}]

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
            return [{"error": f"Failed to read {model} IDs {ids}: {str(e)}"}]

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
            return {"success": False, "model": model, "error": str(e)}

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
            return {"success": False, "model": model, "ids": ids, "error": str(e)}

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
            return {"success": False, "model": model, "ids": ids, "error": str(e)}

    @mcp.tool()
    def odoo_execute_method(
        model: str,
        method: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an allowlisted business logic method on an Odoo model (e.g. action_confirm, button_validate).
        :param model: Technical model name (e.g., 'sale.order', 'vet.appointment').
        :param method: Python method name on the model.
        :param args: Positional arguments list.
        :param kwargs: Keyword arguments dictionary.
        """
        start = time.time()
        try:
            policy.check_method_execution(model=model, method=method)
            result = adapter.execute_method(model=model, method=method, args=args, kwargs=kwargs)
            audit.log_event("odoo_execute_method", model=model, details={"method": method}, duration_ms=(time.time() - start) * 1000)
            return {"success": True, "result": result}
        except Exception as e:
            audit.log_event("odoo_execute_method", model=model, details={"method": method}, status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            return {"success": False, "model": model, "method": method, "error": str(e)}

    @mcp.tool()
    def odoo_list_modules(state: str = "installed") -> List[Dict[str, Any]]:
        """
        List Odoo modules to inspect installed capabilities and verify extensions.
        :param state: Module status filter ('installed', 'uninstalled', or empty string for all).
        """
        start = time.time()
        try:
            res = adapter.list_modules(state=state)
            audit.log_event("odoo_list_modules", details={"state": state}, duration_ms=(time.time() - start) * 1000)
            return res
        except Exception as e:
            audit.log_event("odoo_list_modules", status="error", duration_ms=(time.time() - start) * 1000, error=str(e))
            return [{"error": f"Failed to list modules: {str(e)}"}]

    return mcp
