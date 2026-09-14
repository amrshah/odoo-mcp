"""Text Input Adapter."""

from typing import Any, Dict
from pydantic import BaseModel


class TextInput(BaseModel):
    """Encapsulates plain text user input."""

    text: str
    user_id: str
    session_id: str
    metadata: Dict[str, Any] = {}
