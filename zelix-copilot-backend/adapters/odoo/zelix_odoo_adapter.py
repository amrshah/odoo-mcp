"""
adapters/odoo/zelix_odoo_adapter.py
Bridges Alamia Copilot Starter Engine to Odoo 19 (VetCairn & Stratos HMS) via XML-RPC.
Strictly implements ApplicationAdapter with an explicit MODEL_MAP allowlist.
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
            if entity_type in self.MODEL_MAP.values():
                return entity_type
            raise ValueError(f"Entity type '{entity_type}' is not allowlisted in ZelixOdooAdapter.")
        return model

    def _ensure_authenticated(self) -> int:
        if not self.user_id or self.user_id == 0:
            try:
                common = xmlrpc.client.ServerProxy(self.common_endpoint, allow_none=True)
                uid = common.authenticate(self.db, self.username, self.api_key, {})
                if uid:
                    self.user_id = uid
            except Exception as e:
                logger.warning(f"Could not authenticate with Odoo: {e}")
        return self.user_id

    def identity(self, user_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_authenticated()
        try:
            uid = int(user_id) if str(user_id).isdigit() else self.user_id
            rec = self.models.execute_kw(self.db, self.user_id, self.api_key, "res.users", "read", [[uid], ["id", "name", "login", "email"]])
            return rec[0] if rec else {"id": uid, "name": "Clinician"}
        except Exception:
            return {"id": user_id, "name": "Clinician", "role": "veterinarian"}

    def permissions(self, user_id: str) -> List[str]:
        return [
            "patients.read", "patients.write",
            "medical_records.read", "medical_records.write",
            "prescriptions.read", "prescriptions.write",
            "inventory.read", "clinic_operations.read",
        ]

    def search(
        self,
        entity_type: str,
        query: Optional[Dict[str, Any]] = None,
        limit: int = 100,
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
                self.db, self.user_id, self.api_key,
                model, "search_read", [domain], {"limit": limit}
            )
        except Exception as e:
            logger.error(f"Error searching {model}: {e}")
            return []

    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        model = self._get_model(entity_type)
        self._ensure_authenticated()
        try:
            records = self.models.execute_kw(
                self.db, self.user_id, self.api_key,
                model, "read", [[int(entity_id)]]
            )
            return records[0] if records else None
        except Exception as e:
            logger.error(f"Error fetching {model} ID {entity_id}: {e}")
            return None

    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        model = self._get_model(entity_type)
        self._ensure_authenticated()
        try:
            rec_id = self.models.execute_kw(
                self.db, self.user_id, self.api_key,
                model, "create", [data]
            )
            return {"id": rec_id, "status": "created", "model": model}
        except Exception as e:
            logger.error(f"Error creating in {model}: {e}")
            raise

    def update(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        model = self._get_model(entity_type)
        self._ensure_authenticated()
        try:
            self.models.execute_kw(
                self.db, self.user_id, self.api_key,
                model, "write", [[int(entity_id)], data]
            )
            return {"id": int(entity_id), "status": "updated", "model": model}
        except Exception as e:
            logger.error(f"Error updating {model} ID {entity_id}: {e}")
            raise

    def delete(self, entity_type: str, entity_id: str) -> bool:
        model = self._get_model(entity_type)
        self._ensure_authenticated()
        try:
            return bool(
                self.models.execute_kw(
                    self.db, self.user_id, self.api_key,
                    model, "unlink", [[int(entity_id)]]
                )
            )
        except Exception as e:
            logger.error(f"Error deleting from {model}: {e}")
            return False

    def execute(
        self,
        action_type: str,
        target: Dict[str, Any],
        proposed_changes: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        entity_type = target.get("type", "patient")
        target_id = target.get("id")

        if action_type in ["create_soap_encounter", "create_encounter"]:
            return self.create("encounter", proposed_changes)
        elif action_type in ["create_prescription", "issue_prescription"]:
            return self.create("prescription", proposed_changes)
        elif target_id:
            return self.update(entity_type, str(target_id), proposed_changes)
        else:
            return self.create(entity_type, proposed_changes)

    def relationships(
        self,
        entity_type: str,
        entity_id: str,
        relation_name: str,
    ) -> List[Dict[str, Any]]:
        if entity_type == "patient":
            if relation_name == "vaccinations":
                return self.search("vaccination", {"patient_id": int(entity_id)})
            elif relation_name == "encounters":
                return self.search("encounter", {"patient_id": int(entity_id)})
            elif relation_name == "prescriptions":
                return self.search("prescription", {"patient_id": int(entity_id)})
        return []

    def audit(self, entry: Dict[str, Any]) -> None:
        try:
            self._ensure_authenticated()
            if "zelix.copilot.audit" in self.MODEL_MAP.values():
                pass
        except Exception:
            pass
