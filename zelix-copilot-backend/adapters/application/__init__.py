"""Application adapters module."""

from adapters.application.base.adapter import ApplicationAdapter
from adapters.application.mcp.adapter import MCPApplicationAdapter
from adapters.application.reference.in_memory_adapter import InMemoryApplicationAdapter
from adapters.application.rest.adapter import RESTApplicationAdapter
from adapters.application.sdk.adapter import SDKApplicationAdapter

__all__ = [
    "ApplicationAdapter",
    "InMemoryApplicationAdapter",
    "MCPApplicationAdapter",
    "RESTApplicationAdapter",
    "SDKApplicationAdapter",
]
