"""
core/tools/definition.py
Metadata definition for atomic deterministic tools.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    required_permissions: List[str] = Field(default_factory=list)
    risk_level: str = "LOW"
