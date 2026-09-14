"""Audit Logger interface.

Provides audit trail persistence and export capabilities.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from core.audit.entry import AuditEntry


class AuditLogger(ABC):
    """Abstract interface for recording and querying audit logs."""

    @abstractmethod
    def log(self, entry: AuditEntry) -> None:
        """Record an audit entry."""
        pass

    @abstractmethod
    def get_entries(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        action_id: Optional[str] = None,
    ) -> List[AuditEntry]:
        """Query recorded audit entries."""
        pass


class InMemoryAuditLogger(AuditLogger):
    """In-memory reference implementation of AuditLogger."""

    def __init__(self) -> None:
        self._entries: List[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    def get_entries(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        action_id: Optional[str] = None,
    ) -> List[AuditEntry]:
        results: List[AuditEntry] = []
        for e in self._entries:
            if event_type and e.event_type != event_type:
                continue
            if user_id and e.user_id != user_id:
                continue
            if action_id and e.action_id != action_id:
                continue
            results.append(e)
        return results
