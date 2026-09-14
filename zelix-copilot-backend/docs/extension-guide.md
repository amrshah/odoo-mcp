# Extension Guide: Integrating Host Applications

This guide explains how to integrate existing enterprise systems (such as **Odoo**, **Laravel**, **FastAPI**, **Django**, or proprietary platforms) with Alamia AI Copilot **without modifying a single line in `core/`**.

---

## 1. The 5-Step Integration Workflow

```text
1. Implement ApplicationAdapter
        ↓
2. Register Business Tools
        ↓
3. Register Domain Skills
        ↓
4. Define Employee Roles
        ↓
5. Configure AI Provider & Launch
```

---

## 2. Step 1: Implement an ApplicationAdapter

Create an adapter in `adapters/application/<your_framework>/` implementing the `ApplicationAdapter` abstract base class:

```python
from typing import Any, Dict, List, Optional
from adapters.application.base.adapter import ApplicationAdapter

class LaravelApplicationAdapter(ApplicationAdapter):
    def __init__(self, api_client):
        self.client = api_client

    def identity(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.client.get(f"/api/users/{user_id}")

    def permissions(self, user_id: str) -> List[str]:
        return self.client.get(f"/api/users/{user_id}/permissions")

    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        return self.client.get(f"/api/{entity_type}s/{entity_id}")

    def search(self, entity_type: str, query: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self.client.get(f"/api/{entity_type}s", params=query)

    def execute(self, action_type: str, target: Dict[str, Any], proposed_changes: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Any:
        return self.client.post(f"/api/actions/{action_type}", json={"target": target, "changes": proposed_changes})

    def relationships(self, entity_type: str, entity_id: str, relation_name: str) -> List[Dict[str, Any]]:
        return self.client.get(f"/api/{entity_type}s/{entity_id}/{relation_name}")

    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.post(f"/api/{entity_type}s", json=data)

    def update(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.put(f"/api/{entity_type}s/{entity_id}", json=data)

    def delete(self, entity_type: str, entity_id: str) -> bool:
        return self.client.delete(f"/api/{entity_type}s/{entity_id}").status_code == 200

    def audit(self, entry: Dict[str, Any]) -> None:
        self.client.post("/api/audit-events", json=entry)
```

*(Alternatively, connect over Model Context Protocol using `MCPApplicationAdapter` if your application exposes an MCP server).*

---

## 3. Step 2: Register Domain Business Tools

Wrap application capabilities in deterministic business tools:

```python
from core.tools.base import BaseTool
from core.tools.definition import ToolDefinition

class GetBookingTool(BaseTool):
    def __init__(self, adapter):
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_booking",
            description="Fetches booking record by ID.",
            parameters={"booking_id": {"type": "string"}},
            required_permissions=["bookings.read"],
            risk_level="LOW",
        )

    def execute(self, context, **kwargs):
        return self.adapter.get("booking", kwargs.get("booking_id"))
```

---

## 4. Step 3: Register Domain Skills

```python
from core.skills.base import BaseSkill, SkillResult
from core.skills.definition import SkillDefinition

class CancelBookingSkill(BaseSkill):
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            id="cancel_booking",
            name="Cancel Booking Workflow",
            description="Evaluates cancellation policy and proposes booking cancellation.",
            required_tools=["get_booking"],
            risk_level="HIGH",
            allowed_roles=["travel_agent", "admin"],
        )

    def execute(self, context, tools, ai_provider=None, **kwargs):
        booking_id = kwargs.get("booking_id")
        booking = tools["get_booking"].execute(context, booking_id=booking_id)

        # Propose structured mutation
        proposal = {
            "action_id": f"act_cancel_{booking_id}",
            "action_type": "cancel_booking",
            "idempotency_key": f"cancel_{booking_id}_req_{context.user_id}",
            "target": {"type": "booking", "id": booking_id},
            "reason": kwargs.get("reason", "Customer requested cancellation"),
            "risk_level": "HIGH",
            "required_permission": "bookings.cancel",
            "requires_confirmation": True,
            "created_by": context.user_id,
        }
        return SkillResult(success=True, skill_id=self.definition.id, output=booking, proposed_actions=[proposal])
```

---

## 5. Step 4: Define Roles & Initialize Copilot Engine

```python
from core.roles.manifest import RoleManifest
from core.roles.registry import RoleRegistry
from core.runtime.engine import CopilotEngine
from core.skills.registry import SkillRegistry
from core.tools.registry import ToolRegistry

# Initialize registries
skills = SkillRegistry()
skills.register(CancelBookingSkill())

tools = ToolRegistry()
tools.register(GetBookingTool(adapter))

roles = RoleRegistry()
roles.register(RoleManifest(
    id="travel_agent",
    name="Travel Operations Agent",
    skills=["cancel_booking"],
    permissions=["bookings.read", "bookings.cancel"],
))

# Instantiate engine
engine = CopilotEngine(
    skill_registry=skills,
    tool_registry=tools,
    role_registry=roles,
    application_adapter=adapter,
)
```
