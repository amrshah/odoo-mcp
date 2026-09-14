"""Tool Definition module.

Defines the structure for deterministic application capabilities.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    """Metadata and schema contract for a business/domain tool."""

    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    return_schema: Optional[Dict[str, Any]] = None
    required_permissions: List[str] = Field(default_factory=list)
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    tags: List[str] = Field(default_factory=list)
