"""Payment Followup Skill.

Inspects overdue customer invoices and proposes follow-up action with idempotency protection.
"""

from typing import Any, Dict, Optional
from core.sessions.context import EmployeeContext
from core.skills.base import BaseSkill, SkillResult
from core.skills.definition import SkillDefinition


class PaymentFollowupSkill(BaseSkill):
    """Identifies overdue invoices and proposes payment follow-up action."""

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            id="payment_followup",
            name="Payment Follow-up",
            description="Analyzes customer payment status and proposes follow-up tasks for overdue balances.",
            objectives=["Identify overdue invoices", "Propose follow-up action"],
            required_tools=["get_customer", "get_customer_invoices"],
            input_schema={"customer_id": {"type": "string"}},
            output_schema={"type": "object"},
            risk_level="MEDIUM",
            allowed_roles=["finance_assistant", "admin"],
        )

    def execute(
        self,
        context: EmployeeContext,
        tools: Dict[str, Any],
        ai_provider: Optional[Any] = None,
        **kwargs: Any
    ) -> SkillResult:
        customer_id = kwargs.get("customer_id")
        if not customer_id:
            return SkillResult(
                success=False,
                skill_id=self.definition.id,
                error="customer_id is required",
            )

        get_cust_tool = tools.get("get_customer")
        get_invs_tool = tools.get("get_customer_invoices")

        customer_data = get_cust_tool.execute(context, customer_id=customer_id) if get_cust_tool else None
        invoices_data = get_invs_tool.execute(context, customer_id=customer_id) if get_invs_tool else []

        if not customer_data:
            return SkillResult(
                success=False,
                skill_id=self.definition.id,
                error=f"Customer '{customer_id}' not found.",
            )

        overdue_invoices = [inv for inv in invoices_data if inv.get("status") == "overdue"]
        total_overdue = sum(float(inv.get("amount", 0)) for inv in overdue_invoices)

        proposed_actions = []
        if overdue_invoices:
            # Generate deterministic idempotency key for this customer followup
            idempotency_key = f"followup_cust_{customer_id}_overdue_{len(overdue_invoices)}"
            proposed_actions.append({
                "action_id": f"act_followup_{customer_id}",
                "action_type": "create_followup",
                "idempotency_key": idempotency_key,
                "target": {"type": "customer", "id": customer_id},
                "reason": f"Customer has {len(overdue_invoices)} overdue invoice(s) totaling ${total_overdue:.2f}.",
                "proposed_changes": {
                    "title": f"Follow up with {customer_data.get('name')} regarding overdue invoices",
                    "description": f"Overdue total: ${total_overdue:.2f}",
                },
                "risk_level": "LOW",
                "required_permission": "tasks.create",
                "requires_confirmation": False,
                "created_by": context.user_id,
            })

        return SkillResult(
            success=True,
            skill_id=self.definition.id,
            output={
                "customer_name": customer_data.get("name"),
                "overdue_count": len(overdue_invoices),
                "total_overdue": total_overdue,
            },
            proposed_actions=proposed_actions,
        )
