"""
adapters/odoo/zelix_odoo_adapter.py
Dual-mode ApplicationAdapter supporting controlled side-by-side pilot testing
between the legacy direct XML-RPC backend and the canonical Alamia OdooBridge backend.
"""

import os
import time
import logging
from typing import Any, Dict, List, Optional

from adapters.application.base.adapter import ApplicationAdapter
from .direct_backend import DirectOdooBackend
from .bridge_backend import BridgeOdooBackend
from .comparator import ParityComparator

logger = logging.getLogger("zelix.adapters.odoo")


class ZelixOdooAdapter(ApplicationAdapter):
    """Unified application adapter with dual-mode shadow execution for the Odoo Bridge pilot."""

    MODEL_MAP = DirectOdooBackend.MODEL_MAP

    def __init__(
        self,
        url: Optional[str] = None,
        db: Optional[str] = None,
        user_id: Optional[int] = None,
        api_key: Optional[str] = None,
        mode: Optional[str] = None,
        comparator: Optional[ParityComparator] = None,
        shadow_writes: bool = False,
    ) -> None:
        raw_mode = (mode or os.getenv("ZELIX_ODOO_PILOT_MODE", "dual")).strip().lower()
        if raw_mode not in ["direct", "bridge", "dual"]:
            logger.warning(f"Invalid ZELIX_ODOO_PILOT_MODE='{raw_mode}'; falling back to 'dual'")
            raw_mode = "dual"
        self.mode = raw_mode
        self.shadow_writes = shadow_writes or (os.getenv("ZELIX_ODOO_SHADOW_WRITES", "false").lower() == "true")

        self.direct = DirectOdooBackend(
            url=url,
            db=db,
            user_id=user_id,
            api_key=api_key,
        )
        self.bridge = BridgeOdooBackend(
            url=url,
            db=db,
            username=self.direct.username,
            password=self.direct.api_key,
        )
        self.comparator = comparator or ParityComparator()
        logger.info(f"Initialized ZelixOdooAdapter in '{self.mode}' mode (shadow_writes={self.shadow_writes})")

    @property
    def models(self):
        """Legacy direct ServerProxy accessor for backward compatibility."""
        return self.direct.models

    def _get_model(self, entity_type: str) -> str:
        """Enforces MODEL_MAP allowlist lookup (backward compatibility)."""
        return self.direct.get_model(entity_type)

    def get_model(self, entity_type: str) -> str:
        """Enforces MODEL_MAP allowlist lookup."""
        return self.direct.get_model(entity_type)

    def set_mode(self, mode: str) -> None:
        """Switch active adapter routing mode."""
        m = mode.strip().lower()
        if m in ["direct", "bridge", "dual"]:
            self.mode = m
            logger.info(f"ZelixOdooAdapter mode switched to '{self.mode}'")
        else:
            raise ValueError(f"Invalid mode '{mode}'. Choose from 'direct', 'bridge', 'dual'.")

    def get_parity_telemetry(self) -> Dict[str, Any]:
        """Expose current parity match rate and latency metrics."""
        return self.comparator.get_summary()

    def reset_parity_telemetry(self) -> None:
        """Reset parity telemetry counters."""
        self.comparator.reset()

    # -------------------------------------------------------------------------
    # ApplicationAdapter API Implementation
    # -------------------------------------------------------------------------

    def identity(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.mode == "direct":
            return self.direct.identity(user_id)
        elif self.mode == "bridge":
            return self.bridge.identity(user_id)
        else:
            # Dual shadow mode
            t0 = time.perf_counter()
            direct_res = self.direct.identity(user_id)
            d_ms = (time.perf_counter() - t0) * 1000.0

            t1 = time.perf_counter()
            try:
                bridge_res = self.bridge.identity(user_id)
            except Exception as e:
                bridge_res = None
                logger.debug(f"Shadow bridge.identity failed: {e}")
            b_ms = (time.perf_counter() - t1) * 1000.0

            self.comparator.record_metrics("identity", "res.users", direct_res, bridge_res, d_ms, b_ms)
            return direct_res

    def permissions(self, user_id: str) -> List[str]:
        if self.mode == "bridge":
            return self.bridge.permissions(user_id)
        return self.direct.permissions(user_id)

    def search(
        self,
        entity_type: str,
        query: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self.mode == "direct":
            return self.direct.search(entity_type, query, limit)
        elif self.mode == "bridge":
            return self.bridge.search(entity_type, query, limit)
        else:
            # Dual shadow mode
            t0 = time.perf_counter()
            direct_res = self.direct.search(entity_type, query, limit)
            d_ms = (time.perf_counter() - t0) * 1000.0

            t1 = time.perf_counter()
            try:
                bridge_res = self.bridge.search(entity_type, query, limit)
            except Exception as e:
                bridge_res = []
                logger.debug(f"Shadow bridge.search failed on {entity_type}: {e}")
            b_ms = (time.perf_counter() - t1) * 1000.0

            self.comparator.record_metrics("search", entity_type, direct_res, bridge_res, d_ms, b_ms)
            return direct_res

    def find_patient(self, search_term: str) -> Optional[Dict[str, Any]]:
        if self.mode == "direct":
            return self.direct.find_patient(search_term)
        elif self.mode == "bridge":
            return self.bridge.find_patient(search_term)
        else:
            # Dual shadow mode
            t0 = time.perf_counter()
            direct_res = self.direct.find_patient(search_term)
            d_ms = (time.perf_counter() - t0) * 1000.0

            t1 = time.perf_counter()
            try:
                bridge_res = self.bridge.find_patient(search_term)
            except Exception as e:
                bridge_res = None
                logger.debug(f"Shadow bridge.find_patient failed for '{search_term}': {e}")
            b_ms = (time.perf_counter() - t1) * 1000.0

            self.comparator.record_metrics("find_patient", "patient", direct_res, bridge_res, d_ms, b_ms)
            return direct_res

    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        if self.mode == "direct":
            return self.direct.get(entity_type, entity_id)
        elif self.mode == "bridge":
            return self.bridge.get(entity_type, entity_id)
        else:
            # Dual shadow mode
            t0 = time.perf_counter()
            direct_res = self.direct.get(entity_type, entity_id)
            d_ms = (time.perf_counter() - t0) * 1000.0

            t1 = time.perf_counter()
            try:
                bridge_res = self.bridge.get(entity_type, entity_id)
            except Exception as e:
                bridge_res = None
                logger.debug(f"Shadow bridge.get failed on {entity_type} ID {entity_id}: {e}")
            b_ms = (time.perf_counter() - t1) * 1000.0

            self.comparator.record_metrics("get", entity_type, direct_res, bridge_res, d_ms, b_ms)
            return direct_res

    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mode == "bridge":
            return self.bridge.create(entity_type, data)
        elif self.mode == "direct" or not self.shadow_writes:
            return self.direct.create(entity_type, data)
        else:
            # Dual mode with shadow writes enabled (e.g. test environment)
            t0 = time.perf_counter()
            direct_res = self.direct.create(entity_type, data)
            d_ms = (time.perf_counter() - t0) * 1000.0

            t1 = time.perf_counter()
            try:
                bridge_res = self.bridge.create(entity_type, data)
            except Exception as e:
                bridge_res = {"error": str(e)}
            b_ms = (time.perf_counter() - t1) * 1000.0

            self.comparator.record_metrics("create", entity_type, direct_res, bridge_res, d_ms, b_ms)
            return direct_res

    def update(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mode == "bridge":
            return self.bridge.update(entity_type, entity_id, data)
        elif self.mode == "direct" or not self.shadow_writes:
            return self.direct.update(entity_type, entity_id, data)
        else:
            t0 = time.perf_counter()
            direct_res = self.direct.update(entity_type, entity_id, data)
            d_ms = (time.perf_counter() - t0) * 1000.0

            t1 = time.perf_counter()
            try:
                bridge_res = self.bridge.update(entity_type, entity_id, data)
            except Exception as e:
                bridge_res = {"error": str(e)}
            b_ms = (time.perf_counter() - t1) * 1000.0

            self.comparator.record_metrics("update", entity_type, direct_res, bridge_res, d_ms, b_ms)
            return direct_res

    def delete(self, entity_type: str, entity_id: str) -> bool:
        if self.mode == "bridge":
            return self.bridge.delete(entity_type, entity_id)
        return self.direct.delete(entity_type, entity_id)

    def execute(
        self,
        action_type: str,
        target: Dict[str, Any],
        proposed_changes: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if self.mode == "bridge":
            return self.bridge.execute(action_type, target, proposed_changes, metadata)
        return self.direct.execute(action_type, target, proposed_changes, metadata)

    def relationships(
        self,
        entity_type: str,
        entity_id: str,
        relation_name: str,
    ) -> List[Dict[str, Any]]:
        if self.mode == "direct":
            return self.direct.relationships(entity_type, entity_id, relation_name)
        elif self.mode == "bridge":
            return self.bridge.relationships(entity_type, entity_id, relation_name)
        else:
            t0 = time.perf_counter()
            direct_res = self.direct.relationships(entity_type, entity_id, relation_name)
            d_ms = (time.perf_counter() - t0) * 1000.0

            t1 = time.perf_counter()
            try:
                bridge_res = self.bridge.relationships(entity_type, entity_id, relation_name)
            except Exception as e:
                bridge_res = []
                logger.debug(f"Shadow bridge.relationships failed on {entity_type} {relation_name}: {e}")
            b_ms = (time.perf_counter() - t1) * 1000.0

            self.comparator.record_metrics("relationships", f"{entity_type}.{relation_name}", direct_res, bridge_res, d_ms, b_ms)
            return direct_res

    def audit(self, entry: Dict[str, Any]) -> None:
        if self.mode == "bridge":
            self.bridge.audit(entry)
        else:
            self.direct.audit(entry)
