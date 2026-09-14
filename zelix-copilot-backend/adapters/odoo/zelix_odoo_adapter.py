"""
adapters/odoo/zelix_odoo_adapter.py
Bridges Copilot Engine to Odoo 19 via XML-RPC with an explicit MODEL_MAP allowlist.
"""

import os
import logging
import xmlrpc.client
from typing import Any, Dict, List, Optional
from adapters.application.base.adapter import ApplicationAdapter

logger = logging.getLogger("zelix.adapters.odoo")


class ZelixOdooAdapter(ApplicationAdapter):
    """Bridges Copilot Engine to Odoo 19 (VetCairn & Stratos HMS) via XML-RPC with strict model allowlisting."""

    MODEL_MAP = {
        "patient": "vet.patient",
        "hms_patient": "hms.patient",
        "vaccination": "vet.vaccination",
        "encounter": "vet.encounter",
        "appointment": "vet.appointment",
        "hms_visit": "hms.visit",
        "prescription": "vet.prescription",
        "hms_prescription": "hms.prescription",
        "product": "product.product",
        "inventory": "product.product",
        "user": "res.users",
    }

    def __init__(
        self,
        url: Optional[str] = None,
        db: Optional[str] = None,
        user_id: Optional[int] = None,
        api_key: Optional[str] = None,
    ) -> None:
        default_url = os.getenv("ODOO_LOCAL_URL") or os.getenv("ODOO_URL", "http://localhost:8069")
        if "web:" in default_url and not os.path.exists("/.dockerenv"):
            default_url = "http://localhost:8069"
        self.url = (url or default_url).rstrip("/")
        self.db = db or os.getenv("ODOO_DB", "odoo_hospital")
        self.user_id = user_id or int(os.getenv("ODOO_USER_ID", "2"))
        self.api_key = api_key or os.getenv("ODOO_PASSWORD", "zelix_service_secret_key_2026")
        self.username = os.getenv("ODOO_USERNAME", "zelix_service")

        self.common_endpoint = f"{self.url}/xmlrpc/2/common"
        self.object_endpoint = f"{self.url}/xmlrpc/2/object"
        self._models_proxy: Optional[xmlrpc.client.ServerProxy] = None

    @property
    def models(self) -> xmlrpc.client.ServerProxy:
        if self._models_proxy is None:
            self._models_proxy = xmlrpc.client.ServerProxy(self.object_endpoint, allow_none=True)
        return self._models_proxy

    def _get_model(self, entity_type: str) -> str:
        model = self.MODEL_MAP.get(entity_type.lower())
        if not model:
            # Check if entity_type is already a permitted allowlisted model name
            if entity_type in self.MODEL_MAP.values():
                return entity_type
            raise ValueError(f"Entity type '{entity_type}' is not allowlisted in ZelixOdooAdapter.")
        return model

    def _ensure_authenticated(self) -> int:
        """Ensures valid UID from Odoo."""
        if not self.user_id or self.user_id == 0:
            try:
                common = xmlrpc.client.ServerProxy(self.common_endpoint, allow_none=True)
                uid = common.authenticate(self.db, self.username, self.api_key, {})
                if uid:
                    self.user_id = uid
            except Exception as e:
                logger.warning(f"Could not authenticate with Odoo: {e}")
        return self.user_id

    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        model = self._get_model(entity_type)
        self._ensure_authenticated()
        try:
            records = self.models.execute_kw(
                self.db,
                self.user_id,
                self.api_key,
                model,
                "read",
                [[int(entity_id)]],
            )
            return records[0] if records else None
        except Exception as e:
            logger.error(f"Error fetching {model} ID {entity_id}: {e}")
            return None

    def search(
        self,
        entity_type: str,
        query: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        order: str = "id desc",
    ) -> List[Dict[str, Any]]:
        model = self._get_model(entity_type)
        self._ensure_authenticated()
        domain = []
        if query:
            for k, v in query.items():
                if isinstance(v, (list, tuple)) and len(v) == 3:
                    domain.append(list(v))
                else:
                    domain.append([k, "=", v])

        try:
            return self.models.execute_kw(
                self.db,
                self.user_id,
                self.api_key,
                model,
                "search_read",
                [domain],
                {"limit": limit, "order": order},
            )
        except Exception as e:
            logger.error(f"Error searching {model}: {e}")
            return []

    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        model = self._get_model(entity_type)
        self._ensure_authenticated()
        try:
            rec_id = self.models.execute_kw(
                self.db,
                self.user_id,
                self.api_key,
                model,
                "create",
                [data],
            )
            return {"id": rec_id, "status": "created", "model": model}
        except Exception as e:
            logger.error(f"Error creating record in {model}: {e}")
            raise

    def write(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> bool:
        model = self._get_model(entity_type)
        self._ensure_authenticated()
        try:
            return bool(
                self.models.execute_kw(
                    self.db,
                    self.user_id,
                    self.api_key,
                    model,
                    "write",
                    [[int(entity_id)], data],
                )
            )
        except Exception as e:
            logger.error(f"Error updating {model} ID {entity_id}: {e}")
            return False

    def relationships(self, entity_type: str, entity_id: str, relationship_name: str) -> List[Dict[str, Any]]:
        if entity_type == "patient":
            if relationship_name == "vaccinations":
                return self.search("vaccination", {"patient_id": int(entity_id)})
            elif relationship_name == "encounters":
                return self.search("encounter", {"patient_id": int(entity_id)})
            elif relationship_name == "prescriptions":
                return self.search("prescription", {"patient_id": int(entity_id)})
        return []
