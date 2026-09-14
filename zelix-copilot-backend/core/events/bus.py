"""Event Bus module.

Provides pub/sub event distribution for AI Employee triggers.
"""

from collections import defaultdict
from typing import Callable, Dict, List
from core.events.interface import EmployeeEvent

EventHandler = Callable[[EmployeeEvent], None]


class EventBus:
    """Lightweight in-memory event bus for EmployeeEvents."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event type (or '*' for all events)."""
        self._subscribers[event_type].append(handler)

    def publish(self, event: EmployeeEvent) -> None:
        """Publish an event to all interested handlers."""
        # Exact match handlers
        for handler in self._subscribers.get(event.event_type, []):
            handler(event)
        
        # Wildcard match handlers
        for handler in self._subscribers.get("*", []):
            handler(event)
