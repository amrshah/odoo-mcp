"""Reference application adapter module."""

from adapters.application.reference.in_memory_adapter import InMemoryApplicationAdapter
from adapters.application.reference.models import Customer, Document, Invoice, Task, User

__all__ = [
    "Customer",
    "Document",
    "InMemoryApplicationAdapter",
    "Invoice",
    "Task",
    "User",
]
