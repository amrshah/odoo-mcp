"""
Workflow W03 / W04: Ambient Consultation Scribe & Structured SOAP Generator
Uses strict typed schema validation and clinical consistency checks.
"""

import uuid
from typing import Any, List
from schemas.parser import SchemaParser
from validators.clinical_validator import ClinicalValidator
from .base_workflow import ActionCard, ActionType, BaseWorkflow, WorkflowResult


class AmbientScribeSOAPWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__(
            workflow_id="w04_scribe_soap",
            name="Ambient Consultation Scribe & SOAP Note Generator",
            description="Converts clinical consultation transcripts or dictated notes into formal SOAP documentation and proposed Odoo writes.",
        )

    async def execute(
        self,
        user_input: str,
        context_prompt: str,
        active_context: Any,
        provider: Any,
    ) -> WorkflowResult:
        system_prompt = f"""You are Zelix AI Clinical Scribe for veterinary medicine.
Analyze the consultation transcript and generate a structured SOAP note.

{context_prompt}

OUTPUT FORMAT:
Subjective: <Patient complaints, history from owner, onset duration>
Objective: <Physical exam findings, vitals, temperature, palpation>
Assessment: <Primary clinical assessment / differential diagnosis>
Plan: <Therapy, medications, diet, and follow-up plan>

DIAGNOSIS: <primary clinical diagnosis>
MEDICATION: <medication details if prescribed, or None>
FOLLOW_UP_DAYS: <number of days e.g. 4, or None>
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Consultation transcript / clinical findings:\n\n{user_input}"},
        ]

        result = await provider.chat_complete(
            messages=messages,
            temperature=0.1,
            max_tokens=400,
        )

        # 1. Parse into Typed Pydantic Schema
        soap_schema = SchemaParser.parse_soap_note(result.content)

        # 2. Run Deterministic Clinical Validation
        validation = ClinicalValidator.validate_soap_note(soap_schema)
        if not validation.is_valid:
            return WorkflowResult(
                workflow_id=self.workflow_id,
                response_text=f"Validation Failed: {', '.join(validation.errors)}",
                action_cards=[],
                metadata={"validation_errors": validation.errors},
            )

        # 3. Build Action Cards for Human Approval
        patient_id = getattr(active_context, "patient_id", None) or 3
        encounter_id = getattr(active_context, "encounter_id", None)
        appointment_id = getattr(active_context, "appointment_id", None) or 6

        payload_dict = {
            "patient_id": patient_id,
            "appointment_id": appointment_id,
            "chief_complaint": soap_schema.extracted_entities.primary_diagnosis or "Consultation exam",
            "triage_priority": "routine",
            "subjective": soap_schema.subjective,
            "objective": soap_schema.objective,
            "assessment": soap_schema.assessment,
            "plan": soap_schema.plan,
            "state": "completed",
        }
        if encounter_id:
            payload_dict["id"] = encounter_id

        action_cards: List[ActionCard] = [
            ActionCard(
                action_id=f"act_soap_{uuid.uuid4().hex[:8]}",
                action_type=ActionType.WRITE_ENCOUNTER,
                title="Save Clinical Encounter SOAP Note",
                description=f"Save validated SOAP note to clinical encounter for Patient ID #{patient_id}",
                target_model="vet.encounter",
                target_method="write" if encounter_id else "create",
                payload=payload_dict,
                requires_approval=True,
                preview_data={"soap_schema": soap_schema.model_dump(), "id": encounter_id},
            )
        ]

        # Follow-up Action Card if indicated
        if soap_schema.extracted_entities.follow_up_days:
            days = soap_schema.extracted_entities.follow_up_days
            action_cards.append(
                ActionCard(
                    action_id=f"act_followup_{uuid.uuid4().hex[:8]}",
                    action_type=ActionType.CREATE_APPOINTMENT,
                    title=f"Schedule Clinical Follow-up ({days} days)",
                    description=f"Auto-schedule follow-up visit in {days} days for treatment re-evaluation",
                    target_model="vet.appointment",
                    target_method="create",
                    payload={
                        "patient_id": patient_id,
                        "name": f"Clinical Follow-up ({days}d)",
                        "reason": f"Follow-up for {soap_schema.extracted_entities.primary_diagnosis or 'clinical condition'}",
                    },
                    requires_approval=True,
                )
            )

        formatted_text = f"""### Clinical SOAP Note

**Subjective (S):**
{soap_schema.subjective}

**Objective (O):**
{soap_schema.objective}

**Assessment (A):**
{soap_schema.assessment}

**Plan (P):**
{soap_schema.plan}
"""

        return WorkflowResult(
            workflow_id=self.workflow_id,
            response_text=formatted_text,
            action_cards=action_cards,
            metadata={"soap_schema": soap_schema.model_dump(), "model": result.model},
        )
