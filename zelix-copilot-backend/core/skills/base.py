"""
core/skills/base.py
Abstract base class and result schema for all vertical skills.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from core.skills.definition import SkillDefinition
from core.sessions.context import EmployeeContext


class SkillResult(BaseModel):
    """Encapsulates output, synthesized response, and generated action proposals from a skill execution."""
    success: bool = True
    skill_id: str
    response_text: str = ""
    output: Dict[str, Any] = Field(default_factory=dict)
    proposed_actions: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class BaseSkill(ABC):
    """Abstract base class for vertical, domain-specific AI workflows."""

    @property
    @abstractmethod
    def definition(self) -> SkillDefinition:
        """Returns metadata definition for this skill."""
        pass

    @abstractmethod
    async def execute(
        self,
        context: EmployeeContext,
        tools: Dict[str, Any],
        ai_provider: Optional[Any] = None,
        **kwargs: Any,
    ) -> SkillResult:
        """Executes orchestrated skill workflow combining tools and AI reasoning."""
        pass
