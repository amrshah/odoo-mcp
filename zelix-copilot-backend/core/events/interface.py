"""Employee Event module.

Defines the structure for events and triggers within the AI employee system.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EmployeeEvent(BaseModel):
    """Event emitted across the copilot runtime and application boundary."""

    event_id: str
    event_type: str
    source: str
    record_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    severity: str = "INFO"  # INFO, WARNING, ERROR, CRITICAL
    affected_roles: List[str] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
