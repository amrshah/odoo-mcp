"""
Zelix Copilot Master Orchestrator
Coordinates Role Policy, Dynamic Context Extraction, Intent Routing, Schema Validation, Human Approval, and Strict Odoo Read-Back Verification.
"""

import os
import sys
import uuid
import time
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from providers.alamia_provider import AlamiaAIProvider
from roles.policy import ClinicalRole, RoleResolver
from context.context_engine import ActiveContext, ContextEngine
from router.intent_router import IntentRouter, TargetWorkflow
from audit.audit_ledger import AuditLedger, AuditTrace
from workflows.base_workflow import ActionCard, BaseWorkflow, WorkflowResult
from workflows.practice_query import PracticeQueryWorkflow
from workflows.ambient_scribe_soap import AmbientScribeSOAPWorkflow
from workflows.pre_consult_brief import PreConsultBriefWorkflow
from workflows.patient_summary import PatientSummaryWorkflow
from workflows.prescription_assistant import PrescriptionAssistantWorkflow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server"))
from odoo_client import OdooClient

logger = logging.getLogger("zelix.orchestrator")


class CopilotRequest(BaseModel):
    message: str
    context: Optional[ActiveContext] = None
    role: Optional[str] = "veterinarian"
    session_id: Optional[str] = None


class CopilotResponse(BaseModel):
    response: str
    workflow_id: str
    action_cards: List[ActionCard] = []
    patient_summary: Optional[Dict[str, Any]] = None
    model_used: str
    request_id: str
    execution_time_ms: Optional[float] = None


class ZelixCopilotOrchestrator:
    """Master controller for Zelix AI Copilot enforcing the 12-stage AI safety pipeline."""

    def __init__(
        self,
        provider: Optional[AlamiaAIProvider] = None,
        odoo_client: Optional[OdooClient] = None,
    ):
        self.provider = provider or AlamiaAIProvider()
        self.odoo_client = odoo_client or OdooClient()
        self.context_engine = ContextEngine(self.odoo_client)
        self.audit_ledger = AuditLedger()

        # Registered Workflows
        self.workflows: Dict[str, BaseWorkflow] = {
            "w00_practice_query": PracticeQueryWorkflow(),
            "w04_scribe_soap": AmbientScribeSOAPWorkflow(),
            "w02_pre_consult_brief": PreConsultBriefWorkflow(),
            "w01_patient_summary": PatientSummaryWorkflow(),
            "w09_prescription_assistant": PrescriptionAssistantWorkflow(),
        }

        # In-Memory Action Card Registry (for Pending Approvals)
        self.pending_actions: Dict[str, ActionCard] = {}

    async def process_chat(self, request: CopilotRequest) -> CopilotResponse:
        """Main safety pipeline: Role -> Context -> Intent Classification -> Model -> Schema Validation -> Action Proposal."""
        t0 = time.time()
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        ctx = request.context or ActiveContext()
        role = ClinicalRole(request.role) if request.role in [r.value for r in ClinicalRole] else ClinicalRole.VETERINARIAN
        policy = RoleResolver.get_policy(role)

        # 1. Resolve Patient ID and build clinical context
        patient_id = self.context_engine.resolve_patient_id(ctx)
        patient_summary = None
        context_prompt = ""

        if patient_id:
            ctx.patient_id = patient_id
            patient_summary = self.context_engine.fetch_patient_context(patient_id)
            if patient_summary:
                # Attach summary object to context for workflows
                ctx_dict = ctx.model_dump()
                setattr(ctx, "patient_summary_obj", patient_summary)
                context_prompt = self.context_engine.format_context_prompt(patient_summary)

        if not context_prompt:
            context_prompt = "No specific active patient record linked. Providing general veterinary clinical assistance."

        # 2. Intent Classification via IntentRouter
        intent_res = IntentRouter.classify(request.message)
        logger.info(f"Classified intent: {intent_res.workflow.value} (Confidence: {intent_res.confidence}, Reason: {intent_res.reason})")

        if intent_res.workflow == TargetWorkflow.ASK_CLARIFICATION:
            duration_ms = (time.time() - t0) * 1000
            clarification_msg = (
                "I am not completely sure what clinical action you would like me to perform. "
                "Could you please clarify? For example:\n"
                "- *'Document today's consultation'* or *'Generate SOAP note'*\n"
                "- *'Prepare me for this patient'* (Pre-Consult Brief)\n"
                "- *'Prescribe [medication name and dose]'*\n"
                "- *'Summarize patient history'*"
            )
            return CopilotResponse(
                response=clarification_msg,
                workflow_id="ask_clarification",
                action_cards=[],
                patient_summary=patient_summary.model_dump() if patient_summary else None,
                model_used="none",
                request_id=request_id,
                execution_time_ms=duration_ms,
            )

        workflow_id = intent_res.workflow.value
        workflow = self.workflows.get(workflow_id, self.workflows["w04_scribe_soap"])

        # 3. Execute Workflow with BitNet / SLM
        result: WorkflowResult = await workflow.execute(
            user_input=request.message,
            context_prompt=context_prompt,
            active_context=ctx,
            provider=self.provider,
            odoo_client=self.odoo_client,
        )

        # 4. Register Action Cards for Approval Gate
        for card in result.action_cards:
            self.pending_actions[card.action_id] = card

        duration_ms = (time.time() - t0) * 1000

        # 5. Audit Logging
        self.audit_ledger.record_trace(
            AuditTrace(
                request_id=request_id,
                user_uid=ctx.user_uid,
                role=role.value,
                workflow_id=workflow_id,
                model_used=result.metadata.get("model", self.provider.default_model),
                input_text=request.message,
                routed_intent=intent_res.workflow.value,
                validation_status="failed" if result.metadata.get("validation_errors") else "passed",
                validation_errors=result.metadata.get("validation_errors", []),
                proposed_actions=[c.model_dump() for c in result.action_cards],
                final_status="proposed" if result.action_cards else "success",
                duration_ms=duration_ms,
            )
        )

        return CopilotResponse(
            response=result.response_text,
            workflow_id=result.workflow_id,
            action_cards=result.action_cards,
            patient_summary=patient_summary.model_dump() if patient_summary else None,
            model_used=result.metadata.get("model", self.provider.default_model),
            request_id=request_id,
            execution_time_ms=duration_ms,
        )

    async def approve_and_execute_action(self, action_id: str) -> Dict[str, Any]:
        """
        Executes an approved Action Card directly against Odoo via MCP / XML-RPC layer
        with mandatory strict Read-Back Persistence Verification.
        """
        card = self.pending_actions.get(action_id)
        if not card:
            return {"success": False, "error": f"ActionCard '{action_id}' not found or expired."}

        try:
            target_model = card.target_model
            method = card.target_method
            payload = card.payload

            # Stage 1: Write / Create Operation
            if method == "create":
                record_id = self.odoo_client.create(target_model, payload)
            elif method == "write":
                record_id = payload.get("id") or card.preview_data.get("id")
                clean_payload = {k: v for k, v in payload.items() if k != "id"}
                self.odoo_client.write(target_model, [record_id], clean_payload)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}

            if not record_id:
                return {"success": False, "error": "Odoo create/write returned no record ID."}

            # Stage 2: Strict Read-Back Verification
            # Query the exact record back from Odoo database
            fields_to_read = ["id", "display_name", "create_date"]
            if target_model == "vet.encounter":
                fields_to_read.extend(["patient_id", "appointment_id", "chief_complaint", "state"])
            elif target_model == "vet.prescription":
                fields_to_read.extend(["patient_id", "medication_id", "dose", "frequency", "state"])
            elif target_model == "vet.appointment":
                fields_to_read.extend(["patient_id", "name", "state"])

            read_back_records = self.odoo_client.read(target_model, [record_id], fields_to_read)

            # ASSERTION 1: Result must be a non-empty list with exactly 1 record
            if not read_back_records or len(read_back_records) != 1:
                logger.error(f"[VERIFICATION FAILED] Read-back for {target_model} #{record_id} returned empty or invalid: {read_back_records}")
                return {
                    "success": False,
                    "error": f"Read-back persistence verification failed: Record #{record_id} not found in database.",
                    "read_back_result": read_back_records,
                }

            persisted = read_back_records[0]

            # ASSERTION 2: Returned ID must strictly match
            if persisted.get("id") != record_id:
                return {
                    "success": False,
                    "error": f"Read-back record ID mismatch: Expected {record_id}, got {persisted.get('id')}",
                }

            card.status = "executed"
            logger.info(f"[PERSISTENCE VERIFIED] Successfully created & verified {target_model} record #{record_id} in Odoo.")

            return {
                "success": True,
                "action_id": action_id,
                "model": target_model,
                "record_id": record_id,
                "verified_record": persisted,
                "message": f"Successfully created and verified {target_model} record #{record_id} in Odoo.",
            }

        except Exception as e:
            logger.error(f"Failed to execute ActionCard {action_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
