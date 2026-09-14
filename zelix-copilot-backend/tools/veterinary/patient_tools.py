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

        if not patient_id:
            return context.active_entity or context.metadata.get("patient_context")

        # Try veterinary patient first
        rec = self.adapter.get("patient", str(patient_id))
        if rec:
            return rec
        # Try HMS patient
        return self.adapter.get("hms_patient", str(patient_id))


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
