"""
core/skills/definition.py
Metadata definition for vertical domain skills.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    id: str
    name: str
    description: str
    required_tools: List[str] = Field(default_factory=list)
    risk_level: str = "LOW"
    allowed_roles: List[str] = Field(default_factory=list)
