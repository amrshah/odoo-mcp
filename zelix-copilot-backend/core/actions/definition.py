"""Action Definition module.

Defines the structure and backend constraints for executable business mutations.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ActionDefinition(BaseModel):
    """Authoritative backend definition for an executable action type."""

    action_type: str
    description: str
    target_type: str
    required_permission: str
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    requires_confirmation: bool = False
    input_schema: Dict[str, Any] = Field(default_factory=dict)
