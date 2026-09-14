"""WhatsApp Input Adapter."""

from typing import Any, Dict, Optional
from pydantic import BaseModel


class WhatsAppInput(BaseModel):
    """Encapsulates incoming WhatsApp webhook message payload."""

    phone_number: str
    message_body: str
    media_url: Optional[str] = None
    user_id: str
    session_id: str
    metadata: Dict[str, Any] = {}
