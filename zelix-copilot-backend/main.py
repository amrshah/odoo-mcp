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
from skills.veterinary.patient_360_skill import Patient360Skill
from skills.veterinary.soap_skill import VoiceToSoapSkill
from skills.veterinary.prescription_skill import PrescriptionSafetySkill
from skills.veterinary.clinic_activity_skill import ClinicActivitySkill

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
skills.register(Patient360Skill())
skills.register(VoiceToSoapSkill())
skills.register(PrescriptionSafetySkill())
skills.register(ClinicActivitySkill())

# 4. Role Registry
roles = RoleRegistry()
roles.register(RoleManifest(
    id="veterinarian",
    name="Licensed Veterinarian",
    skills=["patient_360", "voice_to_soap", "prescription_assistant", "clinic_activity"],
    permissions=["patients.read", "medical_records.read", "medical_records.write", "prescriptions.write"],
))
roles.register(RoleManifest(
    id="doctor",
    name="Medical Doctor",
    skills=["patient_360", "voice_to_soap", "prescription_assistant", "clinic_activity"],
    permissions=["patients.read", "medical_records.read", "medical_records.write", "prescriptions.write"],
))
roles.register(RoleManifest(
    id="practice_manager",
    name="Practice Administrator",
    skills=["clinic_activity", "patient_360"],
    permissions=["*"],
))
roles.register(RoleManifest(
    id="technician",
    name="Veterinary Technician",
    skills=["patient_360", "clinic_activity"],
    permissions=["patients.read", "medical_records.read"],
))
roles.register(RoleManifest(
    id="receptionist",
    name="Front Desk Receptionist",
    skills=["clinic_activity", "patient_360"],
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

# 7. Copilot Engine
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


def _classify_intent(query: str, has_patient_context: bool) -> str:
    """Classify user natural language intent to clean core skill ID."""
    q = query.lower()
    if any(w in q for w in ["census", "operational", "activity", "appointments", "inventory", "stock", "clinic", "bed", "occupancy"]):
        return "clinic_activity"
    if any(w in q for w in ["soap", "dictation", "transcript", "consultation", "findings", "vital", "vomiting"]):
        return "voice_to_soap"
    if any(w in q for w in ["prescribe", "rx", "dosage", "dose", "medication", "cerenia", "amoxicillin"]):
        return "prescription_assistant"
    if any(w in q for w in ["patient", "history", "brief", "profile", "vaccin", "ehr", "longitudinal"]):
        return "patient_360"
    
    return "patient_360" if has_patient_context else "clinic_activity"


@app.post("/api/copilot/chat")
@app.post("/api/chat")
async def chat(payload: ChatPayload):
    start_time = time.time()
    user_query = payload.query or payload.message or "Help"
    role = payload.role or payload.user_role or "veterinarian"
    ctx_data = dict(payload.context or {})
    ctx_data["user_input"] = user_query
    
    active_entity = ctx_data.get("patient_context") or ctx_data.get("active_record") or None
    skill_id = _classify_intent(user_query, bool(active_entity))
    
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
    
    exec_result = engine.execute_skill(
        skill_id=skill_id,
        context=emp_context,
        user_input=user_query,
    )
    
    # Extract response message
    if isinstance(exec_result.output, dict):
        response_text = exec_result.output.get("response_text") or str(exec_result.output)
    else:
        response_text = str(exec_result.output or "")
    
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
        "workflow_id": skill_id,
        "skill_id": skill_id,
        "action_cards": action_cards,
        "proposed_actions": exec_result.proposed_actions,
        "patient_summary": exec_result.output if skill_id == "patient_360" else None,
        "model_used": exec_result.metadata.get("model", "qwen3.5:4b"),
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
    return {"success": True, "action_id": req.action_id, "status": "NOT_FOUND"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ZELIX_COPILOT_PORT", "8010"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

