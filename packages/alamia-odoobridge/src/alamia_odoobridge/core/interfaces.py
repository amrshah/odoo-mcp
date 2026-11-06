"""
Abstract interfaces for Odoo adapters.
Ensures loose coupling between MCP tool handlers and the underlying Odoo protocol.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseOdooAdapter(ABC):
    """Abstract interface defining the standardized Odoo operations contract."""

    @abstractmethod
    def authenticate(self) -> int:
        """Authenticate with Odoo and return user ID."""
        pass

    @abstractmethod
    def get_version(self) -> Dict[str, Any]:
        """Fetch Odoo server version and metadata."""
        pass

    @abstractmethod
    def list_models(self, filter_term: str = "") -> List[Dict[str, Any]]:
        """Discover models matching an optional search term."""
        pass

    @abstractmethod
    def get_model_fields(self, model: str, attributes: Optional[List[str]] = None) -> Dict[str, Any]:
        """Inspect model schema and field attributes."""
        pass

    @abstractmethod
    def search(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        offset: int = 0,
        limit: Optional[int] = 50,
        order: Optional[str] = None,
    ) -> List[int]:
        """Search for record IDs matching domain filter."""
        pass

    @abstractmethod
    def search_read(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        offset: int = 0,
        limit: int = 20,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search and read matching records."""
        pass

    @abstractmethod
    def read(self, model: str, ids: List[int], fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Read specific records by their integer IDs."""
        pass

    @abstractmethod
    def create(self, model: str, values: Dict[str, Any]) -> int:
        """Create a new record in the model."""
        pass

    @abstractmethod
    def write(self, model: str, ids: List[int], values: Dict[str, Any]) -> bool:
        """Update existing records."""
        pass

    @abstractmethod
    def unlink(self, model: str, ids: List[int]) -> bool:
        """Delete records by IDs."""
        pass

    @abstractmethod
    def execute_method(
        self,
        model: str,
        method: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a business method on a model."""
        pass

    @abstractmethod
    def list_modules(self, state: str = "installed") -> List[Dict[str, Any]]:
        """List installed or available Odoo modules."""
        pass
