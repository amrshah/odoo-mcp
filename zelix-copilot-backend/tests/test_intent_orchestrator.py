"""
tests/test_intent_orchestrator.py
Comprehensive tests for IntentOrchestrator and EntityLookupSkill routing contracts.
"""

import pytest
from core.skills.registry import SkillRegistry
from core.sessions.context import EmployeeContext
from core.ai.orchestrator import IntentOrchestrator, IntentDecision
from skills.veterinary.entity_lookup_skill import EntityLookupSkill
from skills.veterinary.patient_360_skill import Patient360Skill
from skills.veterinary.soap_skill import VoiceToSoapSkill
from skills.veterinary.prescription_skill import PrescriptionSafetySkill
from skills.veterinary.clinic_activity_skill import ClinicActivitySkill


@pytest.fixture
def orchestrator():
    skills = SkillRegistry()
    skills.register(EntityLookupSkill())
    skills.register(Patient360Skill())
    skills.register(VoiceToSoapSkill())
    skills.register(PrescriptionSafetySkill())
    skills.register(ClinicActivitySkill())
    # Test deterministic contract (ai_provider=None for deterministic reproducibility)
    return IntentOrchestrator(skill_registry=skills, ai_provider=None)


def test_routing_looking_for_anabia(orchestrator):
    decision: IntentDecision = orchestrator.route("looking for Anabia")
    assert decision.intent == "entity_search"
    assert decision.entity_type == "patient"
    assert decision.entity_query == "Anabia"


def test_routing_find_max(orchestrator):
    decision: IntentDecision = orchestrator.route("find Max")
    assert decision.intent == "entity_search"
    assert decision.entity_type == "patient"
    assert decision.entity_query == "Max"


def test_routing_show_me_anabia(orchestrator):
    decision: IntentDecision = orchestrator.route("show me Anabia")
    assert decision.intent == "entity_search"
    assert decision.entity_type == "patient"
    assert decision.entity_query == "Anabia"


def test_routing_summarize_max(orchestrator):
    decision: IntentDecision = orchestrator.route("summarize Max")
    assert decision.intent == "patient_360"
    assert decision.entity_type == "patient"
    assert decision.entity_query == "Max"


def test_routing_what_is_max_history(orchestrator):
    decision: IntentDecision = orchestrator.route("what is Max's history?")
    assert decision.intent == "patient_360"
    assert decision.entity_type == "patient"
    assert decision.entity_query == "Max"


def test_routing_clinic_summary(orchestrator):
    decision: IntentDecision = orchestrator.route("give me today's clinic summary")
    assert decision.intent == "clinic_activity"
    assert decision.entity_query is None


def test_routing_conversational_hello(orchestrator):
    decision: IntentDecision = orchestrator.route("hello")
    assert decision.intent == "general_query"
    assert decision.intent != "clinic_activity"


def test_routing_ambiguous_what_should_i_do(orchestrator):
    decision: IntentDecision = orchestrator.route("what should I do?")
    assert decision.intent == "general_query"
    assert decision.intent != "clinic_activity"


def test_regression_unrecognized_query_never_defaults_to_clinic_activity(orchestrator):
    """Explicit Regression Test: Arbitrary or unknown queries MUST NOT default to clinic_activity."""
    arbitrary_queries = [
        "random banana apple",
        "some random text 123",
        "why is the sky blue",
        "how does quantum computing work",
        "please explain this",
    ]
    for q in arbitrary_queries:
        decision: IntentDecision = orchestrator.route(q)
        assert decision.intent != "clinic_activity", f"Failed for query: '{q}'"
        assert decision.intent == "general_query"


def test_only_registered_skills_can_be_selected(orchestrator):
    """Test that decision intent is strictly constrained to registered Skill Registry."""
    registered = orchestrator.registered_skill_ids
    for sample in ["looking for Anabia", "summarize Max", "give me today's clinic summary", "hello"]:
        decision = orchestrator.route(sample)
        assert decision.intent in registered or decision.intent == "general_query"
