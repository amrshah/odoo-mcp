"""Role Manifest definition.

Defines standard structure for AI Employee roles.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RoleManifest(BaseModel):
    """Manifest specifying the capabilities and policies of an AI Employee role."""

    id: str
    name: str
    description: str = ""
    objectives: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    proactive_rules: List[Dict[str, Any]] = Field(default_factory=list)
    escalation_policy: Dict[str, Any] = Field(default_factory=dict)
    configuration: Dict[str, Any] = Field(default_factory=dict)
