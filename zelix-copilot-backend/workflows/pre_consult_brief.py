"""
Workflow W02: Pre-Consultation Patient Briefing (Evidence-Grounded)
Separates authoritative Odoo facts from AI-generated verification checklists.
"""

from typing import Any, List
from schemas.clinical_schemas import (
    OdooAuthoritativeFacts,
    PreConsultBriefSchema,
)
from .base_workflow import BaseWorkflow, WorkflowResult


class PreConsultBriefWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__(
            workflow_id="w02_pre_consult_brief",
            name="Pre-Consultation Patient Brief",
            description="Synthesizes a 30-second evidence-grounded briefing before patient examination.",
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
        patient_summary = getattr(active_context, "patient_summary_obj", None)

        # 1. Build Immutable Odoo Facts from authoritative database records
        if patient_summary:
            odoo_facts = OdooAuthoritativeFacts(
                patient_id=patient_summary.id,
                patient_name=patient_summary.name,
                species=patient_summary.species,
                breed=patient_summary.breed,
                sex=patient_summary.sex,
                age=patient_summary.age_or_birthdate or "unknown",
                clinic_name=patient_summary.clinic,
                primary_owner=patient_summary.primary_owner,
                known_allergies_or_notes=patient_summary.notes,
            )
            encounter_history = [
                f"{enc.get('start_datetime', 'Date N/A')}: {enc.get('chief_complaint', 'Consult')} - Assessment: {enc.get('assessment', 'N/A')}"
                for enc in patient_summary.recent_encounters
            ]
            active_meds = [
                f"{rx.get('name', 'Rx')}: {rx.get('dose', '')} {rx.get('frequency', '')} ({rx.get('state', 'active')})"
                for rx in patient_summary.active_prescriptions
            ]
            pending_items = [
                f"Appointment: {appt.get('name')} ({appt.get('state')}) on {appt.get('start_datetime')}"
                for appt in patient_summary.upcoming_appointments
            ]
        else:
            odoo_facts = OdooAuthoritativeFacts(
                patient_id=getattr(active_context, "patient_id", 0) or 0,
                patient_name="Unknown Patient",
                species="Unknown",
                breed="Unknown",
                sex="Unknown",
            )
            encounter_history = []
            active_meds = []
            pending_items = []

        # 2. Prompt BitNet strictly to generate Doctor Actionable Checklist (No fake facts)
        system_prompt = f"""You are Zelix AI Clinical Assistant.
Analyze the authoritative patient records and generate a concise 3-item checklist of specific questions or physical exam checks the veterinarian should verify today.

AUTHORITATIVE PATIENT FACTS:
- Patient: {odoo_facts.patient_name} ({odoo_facts.species}, {odoo_facts.breed}, {odoo_facts.sex})
- Notes/Allergies: {odoo_facts.known_allergies_or_notes or 'None recorded'}
- Past Encounters: {'; '.join(encounter_history) if encounter_history else 'No previous encounters recorded.'}
- Active Medications: {'; '.join(active_meds) if active_meds else 'No active medications recorded.'}

INSTRUCTION: Output only 3 bullet points of verification items for the doctor. Do NOT invent past medical facts."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate today's pre-consult checklist. Doctor input: {user_input or 'None'}"},
        ]

        result = await provider.chat_complete(
            messages=messages,
            temperature=0.1,
            max_tokens=250,
        )

        suggested_checks = [
            line.strip().lstrip("-*123456789. ")
            for line in result.content.split("\n")
            if line.strip() and len(line.strip()) > 5
        ][:5]

        # 3. Create Typed PreConsultBriefSchema
        brief = PreConsultBriefSchema(
            odoo_facts=odoo_facts,
            recent_encounter_history=encounter_history,
            active_medications=active_meds,
            pending_items=pending_items,
            suggested_checks=suggested_checks,
        )

        # 4. Format Structured Markdown for Display
        formatted_text = f"""### Pre-Consultation Patient Briefing

#### Authoritative Patient Facts (Odoo DB)
- **Patient**: {brief.odoo_facts.patient_name} (ID: #{brief.odoo_facts.patient_id})
- **Species / Breed**: {brief.odoo_facts.species} - {brief.odoo_facts.breed}
- **Sex / Age**: {brief.odoo_facts.sex} ({brief.odoo_facts.age})
- **Primary Owner**: {brief.odoo_facts.primary_owner or 'None'}
- **Clinical Notes / Alerts**: {brief.odoo_facts.known_allergies_or_notes or 'None'}

#### Past Encounters History
{chr(10).join(f'- {enc}' for enc in brief.recent_encounter_history) if brief.recent_encounter_history else '- No prior recorded encounters.'}

#### Active Medications
{chr(10).join(f'- {med}' for med in brief.active_medications) if brief.active_medications else '- No active medications on file.'}

#### Things for Clinician to Verify Today
{chr(10).join(f'- {chk}' for chk in brief.suggested_checks)}
"""

        return WorkflowResult(
            workflow_id=self.workflow_id,
            response_text=formatted_text,
            action_cards=[],
            metadata={"brief_schema": brief.model_dump(), "model": result.model},
        )
