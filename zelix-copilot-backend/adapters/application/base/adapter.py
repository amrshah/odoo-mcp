"""Base Application Adapter Interface.

The Core Runtime must never directly call an application's ORM or proprietary API.
All host applications (Odoo, Laravel, FastAPI, ZelixVet, TravelOS, In-Memory) implement this contract.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ApplicationAdapter(ABC):
    """Abstract interface defining required capabilities of any host application."""

    @abstractmethod
    def identity(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve identity profile for a user."""
        pass

    @abstractmethod
    def permissions(self, user_id: str) -> List[str]:
        """Retrieve active permissions for a user."""
        pass

    @abstractmethod
    def search(
        self,
        entity_type: str,
        query: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search records of a given entity type matching criteria."""
        pass

    @abstractmethod
    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific record by entity type and ID."""
        pass

    @abstractmethod
    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new entity record."""
        pass

    @abstractmethod
    def update(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing entity record."""
        pass

    @abstractmethod
    def delete(self, entity_type: str, entity_id: str) -> bool:
        """Delete an entity record."""
        pass

    @abstractmethod
    def execute(
        self,
        action_type: str,
        target: Dict[str, Any],
        proposed_changes: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a domain-specific mutating business action."""
        pass

    @abstractmethod
    def relationships(
        self,
        entity_type: str,
        entity_id: str,
        relation_name: str,
    ) -> List[Dict[str, Any]]:
        """Fetch related entity records."""
        pass

    @abstractmethod
    def audit(self, entry: Dict[str, Any]) -> None:
        """Forward an audit entry to the host application's audit system."""
        pass
