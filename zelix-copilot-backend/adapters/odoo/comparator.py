"""
adapters/odoo/comparator.py
Thread-safe parity comparator and telemetry collector for the ZelixVet Odoo Bridge pilot.
"""

import time
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("zelix.adapters.odoo.comparator")


class ParityDiscrepancy:
    """Represents a single discrepancy between direct and bridge outputs."""

    def __init__(
        self,
        operation: str,
        entity_type: str,
        reason: str,
        direct_summary: Any,
        bridge_summary: Any,
    ) -> None:
        self.operation = operation
        self.entity_type = entity_type
        self.reason = reason
        self.direct_summary = direct_summary
        self.bridge_summary = bridge_summary
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "entity_type": self.entity_type,
            "reason": self.reason,
            "direct": str(self.direct_summary)[:200],
            "bridge": str(self.bridge_summary)[:200],
            "timestamp": self.timestamp,
        }


class ParityComparator:
    """Compares execution results between direct and bridge backends."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_operations = 0
        self._matched_operations = 0
        self._discrepancies: List[ParityDiscrepancy] = []
        self._direct_latencies_ms: List[float] = []
        self._bridge_latencies_ms: List[float] = []

    def record_metrics(
        self,
        operation: str,
        entity_type: str,
        direct_result: Any,
        bridge_result: Any,
        direct_duration_ms: float,
        bridge_duration_ms: float,
    ) -> Tuple[bool, Optional[str]]:
        """Compare results, update statistics, and record any discrepancy."""
        is_match, reason = self.compare_results(operation, entity_type, direct_result, bridge_result)

        with self._lock:
            self._total_operations += 1
            self._direct_latencies_ms.append(direct_duration_ms)
            self._bridge_latencies_ms.append(bridge_duration_ms)

            # Keep latency windows bounded
            if len(self._direct_latencies_ms) > 1000:
                self._direct_latencies_ms = self._direct_latencies_ms[-1000:]
                self._bridge_latencies_ms = self._bridge_latencies_ms[-1000:]

            if is_match:
                self._matched_operations += 1
            else:
                disc = ParityDiscrepancy(
                    operation=operation,
                    entity_type=entity_type,
                    reason=reason or "Value mismatch",
                    direct_summary=direct_result,
                    bridge_summary=bridge_result,
                )
                self._discrepancies.append(disc)
                if len(self._discrepancies) > 200:
                    self._discrepancies.pop(0)

                logger.warning(
                    f"Parity discrepancy in {operation}:{entity_type} -> {reason} "
                    f"(direct={str(direct_result)[:80]}, bridge={str(bridge_result)[:80]})"
                )

        return is_match, reason

    def compare_results(
        self,
        operation: str,
        entity_type: str,
        direct: Any,
        bridge: Any,
    ) -> Tuple[bool, Optional[str]]:
        """Deep comparison of direct and bridge outputs."""
        if direct is None and bridge is None:
            return True, None

        if (direct is None) != (bridge is None):
            return False, f"Null mismatch: direct={direct is not None}, bridge={bridge is not None}"

        if operation in ["search", "relationships"]:
            if not isinstance(direct, list) or not isinstance(bridge, list):
                return False, f"Type mismatch: expected list, got ({type(direct).__name__}, {type(bridge).__name__})"
            if len(direct) != len(bridge):
                return False, f"Count mismatch: direct returned {len(direct)}, bridge returned {len(bridge)}"
            direct_ids = {r.get("id") for r in direct if isinstance(r, dict) and "id" in r}
            bridge_ids = {r.get("id") for r in bridge if isinstance(r, dict) and "id" in r}
            if direct_ids and bridge_ids and direct_ids != bridge_ids:
                diff = direct_ids.symmetric_difference(bridge_ids)
                return False, f"ID set mismatch on {len(diff)} records: {diff}"
            return True, None

        elif operation in ["get", "find_patient"]:
            if not isinstance(direct, dict) or not isinstance(bridge, dict):
                return False, f"Type mismatch: expected dict, got ({type(direct).__name__}, {type(bridge).__name__})"
            if direct.get("id") != bridge.get("id"):
                return False, f"Record ID mismatch: direct={direct.get('id')}, bridge={bridge.get('id')}"
            if direct.get("name") != bridge.get("name"):
                return False, f"Record name mismatch: direct='{direct.get('name')}', bridge='{bridge.get('name')}'"
            return True, None

        elif operation in ["create", "update"]:
            if not isinstance(direct, dict) or not isinstance(bridge, dict):
                return False, f"Type mismatch: expected dict, got ({type(direct).__name__}, {type(bridge).__name__})"
            if "status" in direct and "status" in bridge:
                if direct["status"] != bridge["status"]:
                    return False, f"Status mismatch: direct={direct['status']}, bridge={bridge['status']}"
            return True, None

        elif operation == "delete":
            if bool(direct) != bool(bridge):
                return False, f"Delete outcome mismatch: direct={direct}, bridge={bridge}"
            return True, None

        elif operation == "identity":
            if not isinstance(direct, dict) or not isinstance(bridge, dict):
                return False, f"Type mismatch for identity: ({type(direct).__name__}, {type(bridge).__name__})"
            if direct.get("id") != bridge.get("id"):
                return False, f"Identity ID mismatch: direct={direct.get('id')}, bridge={bridge.get('id')}"
            return True, None

        # General equality fallback
        if direct == bridge:
            return True, None
        return False, f"Direct value differs from bridge"

    def get_summary(self) -> Dict[str, Any]:
        """Return real-time parity telemetry summary."""
        with self._lock:
            total = self._total_operations
            matched = self._matched_operations
            rate = (matched / total * 100.0) if total > 0 else 100.0
            avg_direct_lat = (sum(self._direct_latencies_ms) / len(self._direct_latencies_ms)) if self._direct_latencies_ms else 0.0
            avg_bridge_lat = (sum(self._bridge_latencies_ms) / len(self._bridge_latencies_ms)) if self._bridge_latencies_ms else 0.0

            return {
                "total_operations": total,
                "matched_operations": matched,
                "discrepancy_count": len(self._discrepancies),
                "parity_rate_pct": round(rate, 2),
                "avg_direct_latency_ms": round(avg_direct_lat, 2),
                "avg_bridge_latency_ms": round(avg_bridge_lat, 2),
                "recent_discrepancies": [d.to_dict() for d in self._discrepancies[-10:]],
            }

    def reset(self) -> None:
        """Reset internal metrics."""
        with self._lock:
            self._total_operations = 0
            self._matched_operations = 0
            self._discrepancies.clear()
            self._direct_latencies_ms.clear()
            self._bridge_latencies_ms.clear()
