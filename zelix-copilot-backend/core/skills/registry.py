"""Skill Registry.

Central registry for discovering and managing business skills.
"""

from typing import Dict, List, Optional
from core.skills.base import BaseSkill


class SkillRegistry:
    """Registry of available business skills."""

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """Register a skill instance."""
        self._skills[skill.definition.id] = skill

    def get(self, skill_id: str) -> Optional[BaseSkill]:
        """Get a skill by ID."""
        return self._skills.get(skill_id)

    def list(self) -> List[BaseSkill]:
        """List all registered skills."""
        return list(self._skills.values())

    def find_for_role(self, role_id: str) -> List[BaseSkill]:
        """Find all skills permissible for a given role ID."""
        return [
            skill for skill in self._skills.values()
            if not skill.definition.allowed_roles or role_id in skill.definition.allowed_roles or "*" in skill.definition.allowed_roles
        ]

    def unregister(self, skill_id: str) -> bool:
        """Remove a skill by ID."""
        if skill_id in self._skills:
            del self._skills[skill_id]
            return True
        return False
