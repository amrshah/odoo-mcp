"""Generic Reference Models.

Platform-neutral business entity definitions: User, Customer, Task, Document, Invoice.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class User(BaseModel):
    id: str
    name: str
    email: str
    role: str
    permissions: List[str] = Field(default_factory=list)


class Customer(BaseModel):
    id: str
    name: str
    email: str
    phone: str = ""
    status: str = "active"
    tier: str = "standard"
    balance: float = 0.0
    tags: List[str] = Field(default_factory=list)


class Task(BaseModel):
    id: str
    title: str
    description: str = ""
    assigned_to: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed, cancelled
    due_date: Optional[str] = None
    priority: str = "medium"


class Document(BaseModel):
    id: str
    title: str
    content: str
    doc_type: str = "general"
    tags: List[str] = Field(default_factory=list)


class Invoice(BaseModel):
    id: str
    customer_id: str
    amount: float
    status: str = "draft"  # draft, sent, paid, overdue, cancelled
    due_date: Optional[str] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)
