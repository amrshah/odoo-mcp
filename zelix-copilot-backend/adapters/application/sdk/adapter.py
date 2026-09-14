"""SDK Application Adapter.

Implements ApplicationAdapter by wrapping a native Python SDK or client library.
"""

from typing import Any, Dict, List, Optional
from adapters.application.base.adapter import ApplicationAdapter


class SDKApplicationAdapter(ApplicationAdapter):
    """Application adapter wrapping an in-process SDK client instance."""

    def __init__(self, sdk_client: Any) -> None:
        self.sdk = sdk_client

    def identity(self, user_id: str) -> Optional[Dict[str, Any]]:
        if hasattr(self.sdk, "get_user"):
            return self.sdk.get_user(user_id)
        return {"id": user_id}

    def permissions(self, user_id: str) -> List[str]:
        if hasattr(self.sdk, "get_permissions"):
            return self.sdk.get_permissions(user_id)
        return []

    def search(
        self,
        entity_type: str,
        query: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        method_name = f"search_{entity_type}"
        if hasattr(self.sdk, method_name):
            return getattr(self.sdk, method_name)(query or {}, limit=limit)
        return []

    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        method_name = f"get_{entity_type}"
        if hasattr(self.sdk, method_name):
            return getattr(self.sdk, method_name)(entity_id)
        return None

    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        method_name = f"create_{entity_type}"
        if hasattr(self.sdk, method_name):
            return getattr(self.sdk, method_name)(data)
        return data

    def update(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        method_name = f"update_{entity_type}"
        if hasattr(self.sdk, method_name):
            return getattr(self.sdk, method_name)(entity_id, data)
        return data

    def delete(self, entity_type: str, entity_id: str) -> bool:
        method_name = f"delete_{entity_type}"
        if hasattr(self.sdk, method_name):
            return getattr(self.sdk, method_name)(entity_id)
        return True

    def execute(
        self,
        action_type: str,
        target: Dict[str, Any],
        proposed_changes: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if hasattr(self.sdk, "execute_action"):
            return self.sdk.execute_action(action_type, target, proposed_changes, metadata or {})
        return {"status": "success", "action": action_type}

    def relationships(
        self,
        entity_type: str,
        entity_id: str,
        relation_name: str,
    ) -> List[Dict[str, Any]]:
        method_name = f"get_{entity_type}_{relation_name}"
        if hasattr(self.sdk, method_name):
            return getattr(self.sdk, method_name)(entity_id)
        return []

    def audit(self, entry: Dict[str, Any]) -> None:
        if hasattr(self.sdk, "log_audit"):
            self.sdk.log_audit(entry)
