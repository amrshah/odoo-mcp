"""AI Models and Data Contracts.

Defines vendor-neutral structures for LLM messages, routing, and tool invocations.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """Single message in a conversation context."""

    role: ChatRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ToolCallRequest(BaseModel):
    """Request by an LLM to call an external tool."""

    call_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    """Response returned from a tool execution to the LLM."""

    call_id: str
    tool_name: str
    content: str


class ChatResponse(BaseModel):
    """Standardized LLM response."""

    content: str
    tool_calls: List[ToolCallRequest] = Field(default_factory=list)
    model: str = ""
    usage: Dict[str, int] = Field(default_factory=dict)
    finish_reason: str = "stop"


class RoutingRequirements(BaseModel):
    """Requirements used by the AIModelRouter to select an optimal model/provider."""

    quality: str = "high"  # low, medium, high, max
    latency: str = "balanced"  # low, balanced
    privacy: str = "standard"  # standard, private_only, local_only
    max_cost_per_m_tokens: Optional[float] = None
    min_context_length: int = 4096
    requires_tool_calling: bool = False
    requires_structured_output: bool = False
