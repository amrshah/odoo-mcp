"""
main.py — ZelixAI Copilot Bootloader & API Gateway.
Built on the Alamia AI Copilot Starter Clean Core Architecture.
"""

import os
import sys
import uuid
import time
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Core imports
from core.sessions.context import EmployeeContext
from core.actions.proposal import ActionProposal, ActionStatus
from core.actions.statemachine import ActionStateMachine
from core.skills.registry import SkillRegistry
from core.tools.registry import ToolRegistry
from core.roles.manifest import RoleManifest
from core.roles.registry import RoleRegistry
from core.policies.engine import PolicyEngine
from core.policies.confirmation import ConfirmationPolicy
from core.audit.logger import InMemoryAuditLogger
from core.audit.entry import AuditEntry
from core.ai.router import AIModelRouter
from core.runtime.engine import CopilotEngine

# Adapters
from adapters.odoo.zelix_odoo_adapter import ZelixOdooAdapter
from adapters.ai.providers.alamia_provider import AlamiaAIModelProvider
from adapters.ai.providers.mock_provider import MockAIModelProvider

# Domain Tools
from tools.veterinary.patient_tools import (
    GetPatientRecordTool,
    GetVaccinationHistoryTool,
    GetClinicalEncountersTool,
)
from tools.veterinary.inventory_tools import (
    GetInventoryStockTool,
    GetPracticeCensusTool,
)

# Domain Skills
from skills.veterinary.entity_lookup_skill import EntityLookupSkill
from skills.veterinary.patient_360_skill import Patient360Skill
from skills.veterinary.soap_skill import VoiceToSoapSkill
from skills.veterinary.prescription_skill import PrescriptionSafetySkill
from skills.veterinary.clinic_activity_skill import ClinicActivitySkill
from core.ai.orchestrator import IntentOrchestrator, IntentDecision

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("zelix.gateway")

# ==============================================================================
# Assembly & Bootloader
# ==============================================================================

# 1. Application Adapter (Odoo 19 XML-RPC with MODEL_MAP allowlist)
odoo_adapter = ZelixOdooAdapter()

# 2. Tool Registry
tools = ToolRegistry()
tools.register(GetPatientRecordTool(odoo_adapter))
tools.register(GetVaccinationHistoryTool(odoo_adapter))
tools.register(GetClinicalEncountersTool(odoo_adapter))
tools.register(GetInventoryStockTool(odoo_adapter))
tools.register(GetPracticeCensusTool(odoo_adapter))

# 3. Skill Registry
skills = SkillRegistry()
skills.register(EntityLookupSkill())
skills.register(Patient360Skill())
skills.register(VoiceToSoapSkill())
skills.register(PrescriptionSafetySkill())
skills.register(ClinicActivitySkill())

# 4. Role Registry
roles = RoleRegistry()
roles.register(RoleManifest(
    id="veterinarian",
    name="Licensed Veterinarian",
    skills=["entity_search", "patient_360", "voice_to_soap", "prescription_assistant", "clinic_activity"],
    permissions=["patients.read", "medical_records.read", "medical_records.write", "prescriptions.write"],
))
roles.register(RoleManifest(
    id="doctor",
    name="Medical Doctor",
    skills=["entity_search", "patient_360", "voice_to_soap", "prescription_assistant", "clinic_activity"],
    permissions=["patients.read", "medical_records.read", "medical_records.write", "prescriptions.write"],
))
roles.register(RoleManifest(
    id="practice_manager",
    name="Practice Administrator",
    skills=["entity_search", "clinic_activity", "patient_360"],
    permissions=["*"],
))
roles.register(RoleManifest(
    id="technician",
    name="Veterinary Technician",
    skills=["entity_search", "patient_360", "clinic_activity"],
    permissions=["patients.read", "medical_records.read"],
))
roles.register(RoleManifest(
    id="receptionist",
    name="Front Desk Receptionist",
    skills=["entity_search", "clinic_activity", "patient_360"],
    permissions=["patients.read", "appointments.read"],
))

# 5. Policy Engine
confirmation_policy = ConfirmationPolicy()
confirmation_policy.always_require_confirmation_actions.add("create_soap_encounter")
confirmation_policy.always_require_confirmation_actions.add("create_prescription")
policy_engine = PolicyEngine(confirmation_policy=confirmation_policy)

# 6. AI Model Provider & Router
default_ai = AlamiaAIModelProvider()
ai_router = AIModelRouter(default_provider=default_ai)

# 7. Intent Orchestrator
intent_orchestrator = IntentOrchestrator(skill_registry=skills, ai_provider=default_ai)

# 8. Copilot Engine
engine = CopilotEngine(
    skill_registry=skills,
    tool_registry=tools,
    role_registry=roles,
    policy_engine=policy_engine,
    ai_router=ai_router,
    application_adapter=odoo_adapter,
)

# Pending HITL Actions Cache
pending_actions: Dict[str, tuple[ActionProposal, EmployeeContext]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Zelix AI Copilot Clean Core Engine...")
    try:
        health = await default_ai.check_health()
        logger.info(f"AI Provider Status: {health.get('status')} ({health.get('endpoint')})")
    except Exception as e:
        logger.warning(f"AI Provider health check notice: {e}")
    yield
    logger.info("Shutting down Zelix AI Copilot Engine...")


app = FastAPI(
    title="Zelix AI Copilot Gateway",
    description="Vertical Veterinary & Healthcare AI Copilot built on Alamia Copilot Starter Clean Core.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ==============================================================================
# Request / Response Schemas
# ==============================================================================

class ChatPayload(BaseModel):
    query: Optional[str] = None
    message: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    role: Optional[str] = "veterinarian"
    user_role: Optional[str] = None
    user_id: Optional[Any] = "admin"
    session_id: Optional[str] = None


class ActionRequest(BaseModel):
    action_id: str
    reason: Optional[str] = None


# ==============================================================================
# Endpoints
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h2>Zelix AI Copilot Clean Core Active</h2>")


@app.get("/health")
@app.get("/api/copilot/health")
async def health():
    ai_status = await default_ai.check_health()
    return {
        "status": "healthy",
        "service": "Zelix AI Copilot (Alamia Starter Clean Core)",
        "version": "2.0.0",
        "ai_runtime": ai_status,
        "active_skills": [s.definition.id for s in skills.list()],
        "active_tools": [t.definition.name for t in tools.list()],
    }


@app.post("/api/copilot/chat")
@app.post("/api/chat")
async def chat(payload: ChatPayload):
    start_time = time.time()
    user_query = payload.query or payload.message or "Help"
    role = payload.role or payload.user_role or "veterinarian"
    ctx_data = dict(payload.context or {})
    ctx_data["user_input"] = user_query
    
    active_entity = ctx_data.get("patient_context") or ctx_data.get("active_record") or None

    role_manifest = roles.get(role)
    permissions = role_manifest.permissions if role_manifest else ["*"]

    emp_context = EmployeeContext(
        user_id=str(payload.user_id or "admin"),
        role=role,
        permissions=permissions,
        active_entity=active_entity,
        metadata=ctx_data,
        conversation_id=payload.session_id,
    )

    # 1. Route Intent through IntentOrchestrator
    decision: IntentDecision = intent_orchestrator.route(user_query, emp_context)
    logger.info(f"Intent Decision: {decision.model_dump_json()}")

    # 2. Handle general / ambiguous queries without executing unrelated domain skills
    if decision.intent == "general_query":
        general_response = (
            "Hello! I am your Zelix AI Clinical Copilot.\n\n"
            "I can assist you with:\n"
            "- **Patient & Entity Lookup**: e.g. *\"Looking for Anabia\"*, *\"Find Max\"*, *\"Show me Anabia\"*\n"
            "- **Patient 360 History**: e.g. *\"Summarize Max\"*, *\"What is Max's history?\"*\n"
            "- **Clinical Scribe**: e.g. *\"Draft a SOAP note for vomiting x3\"*\n"
            "- **Prescription Safety**: e.g. *\"Prescribe Cerenia 16mg for Max\"*\n"
            "- **Clinic Operations**: e.g. *\"Give me today's clinic summary\"*\n\n"
            "How can I help you today?"
        )
        return {
            "response": general_response,
            "message": general_response,
            "content": general_response,
            "workflow_id": "general_query",
            "skill_id": "general_query",
            "action_cards": [],
            "proposed_actions": [],
            "intent_decision": decision.model_dump(),
            "patient_summary": None,
            "model_used": "orchestrator",
            "request_id": f"req_{uuid.uuid4().hex[:8]}",
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }

    # 3. Execute Selected Business Skill
    exec_result = engine.execute_skill(
        skill_id=decision.intent,
        context=emp_context,
        user_input=user_query,
        entity_type=decision.entity_type,
        entity_query=decision.entity_query,
    )
    
    # Extract response message
    if isinstance(exec_result.output, dict):
        response_text = exec_result.output.get("response_text") or str(exec_result.output)
    elif exec_result.output:
        response_text = str(exec_result.output)
    elif exec_result.error:
        response_text = f"Skill execution error: {exec_result.error}"
    else:
        response_text = ""
    
    action_cards = []
    for raw_prop in exec_result.proposed_actions:
        proposal = ActionProposal.model_validate(raw_prop)
        pending_actions[proposal.action_id] = (proposal, emp_context)
        action_cards.append({
            "action_id": proposal.action_id,
            "title": proposal.metadata.get("title", proposal.action_type),
            "description": proposal.reason,
            "risk_level": proposal.risk_level,
            "proposed_changes": proposal.proposed_changes,
            "requires_confirmation": proposal.requires_confirmation,
            "status": proposal.status.value,
        })
    
    duration_ms = int((time.time() - start_time) * 1000)
    return {
        "response": response_text,
        "message": response_text,
        "content": response_text,
        "workflow_id": decision.intent,
        "skill_id": decision.intent,
        "action_cards": action_cards,
        "proposed_actions": [p.model_dump() for p, _ in [pending_actions.get(c["action_id"]) for c in action_cards] if p],
        "intent_decision": decision.model_dump(),
        "patient_summary": exec_result.output.get("patient") if isinstance(exec_result.output, dict) else None,
        "model_used": default_ai.default_model,
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "execution_time_ms": duration_ms,
    }


@app.post("/api/copilot/action/approve")
@app.post("/api/action/confirm")
async def approve_action(req: ActionRequest):
    if req.action_id not in pending_actions:
        raise HTTPException(status_code=404, detail=f"Action proposal '{req.action_id}' not found or already executed.")
    
    proposal, emp_context = pending_actions.pop(req.action_id)
    ActionStateMachine.transition(proposal, ActionStatus.CONFIRMED)
    executed = engine.execute_action(proposal, emp_context)
    
    return {
        "success": executed.status == ActionStatus.COMPLETED,
        "status": executed.status.value,
        "action_id": executed.action_id,
        "result": executed.result,
        "error": executed.error,
    }


@app.post("/api/copilot/action/reject")
@app.post("/api/action/reject")
async def reject_action(req: ActionRequest):
    if req.action_id in pending_actions:
        proposal, _ = pending_actions.pop(req.action_id)
        proposal.status = ActionStatus.REJECTED
        return {"success": True, "action_id": req.action_id, "status": "REJECTED"}
class PrescriptionApprovalPayload(BaseModel):
    prescription_id: int
    user_id: Optional[str] = "admin"
    user_role: Optional[str] = "veterinarian"


@app.get("/api/copilot/context/identity")
async def get_identity_context(user_id: Optional[str] = "admin", role: Optional[str] = None):
    ident = odoo_adapter.identity(user_id or "admin") or {}
    
    # Query clinic / facility from Odoo
    clinics = odoo_adapter.search("clinic", limit=1)
    clinic_name = clinics[0].get("name") if clinics else "VetCairn Animal Hospital"
    
    # Query company
    companies = odoo_adapter.search("company", limit=1)
    company_name = companies[0].get("name") if companies else "Medical Practice"
    
    name = ident.get("name") or "Administrator"
    effective_role_id = role or ident.get("role") or "veterinarian"
    
    role_manifest = roles.get(effective_role_id)
    role_name = role_manifest.name if role_manifest else effective_role_id.replace("_", " ").title()
    
    # Initials
    parts = name.split()
    initials = "".join([p[0].upper() for p in parts if p])[:2] if parts else "US"
    
    return {
        "status": "success",
        "user": {
            "id": ident.get("id") or 2,
            "name": name,
            "login": ident.get("login") or "admin",
            "role_id": effective_role_id,
            "role": role_name,
            "initials": initials,
        },
        "facility": {
            "clinic_name": clinic_name,
            "company_name": company_name,
        },
        "roles": [
            {"id": r.id, "name": r.name, "skills": r.skills} for r in roles.list()
        ],
    }


@app.get("/api/copilot/dashboard/summary")
async def get_dashboard_summary():
    census_tool = tools.get("get_practice_census")
    emp_context = EmployeeContext(user_id="admin", role="veterinarian", permissions=["*"])
    data = census_tool.execute(emp_context) if census_tool else {}
    return {
        "status": "success",
        "summary": data,
    }


@app.get("/api/copilot/prescriptions/pending")
async def get_pending_prescriptions():
    pending_rx = odoo_adapter.search("prescription", query={"state": ["in", ["draft", "pending"]]}, limit=50)
    formatted = []
    for r in pending_rx:
        patient_name = r["patient_id"][1] if isinstance(r.get("patient_id"), (list, tuple)) else str(r.get("patient_id") or "Max")
        medication_name = r["medication_id"][1] if isinstance(r.get("medication_id"), (list, tuple)) else str(r.get("medication_id") or "Medication")
        formatted.append({
            "id": r["id"],
            "name": r.get("name") or f"RX-{r['id']}",
            "patient_name": patient_name,
            "medication_name": medication_name,
            "dose": r.get("dose") or "1 tablet",
            "route": r.get("route") or "oral",
            "frequency": r.get("frequency") or "SID",
            "duration": r.get("duration") or "3 days",
            "quantity": r.get("quantity") or 1,
            "quantity_unit": r.get("quantity_unit") or "tablets",
            "instructions": r.get("instructions") or "Take with food",
            "clinical_indication": r.get("clinical_indication") or "Routine",
            "state": r.get("state") or "draft",
        })
    return {
        "status": "success",
        "count": len(formatted),
        "prescriptions": formatted,
    }


@app.post("/api/copilot/prescriptions/approve")
async def approve_prescription_direct(payload: PrescriptionApprovalPayload):
    rx_id = payload.prescription_id
    success = odoo_adapter.update("prescription", str(rx_id), {"state": "approved"})
    
    # Audit log
    engine.audit.log(
        AuditEntry(
            audit_id=f"audit_rx_approve_{rx_id}_{uuid.uuid4().hex[:6]}",
            event_type="PRESCRIPTION_APPROVAL",
            user_id=payload.user_id or "admin",
            role=payload.user_role or "veterinarian",
            skill_id="prescription_assistant",
            status="SUCCESS" if success else "FAILURE",
            details={"prescription_id": rx_id, "state": "approved"},
        )
    )
    
    # Check remaining pending count
    remaining = odoo_adapter.search("prescription", query={"state": ["in", ["draft", "pending"]]}, limit=50)
    
    return {
        "success": bool(success),
        "prescription_id": rx_id,
        "state": "approved",
        "remaining_count": len(remaining),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ZELIX_COPILOT_PORT", "8010"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

