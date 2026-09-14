"""Base Tool interface.

Business tools provide deterministic application capabilities and structured facts.
They must NOT secretly perform LLM reasoning.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from core.sessions.context import EmployeeContext
from core.tools.definition import ToolDefinition


class BaseTool(ABC):
    """Abstract base class for all deterministic business tools."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return the tool definition metadata."""
        pass

    @abstractmethod
    def execute(self, context: EmployeeContext, **kwargs: Any) -> Any:
        """Execute the tool deterministically against an application adapter or domain logic."""
        pass
