"""Tool Registry.

Central registry for managing deterministic business tools.
"""

from typing import Dict, List, Optional
from core.tools.base import BaseTool


class ToolRegistry:
    """Registry of available deterministic tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list(self) -> List[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def find_by_permission(self, permission: str) -> List[BaseTool]:
        """Find tools matching a required permission."""
        return [
            tool for tool in self._tools.values()
            if permission in tool.definition.required_permissions
        ]

    def unregister(self, name: str) -> bool:
        """Remove a tool by name."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False
