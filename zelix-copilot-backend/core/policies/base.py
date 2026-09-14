"""Base Policy module.

Defines the structure of policy evaluations.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PolicyEvaluationResult(BaseModel):
    """Outcome of a policy evaluation."""

    allowed: bool
    policy_name: str
    reason: str = ""
    requires_confirmation: bool = False
    risk_level: str = "LOW"
    metadata: Dict[str, Any] = Field(default_factory=dict)
