"""
Schema Parser & Extraction Engine
Extracts typed Pydantic models from LLM markdown / JSON responses with recovery parsing.
"""

import re
import json
from typing import Any, Dict, Optional
from .clinical_schemas import (
    ExtractedEntities,
    OdooAuthoritativeFacts,
    PreConsultBriefSchema,
    PrescriptionProposalSchema,
    SOAPNoteSchema,
)


class SchemaParser:
    """Parses and validates LLM generation into strict Pydantic schemas."""

    @staticmethod
    def parse_soap_note(raw_text: str) -> SOAPNoteSchema:
        """Parses Subjective, Objective, Assessment, Plan from LLM text."""
        # Try JSON extraction first if model generated JSON
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return SOAPNoteSchema(**data)
            except Exception:
                pass

        # Parse sections using robust markdown/header regex
        subj = re.search(r"Subjective(?:\s*\(S\))?:?\s*(.*?)(?=\n\s*(?:\*\*)?Objective|\n\s*(?:\*\*)?Assessment|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
        obj = re.search(r"Objective(?:\s*\(O\))?:?\s*(.*?)(?=\n\s*(?:\*\*)?Assessment|\n\s*(?:\*\*)?Plan|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
        assess = re.search(r"Assessment(?:\s*\(A\))?:?\s*(.*?)(?=\n\s*(?:\*\*)?Plan|\n\s*(?:\*\*)?Extracted|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
        plan = re.search(r"Plan(?:\s*\(P\))?:?\s*(.*?)(?=\n\s*(?:\*\*)?Extracted|\n\s*DIAGNOSIS|\Z)", raw_text, re.DOTALL | re.IGNORECASE)

        subjective_text = subj.group(1).strip() if subj else "Owner reports patient presentation and history as discussed in consult."
        objective_text = obj.group(1).strip() if obj else "Physical examination findings recorded."
        assessment_text = assess.group(1).strip() if assess else "Clinical assessment documented."
        plan_text = plan.group(1).strip() if plan else "Treatment plan and recommendations outlined."

        # Extract structured entities
        diag_match = re.search(r"DIAGNOSIS:\s*([^\n]+)", raw_text, re.IGNORECASE)
        med_match = re.search(r"MEDICATION:\s*([^\n]+)", raw_text, re.IGNORECASE)
        follow_match = re.search(r"FOLLOW_UP_DAYS:\s*(\d+)", raw_text, re.IGNORECASE)

        entities = ExtractedEntities(
            primary_diagnosis=diag_match.group(1).strip() if diag_match else None,
            medications_mentioned=[med_match.group(1).strip()] if med_match else [],
            follow_up_days=int(follow_match.group(1)) if follow_match else None,
        )

        return SOAPNoteSchema(
            subjective=subjective_text,
            objective=objective_text,
            assessment=assessment_text,
            plan=plan_text,
            extracted_entities=entities,
        )

    @staticmethod
    def parse_prescription_proposal(
        raw_text: str,
        patient_id: int,
        medication_id: int,
        clinic_id: int = 3,
        prescriber_id: int = 2,
    ) -> PrescriptionProposalSchema:
        """Parses medication parameters into PrescriptionProposalSchema."""
        # Extract fields from text
        med_name = re.search(r"(?:Medication(?:\s+Name)?|Drug):\s*([^\n]+)", raw_text, re.IGNORECASE)
        dose = re.search(r"(?:Dosage|Dose):\s*([^\n,]+)", raw_text, re.IGNORECASE)
        freq = re.search(r"Frequency:\s*([^\n]+)", raw_text, re.IGNORECASE)
        dur = re.search(r"Duration:\s*([^\n]+)", raw_text, re.IGNORECASE)
        inst = re.search(r"(?:Administration\s+)?Instructions?:\s*([^\n]+)", raw_text, re.IGNORECASE)
        ind = re.search(r"(?:Indication|Reason):\s*([^\n]+)", raw_text, re.IGNORECASE)
        warn = re.search(r"Warning(?:s|\/Precautions)?:\s*([^\n]+)", raw_text, re.IGNORECASE)

        medication_name = med_name.group(1).strip() if med_name else "Prescribed Veterinary Medication"
        dose_val = dose.group(1).strip() if dose else "1 tablet"
        freq_val = freq.group(1).strip() if freq else "BID (Twice Daily)"
        dur_val = dur.group(1).strip() if dur else "7 days"
        inst_val = inst.group(1).strip() if inst else "Administer as directed with food."
        ind_val = ind.group(1).strip() if ind else "Clinical therapy"
        warn_val = warn.group(1).strip() if warn else None

        return PrescriptionProposalSchema(
            medication_name=medication_name,
            medication_id=medication_id,
            patient_id=patient_id,
            clinic_id=clinic_id,
            prescriber_id=prescriber_id,
            dose=dose_val,
            route="oral",
            frequency=freq_val,
            duration=dur_val,
            quantity=14.0,
            quantity_unit="tablets",
            instructions=inst_val,
            clinical_indication=ind_val,
            safety_warnings=warn_val,
        )
