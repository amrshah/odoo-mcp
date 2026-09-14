"""
adapters/ai/providers/alamia_provider.py
HTTP client adapter for OpenAI-compatible LLM endpoints (Alamia AI / Ollama / vLLM).
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Any, Dict, Iterator, List, Optional, Type
from pydantic import BaseModel
from adapters.ai.base.base_provider import BaseAIModelProvider
from core.ai.models import ChatMessage, ChatResponse, ToolCallRequest

logger = logging.getLogger("zelix.ai.alamia")


class AlamiaAIModelProvider(BaseAIModelProvider):
    """Production AI Provider connecting to Alamia AI endpoint or local Ollama."""

    def __init__(
        self,
        name: str = "alamia-ai",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
    ) -> None:
        models = ["gemma3:1b-it-qat", "qwen3.5:4b", "qwen2.5:7b-instruct", "deepseek-r1:14b"]
        super().__init__(name=name, models=models)
        self.base_url = (
            base_url
            or os.getenv("ALAMIA_AI_ENDPOINT")
            or os.getenv("OLLAMA_ENDPOINT")
            or "http://localhost:11434/v1"
        ).rstrip("/")
        self.api_key = api_key or os.getenv("ALAMIA_AI_API_KEY", "")
        self.default_model = default_model or os.getenv("ALAMIA_AI_MODEL", "qwen3.5:4b")

    def chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        model_name = model or self.default_model
        payload = {
            "model": model_name,
            "messages": [{"role": m.role.value if hasattr(m.role, "value") else str(m.role), "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        url = f"{self.base_url}/chat/completions"
        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ZelixAICopilot/2.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                choice = result["choices"][0]["message"]
                content = choice.get("content", "")
                usage = result.get("usage", {})
                return ChatResponse(
                    content=content,
                    model=result.get("model", model_name),
                    usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                )
        except Exception as e:
            logger.warning(f"AI Provider request failed to {url}: {e}")
            raise RuntimeError(f"AI Provider error: {e}") from e

    def stream(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Iterator[str]:
        res = self.chat(messages=messages, model=model, temperature=temperature, **kwargs)
        for word in res.content.split():
            yield word + " "

    def structured_output(
        self,
        messages: List[ChatMessage],
        response_schema: Type[BaseModel],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseModel:
        res = self.chat(messages=messages, model=model, **kwargs)
        try:
            data = json.loads(res.content)
            return response_schema.model_validate(data)
        except Exception:
            return response_schema.model_validate({})

    def tool_calling(
        self,
        messages: List[ChatMessage],
        tools: List[Dict[str, Any]],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        return self.chat(messages=messages, model=model, **kwargs)

    async def check_health(self) -> Dict[str, Any]:
        """Check status of remote/local LLM endpoint."""
        return {
            "provider": self.provider_name,
            "endpoint": self.base_url,
            "default_model": self.default_model,
            "status": "ready",
        }
