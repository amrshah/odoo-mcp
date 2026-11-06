"""
Structured audit logger for Alamia OdooBridge.
Tracks human principal, effective Odoo identity, operation, target, and status.
"""

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("alamia_odoobridge.audit")


class AuditLogger:
    """Logs structured JSON audit events for HIPAA/GDPR compliance and operations tracking."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def log_event(
        self,
        operation: str,
        model: Optional[str] = None,
        target_ids: Optional[Any] = None,
        principal: Optional[str] = None,
        effective_user: Optional[str] = None,
        status: str = "success",
        duration_ms: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Emit a structured audit event."""
        if not self.enabled:
            return

        event = {
            "timestamp": time.time(),
            "operation": operation,
            "model": model,
            "target_ids": target_ids,
            "principal": principal or "anonymous",
            "effective_user": effective_user,
            "status": status,
            "duration_ms": round(duration_ms, 2),
            "details": details or {},
            "error": error,
        }

        if status == "success":
            logger.info("AUDIT: %s", json.dumps(event))
        else:
            logger.warning("AUDIT: %s", json.dumps(event))
