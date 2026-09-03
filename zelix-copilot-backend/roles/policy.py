"""
Role Policy & Authorization Engine
Enforces role-aware intelligence boundaries based on Odoo user security groups.
"""

from enum import Enum
from typing import Dict, List, Optional, Set
from pydantic import BaseModel


class ClinicalRole(str, Enum):
    VETERINARIAN = "veterinarian"
    TECHNICIAN = "technician"
    RECEPTIONIST = "receptionist"
    PRACTICE_MANAGER = "practice_manager"
    ADMINISTRATOR = "administrator"
    UNKNOWN = "unknown"


class RoleCapability(BaseModel):
    role: ClinicalRole
    allowed_models: List[str]
    allowed_actions: List[str]
    can_draft_prescriptions: bool = False
    can_approve_prescriptions: bool = False
    can_edit_clinical_notes: bool = False
    can_manage_appointments: bool = True
    can_view_financials: bool = False


# Canonical Role Policy Matrix
ROLE_POLICIES: Dict[ClinicalRole, RoleCapability] = {
    ClinicalRole.VETERINARIAN: RoleCapability(
        role=ClinicalRole.VETERINARIAN,
        allowed_models=[
            "vet.patient", "vet.appointment", "vet.encounter", "vet.prescription",
            "vet.vaccination", "vet.treatment.plan", "vet.diagnostic.order",
            "vet.medication", "vet.diagnosis", "res.partner"
        ],
        allowed_actions=[
            "generate_soap", "summarize_patient", "prepare_preconsult",
            "propose_prescription", "propose_treatment_plan", "propose_followup",
            "order_diagnostics", "query_records"
        ],
        can_draft_prescriptions=True,
        can_approve_prescriptions=True,
        can_edit_clinical_notes=True,
        can_manage_appointments=True,
        can_view_financials=False,
    ),
    ClinicalRole.TECHNICIAN: RoleCapability(
        role=ClinicalRole.TECHNICIAN,
        allowed_models=[
            "vet.patient", "vet.appointment", "vet.encounter", "vet.treatment.plan",
            "vet.treatment.line", "vet.vaccination", "vet.task", "vet.admission", "vet.ward"
        ],
        allowed_actions=[
            "record_vitals", "log_medication_administration", "update_treatment_task",
            "summarize_patient", "query_records"
        ],
        can_draft_prescriptions=False,
        can_approve_prescriptions=False,
        can_edit_clinical_notes=False,
        can_manage_appointments=True,
        can_view_financials=False,
    ),
    ClinicalRole.RECEPTIONIST: RoleCapability(
        role=ClinicalRole.RECEPTIONIST,
        allowed_models=[
            "vet.patient", "vet.appointment", "vet.reminder", "vet.communication",
            "res.partner"
        ],
        allowed_actions=[
            "book_appointment", "reschedule_appointment", "send_reminder",
            "draft_client_message", "query_records"
        ],
        can_draft_prescriptions=False,
        can_approve_prescriptions=False,
        can_edit_clinical_notes=False,
        can_manage_appointments=True,
        can_view_financials=False,
    ),
    ClinicalRole.PRACTICE_MANAGER: RoleCapability(
        role=ClinicalRole.PRACTICE_MANAGER,
        allowed_models=[
            "vet.patient", "vet.appointment", "vet.dashboard", "vet.clinic",
            "res.partner", "account.move"
        ],
        allowed_actions=[
            "generate_daily_brief", "view_clinic_kpis", "manage_staff_schedule",
            "query_records"
        ],
        can_draft_prescriptions=False,
        can_approve_prescriptions=False,
        can_edit_clinical_notes=False,
        can_manage_appointments=True,
        can_view_financials=True,
    ),
    ClinicalRole.ADMINISTRATOR: RoleCapability(
        role=ClinicalRole.ADMINISTRATOR,
        allowed_models=["*"],
        allowed_actions=["*"],
        can_draft_prescriptions=True,
        can_approve_prescriptions=True,
        can_edit_clinical_notes=True,
        can_manage_appointments=True,
        can_view_financials=True,
    ),
}


class RoleResolver:
    """Resolves Odoo user security groups into normalized Clinical Roles."""

    @staticmethod
    def resolve_role_from_groups(group_names: List[str]) -> ClinicalRole:
        lower_groups = [g.lower() for g in group_names]
        if any("admin" in g or "manager" in g for g in lower_groups):
            return ClinicalRole.ADMINISTRATOR
        if any("vet" in g or "doctor" in g or "clinician" in g for g in lower_groups):
            return ClinicalRole.VETERINARIAN
        if any("nurse" in g or "technician" in g for g in lower_groups):
            return ClinicalRole.TECHNICIAN
        if any("reception" in g or "frontdesk" in g for g in lower_groups):
            return ClinicalRole.RECEPTIONIST
        # Default fallback: Veterinarian with safe guardrails
        return ClinicalRole.VETERINARIAN

    @staticmethod
    def get_policy(role: ClinicalRole) -> RoleCapability:
        return ROLE_POLICIES.get(role, ROLE_POLICIES[ClinicalRole.VETERINARIAN])
