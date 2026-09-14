"""Base Skill interface.

Skills coordinate context, deterministic tools, reasoning, and action proposals.
Skills must NOT directly depend on application framework APIs.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from core.sessions.context import EmployeeContext
from core.skills.definition import SkillDefinition


class SkillResult(BaseModel):
    """Structured result returned by a skill execution."""

    success: bool
    skill_id: str
    output: Any = None
    proposed_actions: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseSkill(ABC):
    """Abstract base class for all business skills."""

    @property
    @abstractmethod
    def definition(self) -> SkillDefinition:
        """Return the skill definition metadata."""
        pass

    @abstractmethod
    def execute(
        self,
        context: EmployeeContext,
        tools: Dict[str, Any],
        ai_provider: Optional[Any] = None,
        **kwargs: Any
    ) -> SkillResult:
        """Execute the business skill workflow."""
        pass
