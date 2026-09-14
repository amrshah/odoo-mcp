"""Web Input Adapter."""

from typing import Any, Dict
from pydantic import BaseModel


class WebInput(BaseModel):
    """Encapsulates web UI events / payload input."""

    action: str
    payload: Dict[str, Any]
    user_id: str
    session_id: str
    metadata: Dict[str, Any] = {}
