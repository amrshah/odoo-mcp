"""MCP Client Implementation.

Provides client-side transport communication with external MCP servers over JSON-RPC.
"""

from typing import Any, Callable, Dict, List, Optional
from adapters.application.mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    MCPTool,
    MCPToolCallResult,
)


class MCPClient:
    """Client for communicating with an MCP server."""

    def __init__(self, transport_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> None:
        self.transport_handler = transport_handler or self._mock_transport
        self._request_counter = 0

    def _mock_transport(self, request_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Default fallback mock transport."""
        req_id = request_dict.get("id", 1)
        method = request_dict.get("method", "")
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {"name": "mcp_get_customer", "description": "Fetch customer", "inputSchema": {}},
                        {"name": "mcp_search_invoices", "description": "Search invoices", "inputSchema": {}},
                    ]
                },
            }
        elif method == "tools/call":
            params = request_dict.get("params", {})
            name = params.get("name", "")
            args = params.get("arguments", {})
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Result for {name} with args {args}"}],
                    "isError": False,
                },
            }
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolCallResult:
        """Invoke a tool over MCP tools/call."""
        self._request_counter += 1
        req = JSONRPCRequest(
            id=self._request_counter,
            method="tools/call",
            params={"name": tool_name, "arguments": arguments},
        )
        raw_resp = self.transport_handler(req.model_dump())
        resp = JSONRPCResponse.model_validate(raw_resp)
        if resp.error:
            return MCPToolCallResult(
                content=[{"type": "text", "text": str(resp.error)}],
                isError=True,
            )
        res_data = resp.result or {}
        return MCPToolCallResult(
            content=res_data.get("content", []),
            isError=res_data.get("isError", False),
        )

    def list_tools(self) -> List[MCPTool]:
        """Discover tools exposed by the MCP server."""
        self._request_counter += 1
        req = JSONRPCRequest(
            id=self._request_counter,
            method="tools/list",
            params={},
        )
        raw_resp = self.transport_handler(req.model_dump())
        resp = JSONRPCResponse.model_validate(raw_resp)
        if resp.error or not resp.result:
            return []
        tools_data = resp.result.get("tools", [])
        return [MCPTool.model_validate(t) for t in tools_data]
