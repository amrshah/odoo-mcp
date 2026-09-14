"""Text Output Adapter."""

from typing import Any, Dict
from pydantic import BaseModel


class TextOutput(BaseModel):
    """Encapsulates plain text copilot output."""

    text: str
    session_id: str
    metadata: Dict[str, Any] = {}
