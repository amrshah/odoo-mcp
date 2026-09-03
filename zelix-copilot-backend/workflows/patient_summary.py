"""
Workflow W01: Patient Longitudinal Summary
Generates comprehensive synthesis of past medical history, encounters, medications, and active clinical problems.
"""

from typing import Any
from .base_workflow import BaseWorkflow, WorkflowResult


class PatientSummaryWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__(
            workflow_id="w01_patient_summary",
            name="Patient Longitudinal Summary",
            description="Synthesizes complete medical history, chronic conditions, and unresolved issues.",
        )

    async def execute(
        self,
        user_input: str,
        context_prompt: str,
        active_context: Any,
        provider: Any,
    ) -> WorkflowResult:
        system_prompt = f"""You are Zelix AI Copilot. Synthesize a structured medical summary for the veterinary patient.

{context_prompt}

STRUCTURE:
- **Demographics & Profile**
- **Active Medical Problems**
- **Medication History**
- **Recent Consultations & Diagnosis Timeline**
- **Vaccination / Prevention Status**
- **Unresolved Items / Follow-ups Needed**
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Summarize case: {user_input or 'Full patient summary'}"},
        ]

        result = await provider.chat_complete(
            messages=messages,
            temperature=0.2,
            max_tokens=500,
        )

        return WorkflowResult(
            workflow_id=self.workflow_id,
            response_text=result.content,
            action_cards=[],
            metadata={"tokens": result.total_tokens, "model": result.model},
        )
