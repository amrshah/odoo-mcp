"""API Response Output Adapter."""

from typing import Any, Dict
from pydantic import BaseModel


class APIResponse(BaseModel):
    """Encapsulates programmatic response payload."""

    status_code: int = 200
    data: Any = None
    session_id: str
    metadata: Dict[str, Any] = {}
