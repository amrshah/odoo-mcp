"""
core/runtime/engine.py
Master CopilotEngine orchestrating context, skills, tools, policies, HITL gates, and audit trails.
"""

import time
import uuid
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.sessions.context import EmployeeContext
from core.actions.proposal import ActionProposal, ActionStatus
from core.skills.registry import SkillRegistry
from core.tools.registry import ToolRegistry
from core.roles.registry import RoleRegistry
from core.policies.engine import PolicyEngine
from core.audit.ledger import AuditLedger, AuditTrace
from core.ai.router import AIModelRouter
from adapters.application.base.adapter import ApplicationAdapter

logger = logging.getLogger("zelix.core.engine")


class EngineTurnRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None
    role: str = "veterinarian"
    user_id: Optional[str] = "admin"
    user_uid: Optional[int] = 2
    session_id: Optional[str] = None


class EngineTurnResponse(BaseModel):
    message: str
    skill_id: str
    proposed_actions: List[Dict[str, Any]] = Field(default_factory=list)
    action_cards: List[Dict[str, Any]] = Field(default_factory=list)
    patient_summary: Optional[Dict[str, Any]] = None
    model_used: str = "Alamia-SLM"
    request_id: str
    duration_ms: float = 0.0


class CopilotEngine:
    """Enterprise Copilot Engine enforcing Clean Core principles."""

    def __init__(
        self,
        skill_registry: SkillRegistry,
        tool_registry: ToolRegistry,
        role_registry: Optional[RoleRegistry] = None,
        policy_engine: Optional[PolicyEngine] = None,
        ai_router: Optional[AIModelRouter] = None,
        application_adapter: Optional[ApplicationAdapter] = None,
        audit_ledger: Optional[AuditLedger] = None,
    ) -> None:
        self.skills = skill_registry
        self.tools = tool_registry
        self.roles = role_registry or RoleRegistry()
        self.policies = policy_engine or PolicyEngine()
        self.ai_router = ai_router
        self.adapter = application_adapter
        self.audit_ledger = audit_ledger or AuditLedger()
        self.pending_actions: Dict[str, ActionProposal] = {}

    def _resolve_context(self, request: EngineTurnRequest) -> EmployeeContext:
        ctx_data = request.context or {}
        role_manifest = self.roles.get(request.role)
        permissions = list(role_manifest.permissions) if role_manifest else ["all"]

        return EmployeeContext(
            user_id=request.user_id or "user",
            user_uid=request.user_uid or 2,
            role=request.role,
            permissions=permissions,
            active_model=ctx_data.get("model"),
            active_record_id=ctx_data.get("record_id"),
            patient_context=ctx_data.get("patient_summary"),
            census_context=ctx_data.get("census"),
            matched_rules=ctx_data.get("matched_rules", []),
            conversation_id=request.session_id,
        )

    def _route_intent(self, query: str, context: EmployeeContext) -> str:
        q = query.lower()
        if any(w in q for w in ["prescribe", "prescription", "rx", "dosage", "medication", "drug"]):
            return "prescription_assistant"
        elif any(w in q for w in ["soap", "consult", "consultation", "scribe", "dictation", "physical exam"]):
            return "voice_to_soap"
        elif any(w in q for w in ["census", "activity", "appointments", "operations", "schedule", "summary of today"]):
            return "clinic_activity"
        elif any(w in q for w in ["patient", "history", "summarize", "360", "brief", "case"]):
            return "patient_360"
        return "patient_360"

    async def process_turn(self, request: EngineTurnRequest) -> EngineTurnResponse:
        t0 = time.time()
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        context = self._resolve_context(request)

        skill_id = self._route_intent(request.query, context)
        skill = self.skills.get(skill_id)

        if not skill:
            skill = self.skills.get("patient_360") or list(self.skills.list_all())[0]

        # Get accessible tools
        accessible_tools = self.tools.get_accessible_tools(context)

        # Execute Skill
        provider = self.ai_router.get_provider_for_skill(skill_id) if self.ai_router else None
        result = await skill.execute(
            context=context,
            tools=accessible_tools,
            ai_provider=provider,
            user_input=request.query,
        )

        # Policy & Confirmation Evaluation
        final_actions = []
        for action_dict in result.proposed_actions:
            proposal = ActionProposal(**action_dict)
            proposal = self.policies.evaluate_action(context, proposal)
            self.pending_actions[proposal.action_id] = proposal
            final_actions.append(proposal.model_dump())

        duration_ms = (time.time() - t0) * 1000

        # Audit Logging
        self.audit_ledger.record(
            AuditTrace(
                request_id=req_id,
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                role=context.role,
                skill_id=skill.definition.id,
                model_used=result.metadata.get("model", "Alamia-SLM"),
                query_text=request.query,
                response_text=result.response_text,
                proposed_actions_count=len(final_actions),
                duration_ms=duration_ms,
            )
        )

        return EngineTurnResponse(
            message=result.response_text,
            skill_id=skill.definition.id,
            proposed_actions=final_actions,
            action_cards=final_actions,
            patient_summary=context.patient_context,
            model_used=result.metadata.get("model", "Alamia-SLM"),
            request_id=req_id,
            duration_ms=duration_ms,
        )

    async def confirm_action(self, action_id: str) -> Dict[str, Any]:
        """Executes approved ActionProposal against application adapter with read-back verification."""
        proposal = self.pending_actions.get(action_id)
        if not proposal:
            return {"success": False, "error": f"ActionProposal '{action_id}' not found."}

        if not self.adapter:
            return {"success": False, "error": "No ApplicationAdapter configured."}

        try:
            target_model = proposal.target_model or proposal.action_type
            payload = proposal.payload or proposal.proposed_changes

            # 1. Execute Write
            res = self.adapter.create(target_model, payload)
            rec_id = res.get("id")

            # 2. Assert Read-Back
            read_back = self.adapter.get(target_model, str(rec_id))
            if not read_back:
                raise RuntimeError(f"Read-back assertion failed for created {target_model} ID {rec_id}")

            proposal.status = ActionStatus.EXECUTED
            proposal.execution_result = {"id": rec_id, "model": target_model, "verified": True}

            return {
                "success": True,
                "action_id": action_id,
                "status": "executed",
                "record_id": rec_id,
                "target_model": target_model,
                "verified": True,
            }
        except Exception as e:
            logger.error(f"Error executing action {action_id}: {e}")
            proposal.status = ActionStatus.FAILED
            return {"success": False, "error": str(e)}

    def reject_action(self, action_id: str) -> Dict[str, Any]:
        proposal = self.pending_actions.get(action_id)
        if proposal:
            proposal.status = ActionStatus.REJECTED
            return {"success": True, "action_id": action_id, "status": "rejected"}
        return {"success": False, "error": "ActionProposal not found"}
