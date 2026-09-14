"""EmployeeContext module.

Defines the working session context for an AI Employee, keeping domain concepts generic.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EmployeeContext(BaseModel):
    """Contextual state for an active employee session."""

    user_id: str
    role: str
    permissions: List[str] = Field(default_factory=list)
    active_entity: Optional[Dict[str, Any]] = None
    active_task: Optional[str] = None
    active_skill: Optional[str] = None
    pending_action: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None
    session_preferences: Dict[str, Any] = Field(default_factory=dict)
    tenant_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        """Check if the context has a specific permission or wildcard."""
        if "*" in self.permissions or "admin" in self.permissions:
            return True
        return permission in self.permissions
