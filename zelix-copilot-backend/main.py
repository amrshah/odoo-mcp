"""
main.py — ZelixAI Copilot Bootloader & API Gateway.
Built on the Alamia AI Copilot Starter Clean Core Architecture.
"""

import os
import sys
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
from core.actions.proposal import ActionProposal
from core.skills.registry import SkillRegistry
from core.tools.registry import ToolRegistry
from core.roles.manifest import RoleManifest
from core.roles.registry import RoleRegistry
from core.policies.engine import PolicyEngine
from core.policies.confirmation import ConfirmationPolicy
from core.audit.ledger import AuditLedger
from core.ai.router import AIModelRouter
from core.runtime.engine import CopilotEngine, EngineTurnRequest, EngineTurnResponse

# Adapters
from adapters.odoo.zelix_odoo_adapter import ZelixOdooAdapter
from adapters.ai.alamia_provider import AlamiaAIModelProvider
from adapters.ai.mock_provider import MockAIModelProvider

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
    id="practice_manager",
    name="Practice Administrator",
    skills=["clinic_activity", "patient_360"],
    permissions=["all"],
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
ai_router = AIModelRouter(
    default_provider=default_ai,
    skill_routes={
        "clinic_activity": "local_fast_slm",
        "patient_360": "local_fast_slm",
        "voice_to_soap": "reasoning_slm",
        "prescription_assistant": "safety_slm",
    },
)

# 7. Copilot Engine
engine = CopilotEngine(
    skill_registry=skills,
    tool_registry=tools,
    role_registry=roles,
    policy_engine=policy_engine,
    ai_router=ai_router,
    application_adapter=odoo_adapter,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Zelix AI Copilot Clean Core Engine...")
    health = await default_ai.check_health()
    logger.info(f"AI Provider Status: {health.get('status')} ({health.get('endpoint')})")
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
        "active_skills": [s.definition.id for s in skills.list_all()],
        "active_tools": [t.definition.name for t in tools.list_all()],
    }


@app.post("/api/copilot/chat")
@app.post("/api/chat")
async def chat(payload: ChatPayload):
    user_query = payload.query or payload.message or "Help"
    role = payload.role or payload.user_role or "veterinarian"
    
    turn_req = EngineTurnRequest(
        query=user_query,
        context=payload.context or {},
        role=role,
        user_id=str(payload.user_id or "user"),
        session_id=payload.session_id,
    )
    
    res: EngineTurnResponse = await engine.process_turn(turn_req)
    
    # Backward compatible response format for Odoo OWL Copilot Sidebar
    return {
        "response": res.message,
        "message": res.message,
        "content": res.message,
        "workflow_id": res.skill_id,
        "skill_id": res.skill_id,
        "action_cards": res.action_cards,
        "proposed_actions": res.proposed_actions,
        "patient_summary": res.patient_summary,
        "model_used": res.model_used,
        "request_id": res.request_id,
        "execution_time_ms": res.duration_ms,
    }


@app.post("/api/copilot/action/approve")
@app.post("/api/action/confirm")
async def approve_action(req: ActionRequest):
    result = await engine.confirm_action(req.action_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@app.post("/api/copilot/action/reject")
@app.post("/api/action/reject")
async def reject_action(req: ActionRequest):
    return engine.reject_action(req.action_id)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ZELIX_COPILOT_PORT", "8010"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
