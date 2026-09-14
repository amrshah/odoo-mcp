"""
tools/veterinary/patient_tools.py
Atomic deterministic tools for patient demographics, vaccination history, and clinical encounters.
"""

from typing import Any, Dict, List, Optional
from core.tools.base import BaseTool
from core.tools.definition import ToolDefinition
from core.sessions.context import EmployeeContext
from adapters.application.base.adapter import ApplicationAdapter


class GetPatientRecordTool(BaseTool):
    """Fetches medical record, species, breed, and alerts for a patient."""

    def __init__(self, adapter: ApplicationAdapter) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_patient_record",
            description="Fetches medical record, species, breed, and alerts for a veterinary or hospital patient.",
            parameters={"patient_id": {"type": "string"}},
            required_permissions=["patients.read"],
            risk_level="LOW",
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> Optional[Dict[str, Any]]:
        patient_id = kwargs.get("patient_id")
        if not patient_id and context.active_entity:
            patient_id = context.active_entity.get("id")
        if not patient_id and "patient_context" in context.metadata:
            patient_id = context.metadata["patient_context"].get("id")
        if not patient_id and context.metadata.get("active_model") in ["vet.patient", "hms.patient"]:
            patient_id = context.metadata.get("active_record_id")

        if patient_id:
            rec = self.adapter.get("patient", str(patient_id))
            if rec:
                return rec
            rec = self.adapter.get("hms_patient", str(patient_id))
            if rec:
                return rec

        # Check natural language query for patient name
        user_input = kwargs.get("query") or context.metadata.get("user_input") or ""
        if user_input:
            import re
            m = re.search(r"(?:for|patient|patient\s+record|history\s+for|about|summary\s+of)\s+([A-Za-z0-9_-]+)", str(user_input), re.IGNORECASE)
            patient_name = m.group(1) if m else None
            if patient_name and patient_name.lower() not in ["history", "summary", "record", "the", "a", "an", "today", "yesterday", "clinical"]:
                found = self.adapter.search("patient", {"name": ("name", "ilike", patient_name)}, limit=1)
                if not found:
                    found = self.adapter.search("patient", {"identifier": ("identifier", "ilike", patient_name)}, limit=1)
                if found:
                    return found[0]

        # Check if any patient is available
        pts = self.adapter.search("patient", limit=1)
        if pts:
            return pts[0]

        return context.active_entity or context.metadata.get("patient_context")


class GetVaccinationHistoryTool(BaseTool):
    """Retrieves administered vaccinations, batch numbers, and booster due dates."""

    def __init__(self, adapter: ApplicationAdapter) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_vaccination_history",
            description="Retrieves administered vaccinations, batch numbers, and booster due dates.",
            parameters={"patient_id": {"type": "string"}},
            required_permissions=["medical_records.read"],
            risk_level="LOW",
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> List[Dict[str, Any]]:
        patient_id = kwargs.get("patient_id")
        if not patient_id and context.active_entity:
            patient_id = context.active_entity.get("id")
        if not patient_id and "patient_context" in context.metadata:
            patient_id = context.metadata["patient_context"].get("id")
        if not patient_id:
            return []
        return self.adapter.relationships("patient", str(patient_id), "vaccinations")


class GetClinicalEncountersTool(BaseTool):
    """Retrieves past clinical encounters and SOAP history."""

    def __init__(self, adapter: ApplicationAdapter) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_clinical_encounters",
            description="Retrieves past clinical encounters, SOAP notes, and chief complaints.",
            parameters={"patient_id": {"type": "string"}},
            required_permissions=["medical_records.read"],
            risk_level="LOW",
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> List[Dict[str, Any]]:
        patient_id = kwargs.get("patient_id")
        if not patient_id and context.active_entity:
            patient_id = context.active_entity.get("id")
        if not patient_id and "patient_context" in context.metadata:
            patient_id = context.metadata["patient_context"].get("id")
        if not patient_id:
            return []
        return self.adapter.relationships("patient", str(patient_id), "encounters")
