"""
End-to-End Test Suite for Zelix Copilot Backend with Microsoft BitNet 1-bit LLM & Odoo 19
"""

import os
import sys
import asyncio
import pprint

# Force UTF-8 on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add zelix-copilot-backend and mcp-server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "zelix-copilot-backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server"))

from providers.alamia_provider import AlamiaAIProvider
from context.context_engine import ActiveContext
from orchestrator import CopilotRequest, ZelixCopilotOrchestrator
from odoo_client import OdooClient


async def run_e2e_tests():
    print("=" * 70)
    print("[*] STARTING ZELIX AI COPILOT E2E VERIFICATION TEST")
    print("=" * 70)

    # 1. Initialize Clients
    provider = AlamiaAIProvider()
    odoo_client = OdooClient()
    orchestrator = ZelixCopilotOrchestrator(provider=provider, odoo_client=odoo_client)

    # 2. Check Provider Health
    print("\n[1] Checking Alamia AI (BitNet Runtime) Connectivity...")
    health = await provider.check_health()
    print("    Health Status:", health.get("status"))
    print("    Endpoint:", health.get("endpoint"))

    # 3. Find our test patient 'Max'
    patients = odoo_client.search("vet.patient", [("name", "=", "Max")])
    patient_id = patients[0] if patients else 3
    print(f"\n[2] Linked Test Patient: 'Max' (ID: {patient_id})")

    appts = odoo_client.search("vet.appointment", [("patient_id", "=", patient_id)])
    appointment_id = appts[0] if appts else None
    existing_encs = odoo_client.search("vet.encounter", [("appointment_id", "=", appointment_id)]) if appointment_id else []
    encounter_id = existing_encs[0] if existing_encs else None
    print(f"    Linked Active Appointment ID: {appointment_id} | Encounter ID: {encounter_id}")

    # 4. Test Scenario 1: Pre-Consultation Brief (W02)
    print("\n" + "-" * 50)
    print("[TEST 1] Executing Pre-Consultation Briefing (W02)...")
    req1 = CopilotRequest(
        message="Prepare me for my next patient Max. Check prior history and what to focus on.",
        context=ActiveContext(model="vet.patient", record_id=patient_id, patient_id=patient_id, appointment_id=appointment_id, encounter_id=encounter_id),
        role="veterinarian",
    )
    res1 = await orchestrator.process_chat(req1)
    print(f"    Workflow Routed: {res1.workflow_id}")
    print(f"    Model Used: {res1.model_used}")
    print("    Response:\n")
    print(res1.response)

    # Assert Test 1: Pre-Consult Routing
    assert res1.workflow_id == "w02_pre_consult_brief", f"Test 1 Routing Failed: Expected w02_pre_consult_brief, got {res1.workflow_id}"
    print("    [PASS] Test 1 Pre-Consult Routing Verified.")

    # 5. Test Scenario 2: Ambient Scribe & SOAP Generation (W04)
    print("\n" + "-" * 50)
    print("[TEST 2] Executing Ambient Consultation Scribe -> SOAP Note (W04)...")
    consult_transcript = (
        "Doctor: Hello Sarah, how is Max doing today? "
        "Owner: Max has been vomiting yellow bile for the past 2 days, refusing dry food, but drinking water normally. "
        "Doctor: Let me examine him. Abdomen is soft, non-painful on palpation. Temperature is normal at 101.4 F, heart rate 90 bpm, mucous membranes pink and moist. "
        "Doctor: Looks like mild acute dietary gastroenteritis. Let's prescribe Maropitant Cerenia 16mg once daily for 3 days and feed bland boiled chicken and rice. "
        "Doctor: Please bring him back for a follow-up in 4 days if vomiting does not resolve completely."
    )

    req2 = CopilotRequest(
        message=consult_transcript,
        context=ActiveContext(model="vet.patient", record_id=patient_id, patient_id=patient_id, appointment_id=appointment_id, encounter_id=encounter_id),
        role="veterinarian",
    )
    res2 = await orchestrator.process_chat(req2)
    print(f"    Workflow Routed: {res2.workflow_id}")
    print("    Generated SOAP Note:\n")
    print(res2.response)
    print(f"\n    Action Cards Generated: {len(res2.action_cards)}")
    for card in res2.action_cards:
        print(f"     - Card ID: {card.action_id} | Title: {card.title} | Target: {card.target_model}")

    # Assert Test 2: Scribe Routing
    assert res2.workflow_id == "w04_scribe_soap", f"Test 2 Routing Failed: Expected w04_scribe_soap, got {res2.workflow_id}"
    assert len(res2.action_cards) >= 1, "Test 2 Failed: No Action Cards generated for SOAP note."
    print("    [PASS] Test 2 Scribe & SOAP Generation Verified.")

    # 6. Test Scenario 3: Human Approval & MCP Execution with Strict Read-Back
    target_card = res2.action_cards[0]
    print("\n" + "-" * 50)
    print(f"[TEST 3] Simulating Doctor Human Approval on ActionCard: '{target_card.title}'...")
    exec_result = await orchestrator.approve_and_execute_action(target_card.action_id)
    print("    Execution Result:")
    pprint.pprint(exec_result)

    assert exec_result.get("success") is True, f"Test 3 Failed: Approval execution failed: {exec_result.get('error')}"
    assert exec_result.get("verified_record") is not None, "Test 3 Failed: No read-back record returned."
    print(f"    [PASS] Test 3 Odoo Persistence Read-Back Verified: Record #{exec_result.get('record_id')}")

    # 7. Test Scenario 4: Prescription Assistant (W09)
    print("\n" + "-" * 50)
    print("[TEST 4] Executing Prescription Assistant (W09)...")
    req4 = CopilotRequest(
        message="Prescribe Amoxicillin-Clavulanate 250mg for Max, 1 tablet twice daily with food for 7 days for mild skin irritation.",
        context=ActiveContext(model="vet.patient", record_id=patient_id, patient_id=patient_id),
        role="veterinarian",
    )
    res4 = await orchestrator.process_chat(req4)
    print(f"    Workflow Routed: {res4.workflow_id}")
    print("    Prescription Proposal:\n")
    print(res4.response)

    assert res4.workflow_id == "w09_prescription_assistant", f"Test 4 Routing Failed: Expected w09_prescription_assistant, got {res4.workflow_id}"
    assert len(res4.action_cards) >= 1, "Test 4 Failed: No Action Cards generated for Prescription."
    print("    [PASS] Test 4 Prescription Routing & Proposal Verified.")

    rx_card = res4.action_cards[0]
    print(f"    Approving Prescription ActionCard: '{rx_card.title}'...")
    rx_exec = await orchestrator.approve_and_execute_action(rx_card.action_id)
    print("    Rx Execution Result:", rx_exec)

    assert rx_exec.get("success") is True, f"Test 4 Execution Failed: {rx_exec.get('error')}"
    assert rx_exec.get("verified_record") is not None, "Test 4 Read-Back Failed."
    print(f"    [PASS] Test 4 Odoo Prescription Persistence Read-Back Verified: Record #{rx_exec.get('record_id')}")

    print("\n" + "=" * 70)
    print("[SUCCESS] ALL ZELIX COPILOT E2E WORKFLOW TESTS COMPLETED & VERIFIED 100%!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_e2e_tests())
