"""
Zelix Copilot Backend API Gateway
FastAPI server connecting Odoo Web UI, Claude Desktop, and web agents to the AI Copilot Orchestrator.
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from providers.alamia_provider import AlamiaAIProvider
from orchestrator import CopilotRequest, CopilotResponse, ZelixCopilotOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("zelix.api")

provider = AlamiaAIProvider()
orchestrator = ZelixCopilotOrchestrator(provider=provider)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Zelix Copilot Backend...")
    health = await provider.check_health()
    logger.info(f"Alamia AI BitNet Health Status: {health.get('status')}")
    yield
    logger.info("Shutting down Zelix Copilot Backend...")


app = FastAPI(
    title="Zelix AI Copilot API Gateway",
    description="Role-Aware AI Copilot Backend for Odoo 19 & VetCairn Clinical Suite powered by Microsoft BitNet 1-bit LLMs.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Odoo web client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


class ActionApprovalRequest(BaseModel):
    action_id: str


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve standalone Zelix AI Copilot Web UI."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h2>Zelix Copilot Backend Active</h2><p>Static UI not found.</p>")


@app.get("/api/status")
async def api_status():
    """API metadata and active workflows endpoint."""
    return {
        "status": "healthy",
        "service": "Zelix Copilot Backend",
        "version": "1.0.0",
        "health": "/health",
        "docs": "/docs",
        "active_workflows": list(orchestrator.workflows.keys()),
    }


@app.get("/health")
@app.get("/api/copilot/health")
async def health_check():
    """Health check endpoint probing BitNet SLM connectivity."""
    ai_health = await orchestrator.provider.check_health()
    return {
        "status": "healthy",
        "service": "Zelix Copilot Backend",
        "ai_runtime": ai_health,
        "active_workflows": list(orchestrator.workflows.keys()),
    }


@app.post("/api/copilot/chat", response_model=CopilotResponse)
async def chat_endpoint(request: CopilotRequest):
    try:
        response = await orchestrator.process_chat(request)
        return response
    except Exception as e:
        logger.error(f"Error processing copilot chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/copilot/action/approve")
async def approve_action_endpoint(req: ActionApprovalRequest):
    result = await orchestrator.approve_and_execute_action(req.action_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@app.post("/api/copilot/action/reject")
async def reject_action_endpoint(req: ActionApprovalRequest):
    if req.action_id in orchestrator.pending_actions:
        orchestrator.pending_actions[req.action_id].status = "rejected"
        return {"success": True, "action_id": req.action_id, "status": "rejected"}
    raise HTTPException(status_code=404, detail="ActionCard not found")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ZELIX_COPILOT_PORT", "8010"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
