"""Runtime execution result models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StepResult(BaseModel):
    """Result of a single execution step (e.g. tool execution, LLM call)."""

    step_name: str
    status: str = "COMPLETED"
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    """Result of an overall Copilot / Skill execution."""

    success: bool
    skill_id: Optional[str] = None
    output: Any = None
    steps: List[StepResult] = Field(default_factory=list)
    proposed_actions: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
