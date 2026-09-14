# Skill Development Guide

A **Skill** defines how an AI Employee performs a specific business task or workflow.

---

## 1. Sacred Invariants for Skills

1. **No Application ORM Imports**: Skills must never import SQLAlchemy, Django ORM, Eloquent, Odoo models, or direct database connections.
2. **Access Data Purely Through Tools**: Skills retrieve facts by invoking deterministic tools passed in via the runtime `tools` dictionary.
3. **Structured Mutation via ActionProposals**: Skills never mutate state directly. Mutating intent must be returned as structured `proposed_actions`.

---

## 2. Anatomy of a Skill

Every skill inherits from `BaseSkill` (`core/skills/base.py`) and specifies a `SkillDefinition`:

```python
from typing import Any, Dict, Optional
from core.sessions.context import EmployeeContext
from core.skills.base import BaseSkill, SkillResult
from core.skills.definition import SkillDefinition

class InvoiceAuditSkill(BaseSkill):
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            id="invoice_audit",
            name="Invoice Compliance Audit",
            description="Audits customer invoices for discrepancies or overdue balances.",
            objectives=["Identify billing anomalies", "Flag high-risk overdue accounts"],
            required_tools=["get_customer_invoices"],
            risk_level="LOW",
            allowed_roles=["finance_assistant", "auditor", "admin"],
            version="1.0.0",
        )

    def execute(
        self,
        context: EmployeeContext,
        tools: Dict[str, Any],
        ai_provider: Optional[Any] = None,
        **kwargs: Any
    ) -> SkillResult:
        customer_id = kwargs.get("customer_id")
        invoices_tool = tools.get("get_customer_invoices")
        invoices = invoices_tool.execute(context, customer_id=customer_id) if invoices_tool else []

        overdue = [inv for inv in invoices if inv.get("status") == "overdue"]
        return SkillResult(
            success=True,
            skill_id=self.definition.id,
            output={"total_invoices": len(invoices), "overdue_count": len(overdue)},
        )
```
