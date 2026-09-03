"""
Base Workflow Engine
Implements the Observe -> Reason -> Propose (Action Card) -> Human Approval -> Execute (MCP) lifecycle.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ActionType(str, Enum):
    WRITE_ENCOUNTER = "write_encounter"
    CREATE_APPOINTMENT = "create_appointment"
    CREATE_PRESCRIPTION = "create_prescription"
    SCHEDULE_REMINDER = "schedule_reminder"
    DRAFT_CLIENT_MESSAGE = "draft_client_message"
    ORDER_DIAGNOSTIC = "order_diagnostic"


class ActionCard(BaseModel):
    action_id: str
    action_type: ActionType
    title: str
    description: str
    target_model: str
    target_method: str = "create"  # "create", "write", etc.
    payload: Dict[str, Any]
    requires_approval: bool = True
    status: str = "proposed"  # "proposed", "approved", "rejected", "executed"
    preview_data: Optional[Dict[str, Any]] = None


class WorkflowResult(BaseModel):
    workflow_id: str
    response_text: str
    action_cards: List[ActionCard] = []
    metadata: Dict[str, Any] = {}


class BaseWorkflow(ABC):
    """Abstract base class for all AI clinical workflows."""

    def __init__(self, workflow_id: str, name: str, description: str):
        self.workflow_id = workflow_id
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(
        self,
        user_input: str,
        context_prompt: str,
        active_context: Any,
        provider: Any,
    ) -> WorkflowResult:
        """Executes reasoning and generates response + proposed action cards."""
        pass
