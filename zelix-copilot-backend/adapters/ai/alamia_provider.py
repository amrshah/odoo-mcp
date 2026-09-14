"""
adapters/ai/alamia_provider.py
Alamia Local AI Runtime Adapter implementing AIModelProvider.
"""

import os
import json
import logging
import httpx
from typing import Any, Dict, List, Optional
from core.ai.provider import AIModelProvider, CompletionResult

logger = logging.getLogger("zelix.adapters.ai.alamia")


class AlamiaAIModelProvider(AIModelProvider):
    """Client for Alamia Local AI Runtime & Microsoft BitNet Inference Fabric."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("ALAMIA_AI_URL", "https://ai.alamiaconnect.com")).rstrip("/")
        self.api_key = api_key or os.getenv("BITNET_API_KEY", "51129693340")
        self.default_model = default_model or os.getenv(
            "BITNET_DEFAULT_MODEL", "/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf"
        )
        self.timeout = timeout_seconds

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 ZelixAI/1.0",
            "Accept": "application/json, text/plain, */*",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["x-api-key"] = self.api_key
            headers["bitnet-api-key"] = self.api_key
        return headers

    async def check_health(self) -> Dict[str, Any]:
        """Verify connectivity and health of Alamia AI endpoint."""
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                r = await client.get(f"{self.base_url}/health", headers=self._get_headers())
                if r.status_code == 200:
                    return {"status": "ok", "endpoint": self.base_url, "details": r.json()}
            except Exception as e:
                logger.warning(f"/health probe failed ({e}), probing /v1/health...")

            try:
                r = await client.get(f"{self.base_url}/v1/health", headers=self._get_headers())
                if r.status_code == 200:
                    return {"status": "ok", "endpoint": self.base_url, "details": r.json()}
                if r.status_code == 403 and "cloudflare" in r.text.lower():
                    return {"status": "cloudflare_blocked", "endpoint": self.base_url, "error": "Cloudflare WAF challenge."}
                return {"status": "error", "code": r.status_code, "body": r.text[:200]}
            except Exception as e:
                return {"status": "unreachable", "error": str(e)}

    async def chat_complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> CompletionResult:
        """Execute chat completion with automatic fallback."""
        target_model = model or self.default_model
        
        alamia_payload = {
            "messages": messages,
            "task": "reasoning",
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        openai_payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            openai_payload["response_format"] = {"type": "json_object"}

        last_err = None
        for attempt in range(1, 3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    # 1. Native /v1/chat endpoint
                    response = await client.post(
                        f"{self.base_url}/v1/chat",
                        headers=self._get_headers(),
                        json=alamia_payload,
                    )
                    
                    # 2. Fallback to /v1/chat/completions if 404
                    if response.status_code == 404:
                        response = await client.post(
                            f"{self.base_url}/v1/chat/completions",
                            headers=self._get_headers(),
                            json=openai_payload,
                        )

                    if response.status_code == 403 and ("cloudflare" in response.text.lower() or "challenge" in response.text.lower()):
                        raise RuntimeError("Cloudflare WAF Challenge (403 Forbidden) on ai.alamiaconnect.com.")
                    
                    if response.status_code != 200:
                        logger.error(f"Alamia AI error ({response.status_code}): {response.text[:300]}")
                        response.raise_for_status()

                    data = response.json()
                    
                    # Case A: Native Alamia response
                    if "message" in data and isinstance(data["message"], dict):
                        content = data["message"].get("content", "")
                        metadata = data.get("metadata", {})
                        return CompletionResult(
                            content=content,
                            model=metadata.get("model_id", target_model),
                            prompt_tokens=metadata.get("prompt_tokens", 0),
                            completion_tokens=metadata.get("completion_tokens", 0),
                            total_tokens=metadata.get("total_tokens", 0),
                            raw_response=data,
                        )
                    # Case B: Standard OpenAI response
                    elif "choices" in data and len(data["choices"]) > 0:
                        choice = data["choices"][0]
                        content = choice.get("message", {}).get("content", "")
                        usage = data.get("usage", {})
                        return CompletionResult(
                            content=content,
                            model=target_model,
                            prompt_tokens=usage.get("prompt_tokens", 0),
                            completion_tokens=usage.get("completion_tokens", 0),
                            total_tokens=usage.get("total_tokens", 0),
                            raw_response=data,
                        )
                    else:
                        raise ValueError(f"Unrecognized response format: {data}")

            except Exception as e:
                last_err = e
                if "Cloudflare" in str(e):
                    break
                import asyncio
                await asyncio.sleep(1.0)

        raise last_err or RuntimeError("Failed to complete inference request.")
