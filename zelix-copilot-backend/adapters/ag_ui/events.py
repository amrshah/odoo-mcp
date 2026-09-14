"""AG-UI Protocol Events.

Defines vendor-neutral AG-UI event specifications for streaming, state sync, and HITL interrupts.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AGUIEventType(str, Enum):
    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"
    TEXT_DELTA = "TEXT_DELTA"
    TOOL_CALL_STARTED = "TOOL_CALL_STARTED"
    TOOL_CALL_FINISHED = "TOOL_CALL_FINISHED"
    INTERRUPT = "INTERRUPT"
    STATE_UPDATE = "STATE_UPDATE"


class AGUIEvent(BaseModel):
    """Base event payload for the AG-UI protocol."""

    event_type: AGUIEventType
    run_id: str
    thread_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None


class InterruptData(BaseModel):
    """Payload for Human-in-the-Loop interrupts."""

    interrupt_id: str
    action_proposal: Dict[str, Any]
    prompt: str
    options: List[str] = Field(default_factory=lambda: ["Approve", "Reject"])
