"""Skill Definition module.

Defines the structure for business tasks that an AI employee performs.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    """Metadata and schema contract for an AI employee skill."""

    id: str
    name: str
    description: str
    objectives: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    allowed_roles: List[str] = Field(default_factory=list)
    version: str = "1.0.0"
