"""
tools/veterinary/inventory_tools.py
Atomic deterministic tools for pharmacy inventory, stock levels, and clinic operations census.
"""

from typing import Any, Dict, List, Optional
from core.tools.base import BaseTool
from core.tools.definition import ToolDefinition
from core.sessions.context import EmployeeContext
from adapters.application.base.adapter import ApplicationAdapter


class GetInventoryStockTool(BaseTool):
    """Queries medicine inventory stock levels, storage location, and reorder levels."""

    def __init__(self, adapter: ApplicationAdapter) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_inventory_stock",
            description="Checks available medication quantities, physical warehouse shelf locations, and reorder alerts.",
            parameters={"product_name": {"type": "string"}},
            required_permissions=["inventory.read"],
            risk_level="LOW",
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> List[Dict[str, Any]]:
        name_filter = kwargs.get("product_name")
        query = {}
        if name_filter:
            query = {"name": ["ilike", name_filter]}
        return self.adapter.search("product", query=query, limit=20)


class GetPracticeCensusTool(BaseTool):
    """Aggregates live operational census across VetCairn and Stratos HMS."""

    def __init__(self, adapter: ApplicationAdapter) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_practice_census",
            description="Retrieves live patient census, today's appointments, encounters, and staff on duty.",
            parameters={},
            required_permissions=["clinic_operations.read"],
            risk_level="LOW",
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> Dict[str, Any]:
        # If already grounded in context via session enrichment
        if "census_context" in context.metadata:
            return context.metadata["census_context"]

        vet_patients = self.adapter.search("patient", limit=100)
        vet_appts = self.adapter.search("appointment", limit=50)
        vet_encs = self.adapter.search("encounter", limit=50)
        vet_rx = self.adapter.search("prescription", query={"state": ["in", ["draft", "pending"]]}, limit=50)
        hms_patients = self.adapter.search("hms_patient", limit=100)
        hms_visits = self.adapter.search("hms_visit", limit=50)
        stock_items = self.adapter.search("product", limit=50)

        return {
            "vet_patients_count": len(vet_patients),
            "hms_patients_count": len(hms_patients),
            "total_patients": len(vet_patients) + len(hms_patients),
            "appointments_today": len(vet_appts),
            "hms_visits_today": len(hms_visits),
            "encounters_count": len(vet_encs),
            "pending_prescriptions_count": len(vet_rx),
            "stock_items_count": len(stock_items),
        }
