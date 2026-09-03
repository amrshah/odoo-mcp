"""
Typed Clinical Output Contracts & Schemas
Every AI workflow must return a validated Pydantic contract before downstream action execution.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# W02: Pre-Consultation Briefing Schema
# -------------------------------------------------------------------
class OdooAuthoritativeFacts(BaseModel):
    patient_id: int
    patient_name: str
    species: str
    breed: str
    sex: str
    age: Optional[str] = "unknown"
    clinic_name: Optional[str] = None
    primary_owner: Optional[str] = None
    known_allergies_or_notes: Optional[str] = None


class PreConsultBriefSchema(BaseModel):
    odoo_facts: OdooAuthoritativeFacts
    recent_encounter_history: List[str] = Field(
        default_factory=list,
        description="Factual summary of past encounters retrieved directly from Odoo."
    )
    active_medications: List[str] = Field(
        default_factory=list,
        description="Factual active prescriptions retrieved directly from Odoo."
    )
    pending_items: List[str] = Field(
        default_factory=list,
        description="Pending lab orders or unconfirmed appointments."
    )
    suggested_checks: List[str] = Field(
        default_factory=list,
        description="Actionable verification checklist for the veterinarian during today's visit."
    )


# -------------------------------------------------------------------
# W04: SOAP Note Schema
# -------------------------------------------------------------------
class ExtractedEntities(BaseModel):
    primary_diagnosis: Optional[str] = None
    medications_mentioned: List[str] = Field(default_factory=list)
    follow_up_days: Optional[int] = None
    dietary_instructions: Optional[str] = None


class SOAPNoteSchema(BaseModel):
    subjective: str = Field(..., min_length=5, description="Client complaint, history, duration.")
    objective: str = Field(..., min_length=5, description="Physical exam findings, vitals, temperature.")
    assessment: str = Field(..., min_length=5, description="Primary clinical assessment and differential diagnosis.")
    plan: str = Field(..., min_length=5, description="Medications, diagnostics, diet, and follow-up.")
    extracted_entities: ExtractedEntities = Field(default_factory=ExtractedEntities)


# -------------------------------------------------------------------
# W09: Prescription Proposal Schema
# -------------------------------------------------------------------
class PrescriptionProposalSchema(BaseModel):
    medication_name: str = Field(..., min_length=2)
    medication_id: int
    patient_id: int
    clinic_id: int = 3
    prescriber_id: int = 2
    dose: str = Field(..., description="e.g., '250mg', '16mg'")
    route: str = Field(default="oral", description="oral, topical, injectable, otic, ophthalmic")
    frequency: str = Field(..., description="e.g., 'BID (Twice Daily)', 'SID (Once Daily)'")
    duration: str = Field(..., description="e.g., '7 days', '14 days'")
    quantity: float = Field(default=1.0, ge=0.1)
    quantity_unit: str = Field(default="tablets", description="tablets, capsules, ml")
    instructions: str = Field(..., min_length=5, description="Administration instructions e.g. with food.")
    clinical_indication: str = Field(..., min_length=3, description="Reason for prescription.")
    safety_warnings: Optional[str] = None
