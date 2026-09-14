"""
core/tools/registry.py
Tool Registry for registration, lookup, and permission validation.
"""

from typing import Dict, List, Optional
from core.tools.base import BaseTool
from core.sessions.context import EmployeeContext


class ToolRegistry:
    """Registry maintaining available deterministic tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_all(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_accessible_tools(self, context: EmployeeContext) -> Dict[str, BaseTool]:
        """Returns tools the context has permission to execute."""
        accessible = {}
        for name, tool in self._tools.items():
            req_perms = tool.definition.required_permissions
            if not req_perms or any(p in context.permissions for p in req_perms) or "all" in context.permissions:
                accessible[name] = tool
        return accessible
