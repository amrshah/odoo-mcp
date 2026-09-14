"""Voice Input Adapter."""

from typing import Any, Dict, Optional
from pydantic import BaseModel


class VoiceInput(BaseModel):
    """Encapsulates voice audio or transcribed audio input."""

    audio_bytes: Optional[bytes] = None
    audio_format: str = "wav"
    transcript: Optional[str] = None
    user_id: str
    session_id: str
    metadata: Dict[str, Any] = {}
