# Tool Development Guide

A **Business Tool** provides deterministic application and domain capabilities.

---

## 1. Sacred Invariants for Tools

1. **Deterministic Execution**: A business tool must return structured facts without secretly embedding LLM reasoning.
2. **Permission Tagging**: Tools must declare required permissions in their `ToolDefinition`.
3. **Application Decoupling**: Tools interact with the host platform strictly via the `ApplicationAdapter` interface.

---

## 2. Anatomy of a Tool

```python
from typing import Any, Dict, Optional
from core.sessions.context import EmployeeContext
from core.tools.base import BaseTool
from core.tools.definition import ToolDefinition

class SearchInvoicesTool(BaseTool):
    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_invoices",
            description="Searches invoices matching filter criteria.",
            parameters={"query": {"type": "object"}},
            required_permissions=["invoices.read"],
            risk_level="LOW",
            tags=["finance", "invoice"],
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> list:
        query = kwargs.get("query", {})
        return self.adapter.search("invoice", query)
```
