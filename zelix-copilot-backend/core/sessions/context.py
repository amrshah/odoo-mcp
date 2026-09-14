"""
core/sessions/context.py
Session and Actor Execution Context for Alamia Copilot.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EmployeeContext(BaseModel):
    """Encapsulates authenticated caller identity, tenant boundaries, and active record state."""
    user_id: str = "anonymous"
    user_name: Optional[str] = None
    user_uid: Optional[int] = None
    tenant_id: str = "default"
    role: str = "veterinarian"
    role_title: Optional[str] = "Veterinarian"
    permissions: List[str] = Field(default_factory=list)
    conversation_id: Optional[str] = None
    active_model: Optional[str] = None
    active_record_id: Optional[int] = None
    patient_context: Optional[Dict[str, Any]] = None
    census_context: Optional[Dict[str, Any]] = None
    matched_rules: List[Dict[str, Any]] = Field(default_factory=list)
    client_metadata: Dict[str, Any] = Field(default_factory=dict)
