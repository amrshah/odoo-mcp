"""Audit Entry model.

Defines the structured audit log schema for operations, security checks, and tool calls.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    """Immutable audit record for compliance and tracing."""

    audit_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str  # e.g., "SKILL_EXECUTION", "ACTION_PROPOSAL", "ACTION_EXECUTION", "SECURITY_DECISION"
    user_id: Optional[str] = None
    role: Optional[str] = None
    action_id: Optional[str] = None
    skill_id: Optional[str] = None
    tool_id: Optional[str] = None
    status: str = "SUCCESS"  # SUCCESS, FAILURE, REJECTED, AWAITING_CONFIRMATION
    details: Dict[str, Any] = Field(default_factory=dict)
