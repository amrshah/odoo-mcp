"""Session management."""

from typing import Dict, Optional
from core.sessions.context import EmployeeContext


class Session:
    """Represents a stateful copilot session."""

    def __init__(self, session_id: str, context: EmployeeContext):
        self.session_id = session_id
        self.context = context
        self.state: Dict[str, any] = {}

    def update_active_entity(self, entity_type: str, entity_id: str, data: Optional[Dict[str, any]] = None) -> None:
        """Update the currently active entity in the context."""
        self.context.active_entity = {
            "type": entity_type,
            "id": entity_id,
            "data": data or {}
        }

    def clear_active_entity(self) -> None:
        """Clear active entity context."""
        self.context.active_entity = None
