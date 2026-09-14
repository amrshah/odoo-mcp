"""Model Context Protocol (MCP) Message Contracts.

Defines JSON-RPC 2.0 schemas for tools/list, tools/call, resources/read, and prompts.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 Request."""

    jsonrpc: str = "2.0"
    id: Union[str, int]
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 Response."""

    jsonrpc: str = "2.0"
    id: Union[str, int]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class MCPTool(BaseModel):
    """Tool schema discovered via tools/list."""

    name: str
    description: str
    inputSchema: Dict[str, Any] = Field(default_factory=dict)


class MCPToolCallResult(BaseModel):
    """Result of tools/call invocation."""

    content: List[Dict[str, Any]] = Field(default_factory=list)
    isError: bool = False
