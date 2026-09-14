"""
skills/veterinary/entity_lookup_skill.py
Lightweight entity search and discovery skill for looking up patients by name or identifier.
"""

from typing import Any, Dict, Optional
from core.skills.base import BaseSkill, SkillResult
from core.skills.definition import SkillDefinition
from core.sessions.context import EmployeeContext
from core.ai.models import ChatMessage, ChatRole


class EntityLookupSkill(BaseSkill):
    """Searches and verifies patient or clinical entity records in the EHR registry."""

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            id="entity_search",
            name="Patient & Entity Lookup",
            description="Searches, verifies, and locates patient or clinical entity records by name, MRN, or identifier, offering relevant follow-up clinical actions.",
            required_tools=["get_patient_record"],
            risk_level="LOW",
            allowed_roles=["veterinarian", "doctor", "technician", "practice_manager", "receptionist"],
        )

    def execute(
        self,
        context: EmployeeContext,
        tools: Dict[str, Any],
        ai_provider: Optional[Any] = None,
        **kwargs: Any,
    ) -> SkillResult:
        patient_tool = tools.get("get_patient_record")
        search_query = kwargs.get("entity_query") or kwargs.get("user_input") or kwargs.get("query")
        clean_kwargs = {k: v for k, v in kwargs.items() if k not in ("entity_query", "query", "user_input")}
        patient = patient_tool.execute(context, entity_query=search_query, **clean_kwargs) if patient_tool else None

        # 1. Not Found Case
        if not patient or patient.get("_not_found"):
            searched = patient.get("searched_name") if (patient and isinstance(patient, dict)) else (search_query or "specified entity")
            not_found_text = (
                f"### Patient Record Search\n"
                f"No patient matching **'{searched}'** was found in the EHR registry (VetCairn & Stratos HMS).\n\n"
                f"Would you like to check the spelling, search with an MRN/Microchip ID, or register a new patient in Odoo?"
            )
            return SkillResult(
                success=True,
                skill_id=self.definition.id,
                output={"response_text": not_found_text, "found": False, "searched_name": searched},
            )

        # 2. Found Case
        name = patient.get("name", "Unknown Patient")
        ident = patient.get("identifier") or patient.get("mrn") or "PAT"
        species = patient.get("species", "Patient")
        breed = patient.get("breed", "")
        status = patient.get("status") or ("Active" if patient.get("active") else "Inactive")
        notes = patient.get("notes") or ""

        # AI Synthesis if provider available
        if ai_provider:
            try:
                system_prompt = (
                    f"You are Zelix AI Copilot. The clinician searched for patient '{name}'.\n"
                    f"Record details: Name: {name} | ID: {ident} | Species: {species} | Breed: {breed} | Status: {status} | Notes: {notes}\n"
                    f"Provide a crisp 2-3 line acknowledgment showing the patient was found, their key demographics, and naturally offer follow-up actions (e.g., summarize medical history, start consultation/SOAP, or draft prescription)."
                )
                messages = [
                    ChatMessage(role=ChatRole.SYSTEM, content=system_prompt),
                    ChatMessage(role=ChatRole.USER, content=f"Look up {name}"),
                ]
                res = ai_provider.chat(messages=messages, max_tokens=350)
                if res.content and res.content.strip():
                    return SkillResult(
                        success=True,
                        skill_id=self.definition.id,
                        output={
                            "response_text": res.content.strip(),
                            "patient": patient,
                            "found": True,
                        },
                        metadata={"model": res.model},
                    )
            except Exception:
                pass

        # Deterministic formatting
        found_text = (
            f"### Patient Record Found: **{name}** ({ident})\n"
            f"- **Demographics**: {species}{(' · ' + breed) if breed else ''}\n"
            f"- **Status**: {status}\n"
            f"{f'- **Clinical Notes**: {notes}' if notes else ''}\n\n"
            f"**Suggested Next Actions**:\n"
            f"- Ask *\"Summarize {name}\"* to view full longitudinal history and encounters.\n"
            f"- Ask *\"Start consultation for {name}\"* to prepare a clinical SOAP note.\n"
            f"- Ask *\"Draft prescription for {name}\"* to prescribe medication."
        )
        return SkillResult(
            success=True,
            skill_id=self.definition.id,
            output={
                "response_text": found_text,
                "patient": patient,
                "found": True,
            },
        )
