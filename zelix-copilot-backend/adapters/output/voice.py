"""Voice Output Adapter."""

from typing import Any, Dict, Optional
from pydantic import BaseModel


class VoiceOutput(BaseModel):
    """Encapsulates generated voice output audio stream."""

    audio_bytes: Optional[bytes] = None
    audio_format: str = "mp3"
    transcript: str = ""
    session_id: str
    metadata: Dict[str, Any] = {}
