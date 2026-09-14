"""REST Application Adapter.

Implements ApplicationAdapter by forwarding operations to standard HTTP REST API endpoints.
"""

from typing import Any, Callable, Dict, List, Optional
from adapters.application.base.adapter import ApplicationAdapter


class RESTApplicationAdapter(ApplicationAdapter):
    """Application adapter connecting to host application via REST endpoints."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api",
        http_client: Optional[Callable[[str, str, Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        self.base_url = base_url
        self._http_client = http_client or self._mock_http

    def _mock_http(self, method: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Mock HTTP dispatcher for testing and development."""
        return {"status": 200, "data": {"method": method, "path": path, "payload": payload}}

    def identity(self, user_id: str) -> Optional[Dict[str, Any]]:
        resp = self._http_client("GET", f"/users/{user_id}", {})
        return resp.get("data")

    def permissions(self, user_id: str) -> List[str]:
        resp = self._http_client("GET", f"/users/{user_id}/permissions", {})
        return resp.get("data", {}).get("permissions", [])

    def search(
        self,
        entity_type: str,
        query: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        resp = self._http_client("GET", f"/{entity_type}", {"query": query or {}, "limit": limit})
        res_data = resp.get("data", [])
        return res_data if isinstance(res_data, list) else []

    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        resp = self._http_client("GET", f"/{entity_type}/{entity_id}", {})
        return resp.get("data")

    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._http_client("POST", f"/{entity_type}", data)
        return resp.get("data", data)

    def update(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._http_client("PUT", f"/{entity_type}/{entity_id}", data)
        return resp.get("data", data)

    def delete(self, entity_type: str, entity_id: str) -> bool:
        resp = self._http_client("DELETE", f"/{entity_type}/{entity_id}", {})
        return resp.get("status") in (200, 204)

    def execute(
        self,
        action_type: str,
        target: Dict[str, Any],
        proposed_changes: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        payload = {
            "action": action_type,
            "target": target,
            "changes": proposed_changes,
            "metadata": metadata or {},
        }
        resp = self._http_client("POST", f"/actions/{action_type}", payload)
        return resp.get("data", {"status": "success"})

    def relationships(
        self,
        entity_type: str,
        entity_id: str,
        relation_name: str,
    ) -> List[Dict[str, Any]]:
        resp = self._http_client("GET", f"/{entity_type}/{entity_id}/{relation_name}", {})
        res_data = resp.get("data", [])
        return res_data if isinstance(res_data, list) else []

    def audit(self, entry: Dict[str, Any]) -> None:
        self._http_client("POST", "/audit", entry)
