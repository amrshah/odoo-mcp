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
    patient_summary: Optional[Dict[str, Any]] = None
    census: Optional[Dict[str, Any]] = None
    matched_rules: Optional[List[Dict[str, Any]]] = None

    class Config:
        extra = "allow"


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
        """Resolves patient ID from encounter, appointment, or direct patient record (VetCairn or HMS)."""
        if context.patient_id:
            return context.patient_id

        # Direct patient records
        if context.model in ["vet.patient", "hms.patient"] and context.record_id:
            return context.record_id

        # Veterinary encounters & appointments
        if context.model == "vet.encounter" and context.record_id:
            enc = self.client.read("vet.encounter", [context.record_id], ["patient_id"])
            if enc and enc[0].get("patient_id"):
                return enc[0]["patient_id"][0]

        if context.model == "vet.appointment" and context.record_id:
            appt = self.client.read("vet.appointment", [context.record_id], ["patient_id"])
            if appt and appt[0].get("patient_id"):
                return appt[0]["patient_id"][0]

        # HMS consultations & appointments
        if context.model == "hms.consultation" and context.record_id:
            enc = self.client.read("hms.consultation", [context.record_id], ["patient_id"])
            if enc and enc[0].get("patient_id"):
                return enc[0]["patient_id"][0]

        if context.model == "hms.appointment" and context.record_id:
            appt = self.client.read("hms.appointment", [context.record_id], ["patient_id"])
            if appt and appt[0].get("patient_id"):
                return appt[0]["patient_id"][0]

        return None

    def fetch_patient_context(self, patient_id: int, model: Optional[str] = None) -> Optional[PatientClinicalSummary]:
        """Fetches structured longitudinal patient summary from VetCairn or Stratos HMS."""
        # 1. Try vet.patient first unless explicitly hms.patient
        if model != "hms.patient":
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
                if records:
                    p = records[0]
                    encounters = self.client.search_read(
                        "vet.encounter",
                        [("patient_id", "=", patient_id)],
                        ["start_datetime", "provider_id", "chief_complaint", "assessment", "state"],
                        limit=3,
                        order="start_datetime desc"
                    )
                    prescriptions = self.client.search_read(
                        "vet.prescription",
                        [("patient_id", "=", patient_id)],
                        ["name", "medication_id", "dose", "frequency", "duration", "state"],
                        limit=3,
                        order="id desc"
                    )
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
                logger.debug(f"vet.patient read skipped/failed: {e}")

        # 2. Try hms.patient (Stratos HMS Human Hospital)
        try:
            records = self.client.read(
                "hms.patient",
                [patient_id],
                [
                    "name", "code", "gender", "age", "birthday",
                    "blood_group", "mobile", "phone", "email", "address"
                ]
            )
            if records:
                p = records[0]
                consults = self.client.search_read(
                    "hms.consultation",
                    [("patient_id", "=", patient_id)],
                    ["name", "physician_id", "chief_complaint", "diagnosis", "state", "date"],
                    limit=3,
                    order="date desc"
                )
                appts = self.client.search_read(
                    "hms.appointment",
                    [("patient_id", "=", patient_id)],
                    ["name", "physician_id", "state", "date"],
                    limit=2,
                    order="date desc"
                )
                return PatientClinicalSummary(
                    id=p["id"],
                    name=p.get("name", "Unknown"),
                    identifier=p.get("code", f"MED-{p['id']:05d}"),
                    species="Human",
                    breed=p.get("blood_group") or "Standard",
                    sex=(p.get("gender") or "Unknown").capitalize(),
                    age_or_birthdate=f"{p.get('age', '')} yrs" if p.get("age") else str(p.get("birthday") or ""),
                    microchip=None,
                    primary_owner=p.get("mobile") or p.get("email") or "Self",
                    clinic="Stratos Hospital",
                    recent_encounters=consults,
                    active_prescriptions=[],
                    upcoming_appointments=appts,
                    notes=f"Blood Group: {p.get('blood_group') or 'N/A'}, Phone: {p.get('mobile') or p.get('phone') or 'N/A'}",
                )
        except Exception as e:
            logger.debug(f"hms.patient read skipped/failed: {e}")

        return None

    def format_context_prompt(self, summary: PatientClinicalSummary, query_text: str = "") -> str:
        """Formats compact prompt string for BitNet / SLM context injection including Learned Rules and Memory."""
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

        # Query Learned Rules from Odoo if model available
        try:
            rules = self.client.search_read("zelix.ai.rule", [["active", "=", True]], ["trigger_keywords", "name", "dosage", "frequency", "duration", "reason"], limit=5)
            if rules:
                lines.append("\n--- LEARNED CLINICIAN RULES (Institutional Guidelines) ---")
                for r in rules:
                    lines.append(f"• Rule '{r.get('trigger_keywords')}': Recommend {r.get('name')} {r.get('dosage')} {r.get('frequency')} ({r.get('reason') or 'Institutional rule'})")
        except Exception:
            pass

        # Query Case Memory from Odoo if model available
        try:
            cases = self.client.search_read("zelix.case.memory", [], ["chief_complaint", "assessment", "prescription_summary"], limit=3)
            if cases:
                lines.append("\n--- INSTITUTIONAL CASE MEMORY (Past Confirmed Precedents) ---")
                for c in cases:
                    lines.append(f"• Precedent: {c.get('chief_complaint')} -> Dx: {c.get('assessment')}")
        except Exception:
            pass

        return "\n".join(lines)
