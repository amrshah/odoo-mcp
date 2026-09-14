"""API Input Adapter."""

from typing import Any, Dict
from pydantic import BaseModel


class APIInput(BaseModel):
    """Encapsulates programmatic REST/RPC API input."""

    endpoint: str
    method: str = "POST"
    payload: Dict[str, Any] = {}
    user_id: str
    session_id: str
    metadata: Dict[str, Any] = {}
