"""
core/audit/ledger.py
Structured append-only audit ledger for compliance, validation traces, and safety audits.
"""

import time
import uuid
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("zelix.core.audit")


class AuditTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid.uuid4().hex[:10]}")
    request_id: str
    user_id: str
    tenant_id: str = "default"
    role: str
    skill_id: str
    model_used: str
    query_text: str
    response_text: str = ""
    proposed_actions_count: int = 0
    validation_status: str = "passed"
    final_status: str = "success"
    duration_ms: float = 0.0
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditLedger:
    """In-memory append-only audit log with persistence hooks."""

    def __init__(self) -> None:
        self._traces: List[AuditTrace] = []

    def record(self, trace: AuditTrace) -> None:
        self._traces.append(trace)
        logger.info(
            f"[AUDIT] Request: {trace.request_id} | Role: {trace.role} | Skill: {trace.skill_id} | "
            f"Actions: {trace.proposed_actions_count} | Status: {trace.final_status} ({trace.duration_ms:.1f}ms)"
        )

    def get_traces(self, limit: int = 50) -> List[AuditTrace]:
        return self._traces[-limit:]
