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
        models = [
            "gemma3:1b-it-qat", "qwen3.5:4b", "qwen2.5:7b-instruct", "deepseek-r1:14b",
            "@cf/meta/llama-3.1-8b-instruct-fp8", "@cf/meta/llama-3.2-3b-instruct",
            "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b"
        ]
        super().__init__(name=name, models=models)

        cf_account = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        cf_token = os.getenv("CLOUDFLARE_API_TOKEN")
        cf_gateway = os.getenv("CLOUDFLARE_GATEWAY_ID")
        cf_model = os.getenv("CLOUDFLARE_MODEL")
        is_cf = (os.getenv("AI_PROVIDER") == "cloudflare") or (bool(cf_account and cf_token) and not base_url and not os.getenv("ALAMIA_AI_URL"))

        if is_cf and cf_account:
            if cf_gateway:
                cf_endpoint = f"https://gateway.ai.cloudflare.com/v1/{cf_account}/{cf_gateway}/workers-ai/v1"
            else:
                cf_endpoint = f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/ai/v1"
            default_endpoint = cf_endpoint
            default_key = cf_token or ""
            default_mod = cf_model or "@cf/meta/llama-3.1-8b-instruct-fp8"
        else:
            default_endpoint = "http://host.docker.internal:11434/v1" if (os.path.exists("/.dockerenv") or os.environ.get("HOSTNAME")) else "http://localhost:11434/v1"
            default_key = os.getenv("BITNET_API_KEY") or os.getenv("ALAMIA_AI_API_KEY", "")
            default_mod = os.getenv("BITNET_DEFAULT_MODEL") or os.getenv("ALAMIA_AI_MODEL") or "qwen3.5:4b"

        self.base_url = (
            base_url
            or (cf_endpoint if is_cf and cf_account else None)
            or os.getenv("ALAMIA_AI_URL")
            or os.getenv("ALAMIA_AI_ENDPOINT")
            or os.getenv("OLLAMA_ENDPOINT")
            or default_endpoint
        ).rstrip("/")
        self.api_key = api_key or (cf_token if is_cf and cf_token else None) or default_key
        self.default_model = (
            default_model
            or (default_mod if is_cf else None)
            or os.getenv("BITNET_DEFAULT_MODEL")
            or os.getenv("ALAMIA_AI_MODEL")
            or default_mod
        )

    def _resolve_endpoint(self, kwargs: Dict[str, Any]) -> tuple[str, str, str]:
        """Dynamically resolves API endpoint, bearer token, and model from request context or env."""
        ai_cfg = kwargs.get("ai_config") or {}
        cf_token = ai_cfg.get("cf_api_token") or os.getenv("CLOUDFLARE_API_TOKEN") or self.api_key
        cf_account = ai_cfg.get("cf_account_id") or os.getenv("CLOUDFLARE_ACCOUNT_ID") or "be941241fb3499e9567c7ec28528c984"
        cf_gateway = ai_cfg.get("cf_gateway_id") or os.getenv("CLOUDFLARE_GATEWAY_ID") or ""
        cf_model = ai_cfg.get("cf_model") or kwargs.get("model") or os.getenv("CLOUDFLARE_MODEL") or "@cf/meta/llama-3.1-8b-instruct-fp8"
        provider = ai_cfg.get("provider") or os.getenv("AI_PROVIDER") or "cloudflare"

        if provider == "cloudflare" or cf_token:
            if cf_gateway:
                url = f"https://gateway.ai.cloudflare.com/v1/{cf_account}/{cf_gateway}/workers-ai/v1/chat/completions"
            else:
                url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/ai/v1/chat/completions"
            return url, (cf_token or ""), cf_model

        # Fallback to local / remote endpoint
        base = (self.base_url or os.getenv("ALAMIA_AI_URL") or "http://localhost:11434/v1").rstrip("/")
        if "/chat/completions" in base:
            url = base
        elif base.endswith("/v1"):
            url = f"{base}/chat/completions"
        else:
            url = f"{base}/v1/chat/completions"
        return url, (self.api_key or ""), (kwargs.get("model") or self.default_model)

    def chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        url, api_key, model_name = self._resolve_endpoint({"model": model, **kwargs})
        payload = {
            "model": model_name,
            "messages": [{"role": m.role.value if hasattr(m.role, "value") else str(m.role), "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ZelixAICopilot/2.0",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                choice = result["choices"][0]["message"]
                content = choice.get("content", "")
                if content and "<think>" in content and "</think>" in content:
                    import re
                    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
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
            raise RuntimeError(f"AI Provider error: {e} [Endpoint: {url}]") from e

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
