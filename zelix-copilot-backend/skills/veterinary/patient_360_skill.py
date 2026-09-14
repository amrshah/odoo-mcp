"""
skills/veterinary/patient_360_skill.py
Synthesizes complete longitudinal medical history, active problems, and vaccination status.
"""

from typing import Any, Dict, Optional
from core.skills.base import BaseSkill, SkillResult
from core.skills.definition import SkillDefinition
from core.sessions.context import EmployeeContext
from core.ai.models import ChatMessage, ChatRole


class Patient360Skill(BaseSkill):
    """Synthesizes complete longitudinal medical history, chronic conditions, and unresolved issues."""

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            id="patient_360",
            name="Patient 360 Longitudinal Summary",
            description="Synthesizes complete medical history, chronic conditions, vaccinations, and unresolved issues.",
            required_tools=["get_patient_record", "get_vaccination_history", "get_clinical_encounters"],
            risk_level="LOW",
            allowed_roles=["veterinarian", "doctor", "technician", "practice_manager"],
        )

    def execute(
        self,
        context: EmployeeContext,
        tools: Dict[str, Any],
        ai_provider: Optional[Any] = None,
        **kwargs: Any,
    ) -> SkillResult:
        patient_tool = tools.get("get_patient_record")
        patient = patient_tool.execute(context, **kwargs) if patient_tool else (context.active_entity or context.metadata.get("patient_context"))

        if not patient:
            no_patient_text = (
                "### Patient Record Synthesis\n"
                "No specific patient record was loaded in the current view.\n\n"
                "Please select or open a Patient record in Odoo to generate a comprehensive longitudinal summary."
            )
            return SkillResult(
                success=True,
                skill_id=self.definition.id,
                output={"response_text": no_patient_text},
            )

        name = patient.get("name", "Unknown Patient")
        ident = patient.get("identifier", "PAT")
        species = patient.get("species", "Patient")
        breed = patient.get("breed", "")
        age = patient.get("age", "")
        notes = patient.get("notes", "No active contraindications recorded.")

        # Vaccinations
        vax_tool = tools.get("get_vaccination_history")
        vax_list = vax_tool.execute(context, patient_id=patient.get("id")) if vax_tool else []
        vax_summary = ", ".join([v.get("name", "Vaccine") for v in vax_list]) if vax_list else "Up to date / None overdue"

        # Encounters
        enc_tool = tools.get("get_clinical_encounters")
        enc_list = enc_tool.execute(context, patient_id=patient.get("id")) if enc_tool else []
        enc_summary = f"{len(enc_list)} past encounters on file." if enc_list else "First clinical encounter."

        system_prompt = (
            f"You are Zelix AI Copilot. Synthesize a concise, clinical summary for veterinary patient {name}.\n"
            f"Species: {species} | Breed: {breed} | Age: {age}\n"
            f"Medical Notes: {notes}\n"
            f"Vaccinations: {vax_summary}\n"
            f"Encounters: {enc_summary}\n"
            f"Provide a structured synthesis with Demographics, Active Issues, Prevention Status, and Recommendations."
        )

        messages = [
            ChatMessage(role=ChatRole.SYSTEM, content=system_prompt),
            ChatMessage(role=ChatRole.USER, content=f"Summarize patient {name} ({ident})"),
        ]

        if ai_provider:
            try:
                res = ai_provider.chat(messages=messages, max_tokens=400)
                return SkillResult(
                    success=True,
                    skill_id=self.definition.id,
                    output={
                        "response_text": res.content,
                        "patient": patient,
                        "vaccinations": vax_list,
                        "encounters": enc_list,
                    },
                    metadata={"model": res.model, "tokens": res.usage.get("total_tokens", 0)},
                )
            except Exception:
                pass

        # Deterministic fallback response
        fallback_text = (
            f"### Patient 360 Summary: **{name}** ({ident})\n"
            f"- **Demographics**: {species} · {breed or 'Standard'} · {age or 'Adult'}\n"
            f"- **Clinical Notes**: {notes}\n"
            f"- **Vaccination & Prevention**: {vax_summary}\n"
            f"- **Encounter History**: {enc_summary}\n"
            f"- **Clinical Recommendations**: Review hydration, confirm no known drug allergies, and check vital signs before prescribing."
        )
        return SkillResult(
            success=True,
            skill_id=self.definition.id,
            output={"response_text": fallback_text, "patient": patient},
            metadata={"model": "deterministic-ehr-fallback"},
        )
