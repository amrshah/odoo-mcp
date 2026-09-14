"""
core/skills/registry.py
Skill Registry for registering, finding, and routing vertical skills.
"""

from typing import Dict, List, Optional
from core.skills.base import BaseSkill
from core.sessions.context import EmployeeContext


class SkillRegistry:
    """Registry maintaining available vertical domain skills."""

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.definition.id] = skill

    def get(self, skill_id: str) -> Optional[BaseSkill]:
        return self._skills.get(skill_id)

    def list_all(self) -> List[BaseSkill]:
        return list(self._skills.values())

    def get_accessible_skills(self, context: EmployeeContext) -> Dict[str, BaseSkill]:
        """Returns skills available for the caller's role."""
        accessible = {}
        for skill_id, skill in self._skills.items():
            allowed = skill.definition.allowed_roles
            if not allowed or context.role in allowed or "all" in allowed or "practice_manager" in context.role or context.role == "admin":
                accessible[skill_id] = skill
        return accessible
