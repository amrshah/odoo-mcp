"""
tests/test_pilot_multi_workflow.py
Multi-workflow end-to-end clinical simulation verifying ZelixOdooAdapter in dual shadow pilot mode.
Executes the 5 primary healthcare skills through CopilotEngine and validates parity telemetry.
"""

import pytest
from unittest.mock import patch

from core.sessions.context import EmployeeContext
from core.ai.models import ChatMessage, ChatRole
from adapters.ai.providers.mock_provider import MockAIModelProvider
from adapters.odoo.zelix_odoo_adapter import ZelixOdooAdapter
from core.skills.registry import SkillRegistry
from core.tools.registry import ToolRegistry
from core.roles.manifest import RoleManifest
from core.roles.registry import RoleRegistry
from core.policies.engine import PolicyEngine
from core.policies.confirmation import ConfirmationPolicy
from core.ai.router import AIModelRouter
from core.runtime.engine import CopilotEngine

from tools.veterinary.patient_tools import (
    GetPatientRecordTool,
    GetVaccinationHistoryTool,
    GetClinicalEncountersTool,
)
from tools.veterinary.inventory_tools import (
    GetInventoryStockTool,
    GetPracticeCensusTool,
)
from skills.veterinary.entity_lookup_skill import EntityLookupSkill
from skills.veterinary.patient_360_skill import Patient360Skill
from skills.veterinary.soap_skill import VoiceToSoapSkill
from skills.veterinary.prescription_skill import PrescriptionSafetySkill
from skills.veterinary.clinic_activity_skill import ClinicActivitySkill


@pytest.fixture
def copilot_pilot_setup():
    """Setup CopilotEngine with ZelixOdooAdapter configured in dual mode."""
    adapter = ZelixOdooAdapter(mode="dual")
    adapter.reset_parity_telemetry()

    tools = ToolRegistry()
    tools.register(GetPatientRecordTool(adapter))
    tools.register(GetVaccinationHistoryTool(adapter))
    tools.register(GetClinicalEncountersTool(adapter))
    tools.register(GetInventoryStockTool(adapter))
    tools.register(GetPracticeCensusTool(adapter))

    skills = SkillRegistry()
    skills.register(EntityLookupSkill())
    skills.register(Patient360Skill())
    skills.register(VoiceToSoapSkill())
    skills.register(PrescriptionSafetySkill())
    skills.register(ClinicActivitySkill())

    roles = RoleRegistry()
    roles.register(RoleManifest(
        id="veterinarian",
        name="Licensed Veterinarian",
        skills=["entity_search", "patient_360", "voice_to_soap", "prescription_assistant", "clinic_activity"],
        permissions=["patients.read", "medical_records.read", "medical_records.write", "prescriptions.write"],
    ))

    policy = PolicyEngine(confirmation_policy=ConfirmationPolicy())
    mock_ai = MockAIModelProvider(
        name="mock-ai",
        canned_response="Clinical synthesis complete. All vitals and indications within expected parameters."
    )
    router = AIModelRouter(default_provider=mock_ai)

    engine = CopilotEngine(
        skill_registry=skills,
        tool_registry=tools,
        role_registry=roles,
        policy_engine=policy,
        ai_router=router,
        application_adapter=adapter,
    )

    context = EmployeeContext(
        user_id="vet_1",
        role="veterinarian",
        permissions=["patients.read", "medical_records.read", "medical_records.write", "prescriptions.write"],
        active_entity={"id": 1, "type": "patient", "name": "Bella"},
        metadata={"user_input": ""},
    )

    return {
        "engine": engine,
        "adapter": adapter,
        "context": context,
    }


def test_multi_workflow_simulation(copilot_pilot_setup):
    """Execute all 5 domain skills through the dual-mode adapter and verify 100% parity."""
    engine = copilot_pilot_setup["engine"]
    adapter = copilot_pilot_setup["adapter"]
    ctx = copilot_pilot_setup["context"]

    sample_patient = {
        "id": 1,
        "name": "Bella",
        "identifier": "PAT-000001",
        "species_id": [1, "Canine"],
        "breed_id": [2, "Labrador Retriever"],
        "clinic_id": [3, "Downtown Vet Clinic"],
        "notes": "Patient in good general health.",
    }

    sample_vaccinations = [
        {"id": 10, "name": "Rabies Booster", "date": "2026-05-01"}
    ]

    sample_encounters = [
        {"id": 20, "chief_complaint": "Annual Exam", "diagnosis_summary": "Healthy"}
    ]

    sample_inventory = [
        {"id": 100, "name": "Cerenia 16mg", "qty_available": 45}
    ]

    sample_census = [
        {"id": 200, "state": "confirmed", "start_datetime": "2026-11-06 09:00:00"}
    ]

    def mock_direct_execute_kw(db, uid, key, model, method, args=None, kwargs=None):
        if model == "vet.patient":
            return [sample_patient]
        elif model == "vet.vaccination":
            return sample_vaccinations
        elif model == "vet.encounter":
            return sample_encounters
        elif model == "product.product":
            return sample_inventory
        elif model == "vet.appointment":
            return sample_census
        return []

    def mock_bridge_search_read(model, domain=None, fields=None, offset=0, limit=20, order=None):
        if model == "vet.patient":
            return [sample_patient]
        elif model == "vet.vaccination":
            return sample_vaccinations
        elif model == "vet.encounter":
            return sample_encounters
        elif model == "product.product":
            return sample_inventory
        elif model == "vet.appointment":
            return sample_census
        return []

    def mock_bridge_read(model, ids, fields=None):
        if model == "vet.patient":
            return [sample_patient]
        return []

    with patch.object(adapter.direct, "models") as mock_direct_models, \
         patch.object(adapter.bridge.client, "search_read", side_effect=mock_bridge_search_read), \
         patch.object(adapter.bridge.client, "read", side_effect=mock_bridge_read):

        mock_direct_models.execute_kw.side_effect = mock_direct_execute_kw

        # 1. Execute EntityLookupSkill
        ctx.metadata["user_input"] = "Find patient Bella"
        res1 = engine.execute_skill("entity_search", ctx)
        assert res1 is not None

        # 2. Execute Patient360Skill
        ctx.metadata["user_input"] = "Give me Patient 360 for Bella"
        res2 = engine.execute_skill("patient_360", ctx)
        assert res2 is not None

        # 3. Execute VoiceToSoapSkill
        ctx.metadata["user_input"] = "Draft SOAP: Dog vomited twice after eating grass, otherwise alert."
        res3 = engine.execute_skill("voice_to_soap", ctx)
        assert res3 is not None
        assert len(res3.proposed_actions) > 0
        action = res3.proposed_actions[0]
        action_type = action.get("action_type") if isinstance(action, dict) else getattr(action, "action_type", None)
        assert action_type == "create_soap_encounter"

        # 4. Execute PrescriptionSafetySkill
        ctx.metadata["user_input"] = "Prescribe Cerenia 16mg once daily for 3 days"
        res4 = engine.execute_skill("prescription_assistant", ctx)
        assert res4 is not None

        # 5. Execute ClinicActivitySkill
        ctx.metadata["user_input"] = "Check clinic activity and census"
        res5 = engine.execute_skill("clinic_activity", ctx)
        assert res5 is not None

        # Verify Parity Telemetry across the simulated session
        telemetry = adapter.get_parity_telemetry()
        assert telemetry["total_operations"] >= 5
        assert telemetry["matched_operations"] == telemetry["total_operations"]
        assert telemetry["parity_rate_pct"] == 100.0
        assert telemetry["discrepancy_count"] == 0
