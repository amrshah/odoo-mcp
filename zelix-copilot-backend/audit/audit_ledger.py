"""
Clinical AI Audit Ledger
Captures comprehensive traces for every AI inference, validation check, human approval, and Odoo persistence action.
"""

import time
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("zelix.audit")


class AuditTrace(BaseModel):
    request_id: str
    timestamp: float = Field(default_factory=time.time)
    user_uid: int
    role: str
    workflow_id: str
    model_used: str
    input_text: str
    routed_intent: str
    validation_status: str  # "passed", "failed", "skipped"
    validation_errors: List[str] = []
    proposed_actions: List[Dict[str, Any]] = []
    approval_status: str = "pending"  # "pending", "approved", "rejected"
    mcp_operation: Optional[str] = None
    odoo_record_id: Optional[int] = None
    read_back_verification: Optional[Dict[str, Any]] = None
    final_status: str  # "success", "rejected", "validation_failed", "execution_failed"
    duration_ms: Optional[float] = None


class AuditLedger:
    """In-memory audit trail and structured logger for clinical safety compliance."""

    def __init__(self):
        self.traces: Dict[str, AuditTrace] = {}

    def record_trace(self, trace: AuditTrace) -> None:
        self.traces[trace.request_id] = trace
        logger.info(
            f"[AUDIT] Request: {trace.request_id} | Role: {trace.role} | Workflow: {trace.workflow_id} | "
            f"Validation: {trace.validation_status} | Final: {trace.final_status} | Odoo Record: {trace.odoo_record_id}"
        )

    def get_trace(self, request_id: str) -> Optional[AuditTrace]:
        return self.traces.get(request_id)
