"""Runtime Context.

Configuration and environment container for the Copilot runtime engine.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RuntimeConfig(BaseModel):
    """Runtime engine operational configuration."""

    environment: str = "development"
    debug: bool = False
    enable_audit: bool = True
    default_role: str = "general_assistant"
    options: Dict[str, Any] = Field(default_factory=dict)
