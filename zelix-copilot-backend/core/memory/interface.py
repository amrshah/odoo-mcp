"""Memory Interface.

Provider-neutral typed memory interface with in-memory reference implementation.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from core.memory.types import MemoryType


class MemoryRecord(BaseModel):
    """A single persistent memory record."""

    id: str
    type: MemoryType
    content: str
    source: str
    scope: str = "global"  # e.g., user_123, session_abc, tenant_xyz
    confidence: float = 1.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryInterface(ABC):
    """Abstract interface for memory persistence and retrieval."""

    @abstractmethod
    def store(self, record: MemoryRecord) -> None:
        """Store a memory record."""
        pass

    @abstractmethod
    def retrieve(self, record_id: str) -> Optional[MemoryRecord]:
        """Retrieve a memory record by ID."""
        pass

    @abstractmethod
    def search(
        self,
        scope: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        query: Optional[str] = None,
    ) -> List[MemoryRecord]:
        """Search stored memory records."""
        pass

    @abstractmethod
    def delete(self, record_id: str) -> bool:
        """Delete a memory record by ID."""
        pass


class InMemoryMemoryStore(MemoryInterface):
    """In-memory reference implementation of MemoryInterface."""

    def __init__(self) -> None:
        self._records: Dict[str, MemoryRecord] = {}

    def store(self, record: MemoryRecord) -> None:
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self._records[record.id] = record

    def retrieve(self, record_id: str) -> Optional[MemoryRecord]:
        return self._records.get(record_id)

    def search(
        self,
        scope: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        query: Optional[str] = None,
    ) -> List[MemoryRecord]:
        results: List[MemoryRecord] = []
        for r in self._records.values():
            if scope and r.scope != scope:
                continue
            if memory_type and r.type != memory_type:
                continue
            if query and query.lower() not in r.content.lower():
                continue
            results.append(r)
        return results

    def delete(self, record_id: str) -> bool:
        if record_id in self._records:
            del self._records[record_id]
            return True
        return False
