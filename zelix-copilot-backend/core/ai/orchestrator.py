"""
core/ai/orchestrator.py
Strict Intent Orchestrator mapping natural language user queries to registered Skill Registry capabilities.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from core.skills.registry import SkillRegistry
from core.sessions.context import EmployeeContext
from core.ai.provider import AIModelProvider
from core.ai.models import ChatMessage, ChatRole

logger = logging.getLogger("zelix.ai.orchestrator")


class IntentDecision(BaseModel):
    """Strict structured contract for intent classification and entity parameter extraction."""

    intent: str = Field(description="Selected skill ID from the Skill Registry, or 'general_query'")
    entity_type: Optional[str] = Field(default=None, description="Entity type: patient, appointment, encounter, medication, clinic, or null")
    entity_query: Optional[str] = Field(default=None, description="Extracted entity search term, name, MRN, or identifier, or null")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Routing confidence between 0.0 and 1.0")


class IntentOrchestrator:
    """Orchestrates natural language intent classification against registered Skill Registry capabilities."""

    def __init__(
        self,
        skill_registry: SkillRegistry,
        ai_provider: Optional[AIModelProvider] = None,
    ) -> None:
        self.skills = skill_registry
        self.ai_provider = ai_provider

    @property
    def registered_skill_ids(self) -> Set[str]:
        """Returns set of all skill IDs currently registered."""
        return {s.definition.id for s in self.skills.list()}

    def _build_skill_catalogue(self) -> str:
        """Dynamically builds skill catalogue from registry metadata."""
        lines = []
        for skill in self.skills.list():
            defn = skill.definition
            lines.append(f"- {defn.id}: {defn.description or defn.name}")
        lines.append("- general_query: Conversational greetings, help questions, or queries that do not match any domain skill.")
        return "\n".join(lines)

    def route(
        self,
        query: str,
        context: Optional[EmployeeContext] = None,
    ) -> IntentDecision:
        """Classify user intent into a validated IntentDecision."""
        clean_query = (query or "").strip()
        if not clean_query:
            return IntentDecision(intent="general_query", entity_type=None, entity_query=None, confidence=1.0)

        # 1. Attempt LLM Structured Reasoning if AI Provider is available
        if self.ai_provider:
            try:
                decision = self._classify_with_llm(clean_query, context)
                if decision:
                    return self._validate_decision(decision)
            except Exception as e:
                logger.warning(f"LLM intent orchestration failed, falling back to deterministic router: {e}")

        # 2. Deterministic Conservative Fallback
        return self._deterministic_fallback(clean_query, context)

    def _classify_with_llm(
        self,
        query: str,
        context: Optional[EmployeeContext] = None,
    ) -> Optional[IntentDecision]:
        """Prompts LLM to produce strict IntentDecision JSON against dynamic catalogue."""
        catalogue = self._build_skill_catalogue()
        allowed_skills = list(self.registered_skill_ids) + ["general_query"]

        system_prompt = (
            "You are the Intent & Entity Orchestrator for an enterprise AI Copilot.\n"
            "Analyze the user's natural language request and select exactly ONE intent from the registered skill catalogue below.\n\n"
            f"REGISTERED SKILL CATALOGUE:\n{catalogue}\n\n"
            "INSTRUCTIONS:\n"
            "1. If the user is looking for, finding, searching, checking existence of, or asking about a specific person/animal/patient record by name or ID (e.g. 'looking for Anabia', 'find Max', 'show me Anabia'), select 'entity_search' with entity_type='patient' and entity_query='<extracted name/id>'.\n"
            "2. If the user explicitly asks for longitudinal medical history, encounters, vaccines, or summary (e.g. 'summarize Max', 'what is Max\\'s history?'), select 'patient_360' with entity_type='patient' and entity_query='<extracted name/id>'.\n"
            "3. If the user dictates symptoms, findings, or consultation notes (e.g. 'vomiting x3, draft SOAP note'), select 'voice_to_soap'.\n"
            "4. If the user asks to prescribe medication or check dosages (e.g. 'prescribe Cerenia 16mg for Max'), select 'prescription_assistant'.\n"
            "5. If the user explicitly asks for daily clinic census, operations, appointments schedule, or inventory stock (e.g. 'give me today\\'s clinic summary', 'how many appointments today?'), select 'clinic_activity'.\n"
            "6. For greetings, ambiguous questions, or general help (e.g. 'hello', 'what can you do?', 'what should I do?'), select 'general_query'. NEVER select 'clinic_activity' for ambiguous queries.\n\n"
            "OUTPUT FORMAT:\n"
            "You MUST return ONLY a valid JSON object matching this schema:\n"
            "{\n"
            f'  "intent": "<one of {allowed_skills}>",\n'
            '  "entity_type": "patient" | "appointment" | "encounter" | "medication" | "clinic" | null,\n'
            '  "entity_query": "<extracted name or identifier or null>",\n'
            '  "confidence": 0.0 to 1.0\n'
            "}"
        )

        messages = [
            ChatMessage(role=ChatRole.SYSTEM, content=system_prompt),
            ChatMessage(role=ChatRole.USER, content=query),
        ]

        res = self.ai_provider.chat(messages=messages, temperature=0.0, max_tokens=100)
        content = res.content.strip()

        start_idx = content.find("{")
        end_idx = content.rfind("}")
        if start_idx != -1 and end_idx != -1:
            raw_json = content[start_idx : end_idx + 1]
            data = json.loads(raw_json)
            return IntentDecision(**data)

        return None

    def _validate_decision(self, decision: IntentDecision) -> IntentDecision:
        """Validates that the selected skill is strictly registered and confidence is sufficient."""
        if decision.intent not in self.registered_skill_ids and decision.intent != "general_query":
            logger.warning(f"Orchestrator proposed unregistered skill '{decision.intent}', falling back to general_query.")
            decision.intent = "general_query"

        if decision.confidence < 0.5:
            decision.intent = "general_query"

        return decision

    def _deterministic_fallback(
        self,
        query: str,
        context: Optional[EmployeeContext] = None,
    ) -> IntentDecision:
        """Conservative deterministic fallback if AI Provider is offline. NEVER defaults to clinic_activity."""
        q = query.lower().strip()

        # 1. Operational Clinic Census (Strict explicit phrases only)
        if any(p in q for p in [
            "clinic summary", "daily summary", "clinic census", "practice census",
            "today's clinic", "clinic activity", "daily census", "hospital summary",
            "hospital census", "clinic operations", "today's appointments and clinic"
        ]):
            return IntentDecision(intent="clinic_activity", entity_type=None, entity_query=None, confidence=0.95)

        # 2. Scribe / SOAP Dictation
        if any(p in q for p in ["draft soap", "create soap", "soap note", "consultation note", "dictation"]):
            return IntentDecision(intent="voice_to_soap", entity_type="patient", entity_query=None, confidence=0.9)

        # 3. Prescription Assistant
        if any(p in q for p in ["prescribe", "prescription", "rx", "dosage check", "dose check"]):
            return IntentDecision(intent="prescription_assistant", entity_type="medication", entity_query=None, confidence=0.9)

        # 4. Patient 360 (Explicit history / summary requests)
        if any(p in q for p in ["history", "summarize", "summary for", "summary of", "patient brief", "medical records", "encounters for"]):
            words = [w.strip(".,;:?!'\"") for w in query.split() if len(w.strip(".,;:?!'\"")) > 2]
            stop_words = {"summarize", "summary", "patient", "history", "details", "brief", "about", "for", "named", "show", "give", "tell", "record", "notes", "what", "is"}
            cand = [w.removesuffix("'s").removesuffix("’s") for w in words if w.lower() not in stop_words]
            return IntentDecision(
                intent="patient_360",
                entity_type="patient",
                entity_query=cand[0] if cand else None,
                confidence=0.85,
            )

        # 5. Entity Search / Lookup (Looking for, find, search, show me, who is)
        if any(p in q for p in ["looking for", "find", "search", "show me", "who is", "lookup", "look up", "check patient", "patient record"]):
            words = [w.strip(".,;:?!'\"") for w in query.split() if len(w.strip(".,;:?!'\"")) > 2]
            stop_words = {"looking", "for", "find", "search", "show", "me", "who", "is", "lookup", "look", "up", "check", "patient", "the", "a", "an", "record"}
            cand = [w.removesuffix("'s").removesuffix("’s") for w in words if w.lower() not in stop_words]
            return IntentDecision(
                intent="entity_search",
                entity_type="patient",
                entity_query=cand[0] if cand else None,
                confidence=0.85,
            )

        # 6. Active Record Context Check
        if context and context.active_entity:
            return IntentDecision(intent="patient_360", entity_type="patient", entity_query=context.active_entity.get("name"), confidence=0.7)

        # 7. Default for ALL Unrecognized, Ambiguous, or Conversational Queries -> general_query
        return IntentDecision(intent="general_query", entity_type=None, entity_query=None, confidence=0.5)
