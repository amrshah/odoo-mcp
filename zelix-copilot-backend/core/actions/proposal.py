"""Action Proposal module.

Every meaningful mutation must first become a structured ActionProposal.
Backend policies determine whether intent is permitted and whether confirmation is required.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ActionStatus(str, Enum):
    """Lifecycle states for an ActionProposal."""

    PROPOSED = "PROPOSED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class ActionProposal(BaseModel):
    """Structured proposal representing an intent to mutate system state."""

    action_id: str
    action_type: str
    idempotency_key: str
    target: Dict[str, Any]
    reason: str
    proposed_changes: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "LOW"
    required_permission: str = ""
    requires_confirmation: bool = False
    status: ActionStatus = ActionStatus.PROPOSED
    created_by: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    executed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
