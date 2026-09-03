"""
Odoo FastMCP Server
Exposes Odoo CRM / ERP / Clinic / Hospital Management API as MCP Tools for AI Copilots.
"""

import os
import sys
import json
import logging
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from fastmcp import FastMCP
from odoo_client import OdooClient

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("odoo_mcp")

# Initialize FastMCP Server
mcp = FastMCP("odoo-mcp-server")
odoo = OdooClient()


@mcp.tool()
def odoo_status() -> Dict[str, Any]:
    """
    Check connection status and server info for the connected Odoo instance.
    Returns server version, database name, and authenticated user ID.
    """
    try:
        version_info = odoo.version()
        uid = odoo.authenticate()
        return {
            "status": "connected",
            "url": odoo.url,
            "database": odoo.db,
            "user": odoo.username,
            "uid": uid,
            "server_version": version_info.get("server_version"),
            "server_version_info": version_info.get("server_version_info"),
            "protocol_version": version_info.get("protocol_version"),
        }
    except Exception as e:
        return {
            "status": "error",
            "url": odoo.url,
            "database": odoo.db,
            "user": odoo.username,
            "error": str(e),
        }


@mcp.tool()
def odoo_list_models(filter_term: str = "") -> List[Dict[str, Any]]:
    """
    List available models in Odoo (e.g. res.partner, res.users, medical.patient, clinic.appointment).
    
    :param filter_term: Optional keyword to filter models by name or technical model identifier (e.g., 'partner', 'patient', 'appointment', 'sale', 'clinic').
    """
    try:
        return odoo.list_models(filter_term=filter_term)
    except Exception as e:
        return [{"error": f"Failed to list models: {str(e)}"}]


@mcp.tool()
def odoo_get_model_fields(model: str, attributes: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Inspect the schema and fields of an Odoo model.
    Returns field definitions, types (char, integer, many2one, one2many, selection, etc.), required flags, and relation targets.
    
    :param model: Technical model name (e.g., 'res.partner', 'calendar.event', 'medical.patient').
    :param attributes: Optional list of field attributes to fetch (default: ['string', 'type', 'required', 'readonly', 'relation', 'help', 'selection']).
    """
    try:
        attrs = attributes or ["string", "type", "required", "readonly", "relation", "help", "selection"]
        return odoo.get_model_fields(model=model, attributes=attrs)
    except Exception as e:
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
    
    :param model: Technical model name (e.g., 'res.partner', 'crm.lead', 'clinic.patient').
    :param domain: Odoo domain filter list, e.g. [["is_company", "=", true], ["email", "!=", false]] or [] for all.
    :param fields: List of specific field names to return. If omitted or empty, all common fields are returned.
    :param offset: Number of records to skip (for pagination).
    :param limit: Maximum number of records to return (default 20).
    :param order: Sort criteria string, e.g. "create_date desc" or "name asc".
    """
    try:
        domain = domain or []
        return odoo.search_read(
            model=model,
            domain=domain,
            fields=fields,
            offset=offset,
            limit=limit,
            order=order,
        )
    except Exception as e:
        return [{"error": f"Failed to search_read on {model}: {str(e)}"}]


@mcp.tool()
def odoo_read_records(model: str, ids: List[int], fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Read specific records by their integer IDs.
    
    :param model: Technical model name (e.g., 'res.partner').
    :param ids: List of record integer IDs.
    :param fields: Optional list of field names to read.
    """
    try:
        return odoo.read(model=model, ids=ids, fields=fields)
    except Exception as e:
        return [{"error": f"Failed to read {model} IDs {ids}: {str(e)}"}]


@mcp.tool()
def odoo_create_record(model: str, values: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new record in an Odoo model.
    
    :param model: Technical model name (e.g., 'res.partner', 'calendar.event', 'medical.patient').
    :param values: Dictionary containing field names and their corresponding values.
    """
    try:
        record_id = odoo.create(model=model, values=values)
        return {"success": True, "model": model, "id": record_id}
    except Exception as e:
        return {"success": False, "model": model, "error": str(e)}


@mcp.tool()
def odoo_write_record(model: str, ids: List[int], values: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update one or more existing records in an Odoo model.
    
    :param model: Technical model name (e.g., 'res.partner').
    :param ids: List of record integer IDs to update.
    :param values: Dictionary containing the fields and updated values.
    """
    try:
        result = odoo.write(model=model, ids=ids, values=values)
        return {"success": bool(result), "model": model, "ids": ids}
    except Exception as e:
        return {"success": False, "model": model, "ids": ids, "error": str(e)}


@mcp.tool()
def odoo_unlink_record(model: str, ids: List[int]) -> Dict[str, Any]:
    """
    Delete one or more records from an Odoo model by ID.
    
    :param model: Technical model name (e.g., 'res.partner').
    :param ids: List of record integer IDs to delete.
    """
    try:
        result = odoo.unlink(model=model, ids=ids)
        return {"success": bool(result), "model": model, "ids": ids}
    except Exception as e:
        return {"success": False, "model": model, "ids": ids, "error": str(e)}


@mcp.tool()
def odoo_execute_method(
    model: str,
    method: str,
    args: Optional[List[Any]] = None,
    kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Execute any custom or business logic method on an Odoo model (e.g. action_confirm, button_validate).
    
    :param model: Technical model name (e.g., 'sale.order', 'clinic.appointment').
    :param method: Python method name on the model.
    :param args: Positional arguments list (e.g. [[record_id]]).
    :param kwargs: Keyword arguments dictionary.
    """
    try:
        args = args or []
        kwargs = kwargs or {}
        result = odoo.execute_kw(model=model, method=method, args=args, kwargs=kwargs)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "model": model, "method": method, "error": str(e)}


@mcp.tool()
def odoo_list_modules(state: str = "installed") -> List[Dict[str, Any]]:
    """
    List Odoo modules to inspect installed capabilities and verify medical/hospital extensions.
    
    :param state: Module status filter ('installed', 'uninstalled', 'to upgrade', or empty string for all).
    """
    try:
        return odoo.list_modules(state=state)
    except Exception as e:
        return [{"error": f"Failed to list modules: {str(e)}"}]


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if len(sys.argv) > 1:
        if "--sse" in sys.argv or sys.argv[1] == "sse":
            transport = "sse"
        elif "--stdio" in sys.argv or sys.argv[1] == "stdio":
            transport = "stdio"

    logger.info(f"Starting Odoo MCP Server with transport: {transport}")
    
    if transport == "sse":
        host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_SERVER_PORT", "8008"))
        logger.info(f"Serving SSE on http://{host}:{port}/sse")
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run(transport="stdio")
