"""
core/tools/base.py
Abstract base class for all deterministic domain tools.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from core.tools.definition import ToolDefinition
from core.sessions.context import EmployeeContext


class BaseTool(ABC):
    """Abstract base class for atomic, deterministic tools."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Returns tool metadata and schema."""
        pass

    @abstractmethod
    def execute(self, context: EmployeeContext, **kwargs: Any) -> Any:
        """Executes tool logic deterministically."""
        pass
