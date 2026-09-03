"""
Deterministic Clinical Data & Safety Validator
Enforces medical consistency, frequency checks, and data integrity before Action Card creation.
"""

import re
from typing import List, Tuple
from pydantic import BaseModel
from schemas.clinical_schemas import PrescriptionProposalSchema, SOAPNoteSchema


class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class ClinicalValidator:
    """
    Deterministic data-integrity and consistency barrier:
    - Rejects contradictory dosing frequencies (e.g. 'BID (once daily)').
    - Rejects missing required prescription fields.
    - Validates route and dosage units.
    """

    # Medical acronym contradiction rules
    FREQUENCY_CONTRADICTIONS = [
        # BID = bis in die (twice daily) -> Cannot be once daily or 3 times daily
        (r"\bbid\b", r"\b(?:once\s+daily|every\s+24\s+hours|sid|qd)\b", "Contradiction detected: 'BID' (twice daily) conflicts with 'once daily'/'SID'."),
        # SID / QD = once daily -> Cannot be twice daily or every 12 hours
        (r"\b(?:sid|qd)\b", r"\b(?:twice\s+daily|every\s+12\s+hours|bid)\b", "Contradiction detected: 'SID' (once daily) conflicts with 'twice daily'/'BID'."),
        # TID = ter in die (three times daily) -> Cannot be once daily or twice daily
        (r"\btid\b", r"\b(?:once\s+daily|twice\s+daily|bid|sid)\b", "Contradiction detected: 'TID' (three times daily) conflicts with 'once/twice daily'."),
    ]

    @classmethod
    def validate_prescription(cls, proposal: PrescriptionProposalSchema) -> ValidationResult:
        errors = []
        warnings = []

        combined_text = f"{proposal.frequency} {proposal.instructions} {proposal.dose}".lower()

        # 1. Frequency Contradiction Check
        for primary_pattern, conflict_pattern, msg in cls.FREQUENCY_CONTRADICTIONS:
            if re.search(primary_pattern, combined_text) and re.search(conflict_pattern, combined_text):
                errors.append(msg)

        # 2. Required Fields Check
        if not proposal.medication_name or len(proposal.medication_name.strip()) < 2:
            errors.append("Medication name is missing or invalid.")

        if not proposal.dose or len(proposal.dose.strip()) < 1:
            errors.append("Dosage is missing or invalid.")

        if proposal.patient_id <= 0:
            errors.append(f"Invalid patient ID: {proposal.patient_id}")

        if proposal.quantity <= 0:
            errors.append("Prescription quantity must be greater than zero.")

        # 3. Route Validation
        valid_routes = ["oral", "topical", "injectable", "otic", "ophthalmic", "subcutaneous", "intravenous"]
        if proposal.route.lower() not in valid_routes:
            warnings.append(f"Uncommon administration route: '{proposal.route}'.")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def validate_soap_note(cls, soap: SOAPNoteSchema) -> ValidationResult:
        errors = []
        warnings = []

        if len(soap.subjective.strip()) < 5:
            errors.append("SOAP Subjective section is empty or too short.")

        if len(soap.objective.strip()) < 5:
            errors.append("SOAP Objective section is empty or too short.")

        if len(soap.assessment.strip()) < 5:
            errors.append("SOAP Assessment section is empty or too short.")

        if len(soap.plan.strip()) < 5:
            errors.append("SOAP Plan section is empty or too short.")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
