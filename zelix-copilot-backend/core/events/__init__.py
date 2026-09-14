"""Events module."""

from core.events.bus import EventBus, EventHandler
from core.events.interface import EmployeeEvent

__all__ = ["EmployeeEvent", "EventBus", "EventHandler"]
