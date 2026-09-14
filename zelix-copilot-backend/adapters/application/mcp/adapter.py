"""MCP Application Adapter.

Implements ApplicationAdapter by forwarding data and action requests to an external MCP server.
Enables plug-and-play integration with Odoo MCP, Laravel MCP, FastAPI MCP, etc.
"""

import json
from typing import Any, Dict, List, Optional
from adapters.application.base.adapter import ApplicationAdapter
from adapters.application.mcp.client import MCPClient


class MCPApplicationAdapter(ApplicationAdapter):
    """Application adapter that communicates with host applications over MCP."""

    def __init__(self, mcp_client: Optional[MCPClient] = None) -> None:
        self.client = mcp_client or MCPClient()

    def identity(self, user_id: str) -> Optional[Dict[str, Any]]:
        res = self.client.call_tool("get_identity", {"user_id": user_id})
        if res.isError or not res.content:
            return None
        try:
            return json.loads(res.content[0].get("text", "{}"))
        except Exception:
            return {"user_id": user_id, "raw": res.content[0].get("text")}

    def permissions(self, user_id: str) -> List[str]:
        res = self.client.call_tool("get_permissions", {"user_id": user_id})
        if res.isError or not res.content:
            return []
        try:
            return json.loads(res.content[0].get("text", "[]"))
        except Exception:
            return []

    def search(
        self,
        entity_type: str,
        query: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        res = self.client.call_tool(f"search_{entity_type}", {"query": query or {}, "limit": limit})
        if res.isError or not res.content:
            return []
        try:
            return json.loads(res.content[0].get("text", "[]"))
        except Exception:
            return []

    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        res = self.client.call_tool(f"get_{entity_type}", {"id": entity_id})
        if res.isError or not res.content:
            return None
        try:
            return json.loads(res.content[0].get("text", "{}"))
        except Exception:
            return {"id": entity_id, "raw": res.content[0].get("text")}

    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        res = self.client.call_tool(f"create_{entity_type}", {"data": data})
        if res.isError or not res.content:
            raise RuntimeError(f"MCP creation of '{entity_type}' failed.")
        try:
            return json.loads(res.content[0].get("text", "{}"))
        except Exception:
            return data

    def update(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        res = self.client.call_tool(f"update_{entity_type}", {"id": entity_id, "data": data})
        if res.isError or not res.content:
            raise RuntimeError(f"MCP update of '{entity_type}' failed.")
        try:
            return json.loads(res.content[0].get("text", "{}"))
        except Exception:
            return data

    def delete(self, entity_type: str, entity_id: str) -> bool:
        res = self.client.call_tool(f"delete_{entity_type}", {"id": entity_id})
        return not res.isError

    def execute(
        self,
        action_type: str,
        target: Dict[str, Any],
        proposed_changes: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        res = self.client.call_tool(
            f"execute_action_{action_type}",
            {
                "target": target,
                "proposed_changes": proposed_changes,
                "metadata": metadata or {},
            },
        )
        if res.isError:
            raise RuntimeError(f"MCP action execution failed: {res.content}")
        try:
            return json.loads(res.content[0].get("text", "{}"))
        except Exception:
            return res.content[0].get("text") if res.content else {"status": "ok"}

    def relationships(
        self,
        entity_type: str,
        entity_id: str,
        relation_name: str,
    ) -> List[Dict[str, Any]]:
        res = self.client.call_tool(
            f"get_{entity_type}_relationships",
            {"id": entity_id, "relation": relation_name},
        )
        if res.isError or not res.content:
            return []
        try:
            return json.loads(res.content[0].get("text", "[]"))
        except Exception:
            return []

    def audit(self, entry: Dict[str, Any]) -> None:
        self.client.call_tool("log_audit_event", {"entry": entry})
