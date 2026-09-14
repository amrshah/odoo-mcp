"""
adapters/application/base/adapter.py
Abstract base class defining the contract for enterprise ERP/database connectors.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ApplicationAdapter(ABC):
    """Abstract connector bridging Copilot Engine to host business applications (e.g. Odoo 19, Sabre, PostgreSQL)."""

    @abstractmethod
    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single record by entity type and primary key."""
        pass

    @abstractmethod
    def search(self, entity_type: str, query: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Search records matching criteria."""
        pass

    @abstractmethod
    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new record in the host application."""
        pass

    @abstractmethod
    def write(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing record in the host application."""
        pass

    @abstractmethod
    def relationships(self, entity_type: str, entity_id: str, relationship_name: str) -> List[Dict[str, Any]]:
        """Fetch related records for a given entity."""
        pass
