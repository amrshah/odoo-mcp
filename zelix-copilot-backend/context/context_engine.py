"""
Context Engine
Builds compact, high-signal contextual state for the AI Copilot from active Odoo records.
"""

import sys
import os
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

# Ensure odoo_client can be imported from mcp-server directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-server"))
from odoo_client import OdooClient

logger = logging.getLogger("zelix.context")


class ActiveContext(BaseModel):
    model: Optional[str] = None
    record_id: Optional[int] = None
    patient_id: Optional[int] = None
    encounter_id: Optional[int] = None
    appointment_id: Optional[int] = None
    clinic_id: Optional[int] = None
    user_uid: int = 2
    user_name: str = "Administrator"
    role: str = "veterinarian"
    patient_summary_obj: Optional[Any] = None


class PatientClinicalSummary(BaseModel):
    id: int
    name: str
    identifier: str
    species: str
    breed: str
    sex: str
    age_or_birthdate: Optional[str] = None
    microchip: Optional[str] = None
    primary_owner: Optional[str] = None
    clinic: Optional[str] = None
    recent_encounters: List[Dict[str, Any]] = []
    active_prescriptions: List[Dict[str, Any]] = []
    upcoming_appointments: List[Dict[str, Any]] = []
    recent_diagnostics: List[Dict[str, Any]] = []
    notes: Optional[str] = None


class ContextEngine:
    """Builds targeted clinical context without overflowing the LLM token budget."""

    def __init__(self, odoo_client: Optional[OdooClient] = None):
        self.client = odoo_client or OdooClient()

    def resolve_patient_id(self, context: ActiveContext) -> Optional[int]:
        """Resolves patient ID from encounter, appointment, or direct patient record."""
        if context.patient_id:
            return context.patient_id

        if context.model == "vet.patient" and context.record_id:
            return context.record_id

        if context.model == "vet.encounter" and context.record_id:
            enc = self.client.read("vet.encounter", [context.record_id], ["patient_id"])
            if enc and enc[0].get("patient_id"):
                return enc[0]["patient_id"][0]

        if context.model == "vet.appointment" and context.record_id:
            appt = self.client.read("vet.appointment", [context.record_id], ["patient_id"])
            if appt and appt[0].get("patient_id"):
                return appt[0]["patient_id"][0]

        return None

    def fetch_patient_context(self, patient_id: int) -> Optional[PatientClinicalSummary]:
        """Fetches structured longitudinal patient summary."""
        try:
            records = self.client.read(
                "vet.patient",
                [patient_id],
                [
                    "name", "identifier", "species_id", "breed_id", "sex",
                    "birthdate", "age_display", "microchip_number", "primary_owner_id",
                    "clinic_id", "notes"
                ]
            )
            if not records:
                return None

            p = records[0]

            # 1. Recent Encounters
            encounters = self.client.search_read(
                "vet.encounter",
                [("patient_id", "=", patient_id)],
                ["start_datetime", "provider_id", "chief_complaint", "assessment", "state"],
                limit=3,
                order="start_datetime desc"
            )

            # 2. Active / Recent Prescriptions
            prescriptions = self.client.search_read(
                "vet.prescription",
                [("patient_id", "=", patient_id)],
                ["name", "medication_id", "dose", "frequency", "duration", "state"],
                limit=3,
                order="id desc"
            )

            # 3. Upcoming Appointments
            appointments = self.client.search_read(
                "vet.appointment",
                [("patient_id", "=", patient_id), ("state", "!=", "cancelled")],
                ["name", "appointment_type_id", "start_datetime", "state", "reason"],
                limit=2,
                order="start_datetime desc"
            )

            return PatientClinicalSummary(
                id=p["id"],
                name=p.get("name", "Unknown"),
                identifier=p.get("identifier", f"PAT-{p['id']:05d}"),
                species=p.get("species_id", [0, "Unknown"])[1] if p.get("species_id") else "Unknown",
                breed=p.get("breed_id", [0, "Unknown"])[1] if p.get("breed_id") else "Unknown",
                sex=p.get("sex", "Unknown"),
                age_or_birthdate=p.get("age_display") or str(p.get("birthdate") or ""),
                microchip=p.get("microchip_number"),
                primary_owner=p.get("primary_owner_id", [0, "None"])[1] if p.get("primary_owner_id") else "None",
                clinic=p.get("clinic_id", [0, "None"])[1] if p.get("clinic_id") else "None",
                recent_encounters=encounters,
                active_prescriptions=prescriptions,
                upcoming_appointments=appointments,
                notes=p.get("notes"),
            )
        except Exception as e:
            logger.error(f"Error building patient context for ID {patient_id}: {e}")
            return None

    def format_context_prompt(self, summary: PatientClinicalSummary) -> str:
        """Formats compact prompt string for BitNet / SLM context injection."""
        lines = [
            f"=== PATIENT PROFILE: {summary.name} ({summary.identifier}) ===",
            f"Species: {summary.species} | Breed: {summary.breed} | Sex: {summary.sex} | Age: {summary.age_or_birthdate}",
            f"Clinic: {summary.clinic} | Primary Owner: {summary.primary_owner}",
        ]
        if summary.notes:
            lines.append(f"Clinical Notes / Allergies: {summary.notes}")

        if summary.recent_encounters:
            lines.append("\n--- RECENT ENCOUNTERS ---")
            for enc in summary.recent_encounters:
                lines.append(f"- Date: {enc.get('start_datetime')} | Reason: {enc.get('chief_complaint')} | Assessment: {enc.get('assessment')}")

        if summary.active_prescriptions:
            lines.append("\n--- RECENT PRESCRIPTIONS ---")
            for rx in summary.active_prescriptions:
                med = rx.get('medication_id', [0, rx.get('name')])[1]
                lines.append(f"- Rx: {med} ({rx.get('dose')} {rx.get('frequency')} for {rx.get('duration')}) - Status: {rx.get('state')}")

        return "\n".join(lines)
