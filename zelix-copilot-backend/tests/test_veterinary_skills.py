"""
tests/test_veterinary_skills.py
Vertical integration tests for ZelixAI Veterinary Skills and Odoo Adapter.
"""

import pytest
from core.sessions.context import EmployeeContext
from core.tools.registry import ToolRegistry
from adapters.ai.providers.mock_provider import MockAIModelProvider
from adapters.odoo.zelix_odoo_adapter import ZelixOdooAdapter
from tools.veterinary.patient_tools import GetPatientRecordTool, GetVaccinationHistoryTool
from skills.veterinary.patient_360_skill import Patient360Skill
from skills.veterinary.soap_skill import VoiceToSoapSkill
from skills.veterinary.prescription_skill import PrescriptionSafetySkill
from skills.veterinary.clinic_activity_skill import ClinicActivitySkill


def test_zelix_odoo_adapter_allowlist():
    """Verify ZelixOdooAdapter strictly enforces MODEL_MAP allowlist."""
    adapter = ZelixOdooAdapter()
    assert adapter._get_model("patient") == "vet.patient"
    assert adapter._get_model("encounter") == "vet.encounter"
    assert adapter._get_model("prescription") == "vet.prescription"
    assert adapter._get_model("hms_patient") == "hms.patient"

    with pytest.raises(ValueError) as exc:
        adapter._get_model("unknown_illegal_model")
    assert "not allowlisted" in str(exc.value)


def test_veterinary_patient_360():
    tools = ToolRegistry()
    skill = Patient360Skill()
    mock_ai = MockAIModelProvider(name="mock-ai", canned_response="Longitudinal brief for Max: Golden Retriever with gastroenteritis.")
    context = EmployeeContext(
        user_id="vet_1",
        role="veterinarian",
        active_entity={"id": 1, "name": "Max", "species": "Canine", "breed": "Golden Retriever"},
    )
    result = skill.execute(context, tools={t.definition.name: t for t in tools.list()}, ai_provider=mock_ai)
    assert result.success is True
    assert "Max" in result.output["response_text"]


def test_veterinary_soap_and_prescription_skills():
    tools = ToolRegistry()
    soap_skill = VoiceToSoapSkill()
    rx_skill = PrescriptionSafetySkill()
    context = EmployeeContext(
        user_id="vet_1",
        role="veterinarian",
        active_entity={"id": 4, "name": "Bella", "species": "Feline"},
    )

    # Test SOAP
    soap_res = soap_skill.execute(context, tools={t.definition.name: t for t in tools.list()}, user_input="Vomiting x3")
    assert soap_res.success is True
    assert len(soap_res.proposed_actions) == 1
    assert soap_res.proposed_actions[0]["action_type"] == "create_soap_encounter"

    # Test Rx
    rx_res = rx_skill.execute(context, tools={t.definition.name: t for t in tools.list()}, user_input="Prescribe Cerenia")
    assert rx_res.success is True
    assert len(rx_res.proposed_actions) == 1
    assert rx_res.proposed_actions[0]["action_type"] == "create_prescription"


def test_veterinary_clinic_activity_skill():
    tools = ToolRegistry()
    skill = ClinicActivitySkill()
    context = EmployeeContext(
        user_id="mgr_1",
        role="practice_manager",
    )
    result = skill.execute(context, tools={t.definition.name: t for t in tools.list()})
    assert result.success is True
    assert "Clinic & Hospital Operations Daily Summary" in result.output["response_text"]
    assert result.output["total_patients"] >= 1
