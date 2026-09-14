"""Customer 360 Skill.

Aggregates structured customer profile, invoices, and tasks without framework coupling.
"""

from typing import Any, Dict, Optional
from core.sessions.context import EmployeeContext
from core.skills.base import BaseSkill, SkillResult
from core.skills.definition import SkillDefinition


class Customer360Skill(BaseSkill):
    """Aggregates all 360-degree data for a given customer."""

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            id="customer_360",
            name="Customer 360 View",
            description="Aggregates full customer profile, invoices, and active tasks.",
            objectives=["Provide unified customer summary"],
            required_tools=["get_customer", "get_customer_invoices", "get_customer_tasks"],
            input_schema={"customer_id": {"type": "string"}},
            output_schema={"type": "object"},
            risk_level="LOW",
            allowed_roles=["sales_assistant", "support_assistant", "operations_assistant", "finance_assistant", "admin"],
        )

    def execute(
        self,
        context: EmployeeContext,
        tools: Dict[str, Any],
        ai_provider: Optional[Any] = None,
        **kwargs: Any
    ) -> SkillResult:
        customer_id = kwargs.get("customer_id")
        if not customer_id and context.active_entity:
            if context.active_entity.get("type") == "customer":
                customer_id = context.active_entity.get("id")

        if not customer_id:
            return SkillResult(
                success=False,
                skill_id=self.definition.id,
                error="customer_id is required",
            )

        get_cust_tool = tools.get("get_customer")
        get_invs_tool = tools.get("get_customer_invoices")
        get_tasks_tool = tools.get("get_customer_tasks")

        customer_data = get_cust_tool.execute(context, customer_id=customer_id) if get_cust_tool else None
        invoices_data = get_invs_tool.execute(context, customer_id=customer_id) if get_invs_tool else []
        tasks_data = get_tasks_tool.execute(context, customer_id=customer_id) if get_tasks_tool else []

        if not customer_data:
            return SkillResult(
                success=False,
                skill_id=self.definition.id,
                error=f"Customer '{customer_id}' not found.",
            )

        summary = {
            "customer": customer_data,
            "invoices": invoices_data,
            "tasks": tasks_data,
            "total_invoices": len(invoices_data),
            "pending_tasks": len([t for t in tasks_data if t.get("status") != "completed"]),
        }

        return SkillResult(
            success=True,
            skill_id=self.definition.id,
            output=summary,
        )
