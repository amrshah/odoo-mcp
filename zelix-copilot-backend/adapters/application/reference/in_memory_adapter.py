"""In-Memory Reference Application Adapter.

Provides a standalone, framework-neutral application backend for tests and local development.
"""

from typing import Any, Dict, List, Optional
from adapters.application.base.adapter import ApplicationAdapter


class InMemoryApplicationAdapter(ApplicationAdapter):
    """In-memory reference implementation of ApplicationAdapter."""

    def __init__(self) -> None:
        self.users: Dict[str, Dict[str, Any]] = {}
        self.customers: Dict[str, Dict[str, Any]] = {}
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.invoices: Dict[str, Dict[str, Any]] = {}
        self.audit_log: List[Dict[str, Any]] = []
        self.executed_actions: List[Dict[str, Any]] = []

    def _get_store(self, entity_type: str) -> Dict[str, Dict[str, Any]]:
        stores = {
            "user": self.users,
            "users": self.users,
            "customer": self.customers,
            "customers": self.customers,
            "task": self.tasks,
            "tasks": self.tasks,
            "document": self.documents,
            "documents": self.documents,
            "invoice": self.invoices,
            "invoices": self.invoices,
        }
        if entity_type.lower() not in stores:
            raise ValueError(f"Unknown entity type: '{entity_type}'.")
        return stores[entity_type.lower()]

    def identity(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.users.get(user_id)

    def permissions(self, user_id: str) -> List[str]:
        user = self.users.get(user_id)
        if not user:
            return []
        return user.get("permissions", [])

    def search(
        self,
        entity_type: str,
        query: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        store = self._get_store(entity_type)
        results: List[Dict[str, Any]] = []
        q = query or {}

        for item in store.values():
            matches = True
            for k, v in q.items():
                if item.get(k) != v:
                    matches = False
                    break
            if matches:
                results.append(item.copy())
            if len(results) >= limit:
                break
        return results

    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        store = self._get_store(entity_type)
        item = store.get(entity_id)
        return item.copy() if item else None

    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        store = self._get_store(entity_type)
        item_id = data.get("id") or f"{entity_type}_{len(store) + 1}"
        record = data.copy()
        record["id"] = item_id
        store[item_id] = record
        return record.copy()

    def update(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        store = self._get_store(entity_type)
        if entity_id not in store:
            raise KeyError(f"Entity '{entity_type}' with ID '{entity_id}' not found.")
        store[entity_id].update(data)
        return store[entity_id].copy()

    def delete(self, entity_type: str, entity_id: str) -> bool:
        store = self._get_store(entity_type)
        if entity_id in store:
            del store[entity_id]
            return True
        return False

    def execute(
        self,
        action_type: str,
        target: Dict[str, Any],
        proposed_changes: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        target_type = target.get("type", "")
        target_id = target.get("id", "")

        execution_record = {
            "action_type": action_type,
            "target": target,
            "proposed_changes": proposed_changes,
            "metadata": metadata or {},
        }
        self.executed_actions.append(execution_record)

        if action_type == "mark_invoice_paid" or action_type == "mark_paid":
            inv = self.get("invoice", target_id)
            if inv:
                self.update("invoice", target_id, {"status": "paid"})
            return {"status": "success", "action": action_type, "invoice_id": target_id}

        elif action_type == "create_followup" or action_type == "create_task":
            new_task = self.create("task", {
                "id": proposed_changes.get("id", f"task_{len(self.tasks) + 1}"),
                "title": proposed_changes.get("title", f"Followup for {target_id}"),
                "description": proposed_changes.get("description", ""),
                "status": "pending",
            })
            return {"status": "success", "task": new_task}

        elif action_type == "update_customer_status":
            self.update("customer", target_id, proposed_changes)
            return {"status": "success", "customer_id": target_id}

        elif action_type == "delete_record":
            deleted = self.delete(target_type, target_id)
            return {"status": "success" if deleted else "not_found", "deleted": deleted}

        return {"status": "success", "action_type": action_type, "target": target}

    def relationships(
        self,
        entity_type: str,
        entity_id: str,
        relation_name: str,
    ) -> List[Dict[str, Any]]:
        if relation_name in ("invoices", "invoice") and entity_type in ("customer", "customers"):
            return self.search("invoice", {"customer_id": entity_id})
        elif relation_name in ("tasks", "task") and entity_type in ("customer", "customers"):
            return self.search("task", {"customer_id": entity_id})
        return []

    def audit(self, entry: Dict[str, Any]) -> None:
        self.audit_log.append(entry)
