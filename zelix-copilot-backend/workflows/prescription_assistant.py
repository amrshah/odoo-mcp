"""
Workflow W09: Prescription Assistant
Parses prescription directives, validates medical consistency (e.g. rejects contradictory frequencies), and prepares proposals.
"""

import uuid
from typing import Any, List
from schemas.parser import SchemaParser
from validators.clinical_validator import ClinicalValidator
from .base_workflow import ActionCard, ActionType, BaseWorkflow, WorkflowResult


class PrescriptionAssistantWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__(
            workflow_id="w09_prescription_assistant",
            name="Prescription Assistant",
            description="Parses natural language medication directives, checks clinical consistency, and prepares structured prescription proposals.",
        )

    async def execute(
        self,
        user_input: str,
        context_prompt: str,
        active_context: Any,
        provider: Any,
        odoo_client: Any = None,
        **kwargs,
    ) -> WorkflowResult:
        system_prompt = f"""You are Zelix AI Prescription Copilot for veterinary medicine.
Extract the medication prescription parameters from the doctor's request.

{context_prompt}

FORMAT:
Medication Name: <name of drug>
Dosage: <e.g. 250mg, 16mg>
Frequency: <e.g. BID (Twice Daily), SID (Once Daily), TID (Three times daily)>
Duration: <e.g. 7 days, 14 days>
Instructions: <administration instructions e.g. with food>
Indication: <clinical reason>
Warnings: <precautions/contraindications>
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Prescribe medication: {user_input}"},
        ]

        result = await provider.chat_complete(
            messages=messages,
            temperature=0.1,
            max_tokens=300,
        )

        patient_id = getattr(active_context, "patient_id", None) or 3
        clinic_id = getattr(active_context, "clinic_id", None) or 3
        prescriber_id = getattr(active_context, "user_uid", None) or 2

        # 1. Parse into Typed Schema
        proposal = SchemaParser.parse_prescription_proposal(
            raw_text=result.content,
            patient_id=patient_id,
            medication_id=3,  # Amoxicillin-Clavulanate 250mg
            clinic_id=clinic_id,
            prescriber_id=prescriber_id,
        )

        # 2. Run Deterministic Clinical Consistency Check
        validation = ClinicalValidator.validate_prescription(proposal)
        if not validation.is_valid:
            return WorkflowResult(
                workflow_id=self.workflow_id,
                response_text=f"❌ **Prescription Validation Failed**:\n" + "\n".join(f"- {err}" for err in validation.errors),
                action_cards=[],
                metadata={"validation_errors": validation.errors, "is_valid": False},
            )

        # 3. Create Action Card for Human Approval
        action_cards: List[ActionCard] = [
            ActionCard(
                action_id=f"act_rx_{uuid.uuid4().hex[:8]}",
                action_type=ActionType.CREATE_PRESCRIPTION,
                title=f"Issue Prescription: {proposal.medication_name}",
                description=f"Issue {proposal.dose} ({proposal.frequency}) for {proposal.duration}",
                target_model="vet.prescription",
                target_method="create",
                payload={
                    "patient_id": proposal.patient_id,
                    "clinic_id": proposal.clinic_id,
                    "prescriber_id": proposal.prescriber_id,
                    "medication_id": proposal.medication_id,
                    "dose": proposal.dose,
                    "route": proposal.route,
                    "frequency": proposal.frequency,
                    "duration": proposal.duration,
                    "quantity": proposal.quantity,
                    "quantity_unit": proposal.quantity_unit,
                    "instructions": proposal.instructions,
                    "clinical_indication": proposal.clinical_indication,
                    "state": "draft",
                },
                requires_approval=True,
                preview_data={"prescription_proposal": proposal.model_dump()},
            )
        ]

        formatted_text = f"""### Prescription Proposal

- **Medication**: {proposal.medication_name}
- **Dosage**: {proposal.dose}
- **Frequency**: {proposal.frequency}
- **Duration**: {proposal.duration}
- **Instructions**: {proposal.instructions}
- **Indication**: {proposal.clinical_indication}
{f"- **Warnings**: {proposal.safety_warnings}" if proposal.safety_warnings else ""}

[ACTION REQUIRED] Please review and approve the prescription details before saving.
"""

        return WorkflowResult(
            workflow_id=self.workflow_id,
            response_text=formatted_text,
            action_cards=action_cards,
            metadata={"proposal": proposal.model_dump(), "model": result.model},
        )
