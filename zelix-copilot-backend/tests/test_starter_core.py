"""
tests/test_starter_core.py
Unit tests verifying Clean Core components, adapters, tools, skills, and policy gates.
"""

import pytest
import asyncio
from core.sessions.context import EmployeeContext
from core.actions.proposal import ActionProposal, RiskLevel, ActionStatus
from core.tools.registry import ToolRegistry
from core.skills.registry import SkillRegistry
from core.roles.registry import RoleRegistry
from core.roles.manifest import RoleManifest
from core.policies.engine import PolicyEngine
from core.policies.confirmation import ConfirmationPolicy
from core.runtime.engine import CopilotEngine, EngineTurnRequest
from adapters.ai.mock_provider import MockAIModelProvider
from adapters.odoo.zelix_odoo_adapter import ZelixOdooAdapter
from tools.veterinary.patient_tools import GetPatientRecordTool, GetVaccinationHistoryTool
from tools.veterinary.inventory_tools import GetPracticeCensusTool, GetInventoryStockTool
from skills.veterinary.patient_360_skill import Patient360Skill
from skills.veterinary.soap_skill import VoiceToSoapSkill
from skills.veterinary.prescription_skill import PrescriptionSafetySkill
from skills.veterinary.clinic_activity_skill import ClinicActivitySkill


def test_odoo_adapter_model_allowlist():
    """Verify ZelixOdooAdapter strictly enforces MODEL_MAP allowlist."""
    adapter = ZelixOdooAdapter()
    
    # Valid allowlisted entities
    assert adapter._get_model("patient") == "vet.patient"
    assert adapter._get_model("encounter") == "vet.encounter"
    assert adapter._get_model("prescription") == "vet.prescription"
    assert adapter._get_model("hms_patient") == "hms.patient"
    assert adapter._get_model("product") == "product.product"
    
    # Invalid model injection attempt
    with pytest.raises(ValueError) as exc:
        adapter._get_model("res.users.passwords")
    assert "not allowlisted" in str(exc.value)


def test_confirmation_policy_gates():
    """Verify clinical mutations strictly require confirmation."""
    policy = ConfirmationPolicy()
    assert policy.requires_confirmation("create_soap_encounter") is True
    assert policy.requires_confirmation("create_prescription") is True
    assert policy.requires_confirmation("read_patient_record") is False


def test_policy_engine_evaluation():
    """Verify PolicyEngine flags high-risk proposals as requires_confirmation=True."""
    engine_policy = PolicyEngine()
    context = EmployeeContext(user_id="vet_1", role="veterinarian")
    
    proposal = ActionProposal(
        action_id="act_test_1",
        action_type="create_soap_encounter",
        idempotency_key="soap_key_1",
        reason="Clinical SOAP test",
        risk_level=RiskLevel.HIGH,
        requires_confirmation=False, # initially False
    )
    
    evaluated = engine_policy.evaluate_action(context, proposal)
    assert evaluated.requires_confirmation is True


@pytest.mark.asyncio
async def test_patient_360_skill():
    """Verify Patient360Skill generates longitudinal brief."""
    tools = ToolRegistry()
    skill = Patient360Skill()
    mock_ai = MockAIModelProvider("Longitudinal brief: Max is a 4yo Golden Retriever with gastroenteritis.")
    
    context = EmployeeContext(
        patient_context={"id": 1, "name": "Max", "species": "Canine", "breed": "Golden Retriever"}
    )
    
    result = await skill.execute(context, tools=tools.get_accessible_tools(context), ai_provider=mock_ai)
    assert result.success is True
    assert "Max" in result.response_text or "Longitudinal" in result.response_text


@pytest.mark.asyncio
async def test_voice_to_soap_skill():
    """Verify VoiceToSoapSkill creates structured draft and high-risk ActionProposal."""
    tools = ToolRegistry()
    skill = VoiceToSoapSkill()
    mock_ai = MockAIModelProvider("### Clinical SOAP Draft\n**Subjective (S)**: Vomiting x3\n**Plan (P)**: Cerenia 16mg")
    
    context = EmployeeContext(
        patient_context={"id": 4, "name": "Bella", "species": "Feline"}
    )
    
    result = await skill.execute(
        context,
        tools=tools.get_accessible_tools(context),
        ai_provider=mock_ai,
        user_input="Bella vomiting x3, mild dehydration",
    )
    
    assert result.success is True
    assert len(result.proposed_actions) == 1
    proposal = result.proposed_actions[0]
    assert proposal["action_type"] == "create_soap_encounter"
    assert proposal["risk_level"] == "HIGH"
    assert proposal["requires_confirmation"] is True


@pytest.mark.asyncio
async def test_prescription_safety_skill():
    """Verify PrescriptionSafetySkill generates dosage and prescription proposal."""
    tools = ToolRegistry()
    skill = PrescriptionSafetySkill()
    
    context = EmployeeContext(
        patient_context={"id": 4, "name": "Max", "species": "Canine"}
    )
    
    result = await skill.execute(
        context,
        tools=tools.get_accessible_tools(context),
        user_input="Prescribe Cerenia 16mg for Max",
    )
    
    assert result.success is True
    assert len(result.proposed_actions) == 1
    proposal = result.proposed_actions[0]
    assert proposal["action_type"] == "create_prescription"
    assert "Cerenia" in proposal["payload"]["medication"]


@pytest.mark.asyncio
async def test_copilot_engine_e2e_turn():
    """Verify CopilotEngine end-to-end turn processing."""
    skills = SkillRegistry()
    skills.register(Patient360Skill())
    skills.register(VoiceToSoapSkill())
    skills.register(PrescriptionSafetySkill())
    skills.register(ClinicActivitySkill())
    
    tools = ToolRegistry()
    roles = RoleRegistry()
    roles.register(RoleManifest(id="veterinarian", name="Vet", permissions=["all"]))
    
    engine = CopilotEngine(
        skill_registry=skills,
        tool_registry=tools,
        role_registry=roles,
    )
    
    req = EngineTurnRequest(
        query="Summarize patient history for Max",
        context={"patient_summary": {"name": "Max", "species": "Canine", "breed": "Golden Retriever"}},
        role="veterinarian",
    )
    
    res = await engine.process_turn(req)
    assert res.skill_id == "patient_360"
    assert res.request_id.startswith("req_")
    assert "Max" in res.message
