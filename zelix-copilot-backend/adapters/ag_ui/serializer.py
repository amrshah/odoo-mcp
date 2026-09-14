"""AG-UI Protocol Serializer.

Serializes and deserializes AG-UI event frames for Server-Sent Events (SSE) and HTTP transports.
"""

import json
from typing import Any, Dict
from adapters.ag_ui.events import AGUIEvent, AGUIEventType


class AGUISerializer:
    """Encodes and decodes AG-UI SSE protocol lines."""

    @staticmethod
    def encode_sse(event: AGUIEvent) -> str:
        """Encode an AGUIEvent into an SSE-formatted chunk."""
        data_json = json.dumps(event.model_dump())
        return f"event: {event.event_type.value}\ndata: {data_json}\n\n"

    @staticmethod
    def decode_sse(raw_data: str) -> AGUIEvent:
        """Decode a raw JSON string into an AGUIEvent."""
        parsed = json.loads(raw_data)
        return AGUIEvent.model_validate(parsed)
