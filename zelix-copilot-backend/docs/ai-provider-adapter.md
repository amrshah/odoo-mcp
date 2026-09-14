# AI Provider Adapter Guide

Alamia AI Copilot abstracts LLM providers through `AIModelProvider` and routes requests dynamically using `AIModelRouter`.

---

## 1. AIModelProvider Contract

Every LLM provider implements `AIModelProvider` (`core/ai/provider.py`):

- `chat(messages, model, temperature, max_tokens, **kwargs) -> ChatResponse`
- `stream(messages, model, temperature, **kwargs) -> Iterator[str]`
- `structured_output(messages, response_schema, model, **kwargs) -> BaseModel`
- `tool_calling(messages, tools, model, **kwargs) -> ChatResponse`

---

## 2. Dynamic Routing with AIModelRouter

The router selects providers based on criteria:

```python
from core.ai.models import RoutingRequirements
from core.ai.router import AIModelRouter

router = AIModelRouter(default_provider=my_provider)
provider, model = router.select(RoutingRequirements(
    quality="high",
    privacy="local_only",
    requires_tool_calling=True,
))
```
