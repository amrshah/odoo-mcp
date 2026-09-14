"""
core/actions/proposal.py
Human-in-the-Loop Action Proposal & State Machine.
"""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ActionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class ActionProposal(BaseModel):
    """Structured proposal for an external mutation requiring human confirmation or policy clearance."""
    action_id: str
    action_type: str
    idempotency_key: str
    title: Optional[str] = None
    description: Optional[str] = None
    target: Dict[str, Any] = Field(default_factory=dict)
    target_model: Optional[str] = None
    target_method: str = "create"
    reason: str
    proposed_changes: Dict[str, Any] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    required_permission: Optional[str] = None
    requires_confirmation: bool = True
    status: ActionStatus = ActionStatus.PROPOSED
    created_by: str = "copilot_engine"
    execution_result: Optional[Dict[str, Any]] = None
