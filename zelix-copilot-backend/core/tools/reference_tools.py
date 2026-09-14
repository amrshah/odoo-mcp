"""Reference Business Tools.

Deterministic tools that interface with ApplicationAdapters to return structured facts.
"""

from typing import Any, Dict, List, Optional
from core.sessions.context import EmployeeContext
from core.tools.base import BaseTool
from core.tools.definition import ToolDefinition


class GetCustomerTool(BaseTool):
    """Tool to fetch customer data by ID."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_customer",
            description="Fetches customer profile by ID.",
            parameters={"customer_id": {"type": "string"}},
            required_permissions=["customers.read"],
            risk_level="LOW",
            tags=["customer", "crm"],
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> Optional[Dict[str, Any]]:
        customer_id = kwargs.get("customer_id")
        if not customer_id:
            return None
        return self.adapter.get("customer", customer_id)


class GetCustomerInvoicesTool(BaseTool):
    """Tool to fetch invoices for a customer."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_customer_invoices",
            description="Fetches all invoices for a given customer ID.",
            parameters={"customer_id": {"type": "string"}},
            required_permissions=["invoices.read"],
            risk_level="LOW",
            tags=["invoice", "finance"],
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> List[Dict[str, Any]]:
        customer_id = kwargs.get("customer_id")
        if not customer_id:
            return []
        return self.adapter.relationships("customer", customer_id, "invoices")


class GetCustomerTasksTool(BaseTool):
    """Tool to fetch tasks associated with a customer."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_customer_tasks",
            description="Fetches all tasks associated with a customer ID.",
            parameters={"customer_id": {"type": "string"}},
            required_permissions=["tasks.read"],
            risk_level="LOW",
            tags=["task", "operations"],
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> List[Dict[str, Any]]:
        customer_id = kwargs.get("customer_id")
        if not customer_id:
            return []
        return self.adapter.relationships("customer", customer_id, "tasks")


class GetWorkItemsTool(BaseTool):
    """Tool to fetch active work items / tasks."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_work_items",
            description="Fetches active tasks and work items across the system.",
            parameters={},
            required_permissions=["tasks.read"],
            risk_level="LOW",
            tags=["task", "briefing"],
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> List[Dict[str, Any]]:
        return self.adapter.search("task", {})
