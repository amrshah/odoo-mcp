"""
Alamia AI / Microsoft BitNet Provider Adapter
Connects to https://ai.alamiaconnect.com (or local BitNet runtime) for local SLM inference.
"""

import os
import json
import logging
import httpx
from dotenv import load_dotenv
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel

load_dotenv()
logger = logging.getLogger("zelix.provider.alamia")


class CompletionResult(BaseModel):
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw_response: Optional[Dict[str, Any]] = None


class AlamiaAIProvider:
    """
    Client for Alamia AI runtime exposing OpenAI-compatible endpoints:
    - /v1/chat/completions
    - /v1/models
    - /health
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout_seconds: float = 120.0,
    ):
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
                logger.warning(f"/health check failed ({e}), probing /v1/health...")

            try:
                r = await client.get(f"{self.base_url}/v1/health", headers=self._get_headers())
                if r.status_code == 200:
                    return {"status": "ok", "endpoint": self.base_url, "details": r.json()}
                if r.status_code == 403 and "cloudflare" in r.text.lower():
                    return {"status": "cloudflare_blocked", "endpoint": self.base_url, "error": "Cloudflare WAF JS challenge active."}
                return {"status": "error", "code": r.status_code, "body": r.text[:200]}
            except Exception as e:
                logger.error(f"Alamia AI health probe failed: {e}")
                return {"status": "unreachable", "error": str(e)}

    async def list_models(self) -> List[str]:
        """Fetch available model IDs from the remote runtime."""
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                r = await client.get(f"{self.base_url}/api/v1/garden/models", headers=self._get_headers())
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        return [m.get("model_id", m.get("id")) for m in data if isinstance(m, dict) and ("model_id" in m or "id" in m)]
            except Exception:
                pass
        return [self.default_model]

    async def chat_complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> CompletionResult:
        """Execute a non-streaming chat completion request supporting native /v1/chat and OpenAI formats."""
        target_model = model or self.default_model
        
        # Native Alamia AI payload
        alamia_payload: Dict[str, Any] = {
            "messages": messages,
            "task": "reasoning",
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # OpenAI compatible payload
        openai_payload: Dict[str, Any] = {
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
                    # 1. Try native Alamia Runtime /v1/chat endpoint first
                    response = await client.post(
                        f"{self.base_url}/v1/chat",
                        headers=self._get_headers(),
                        json=alamia_payload,
                    )
                    
                    # 2. Fallback to OpenAI /v1/chat/completions if /v1/chat is 404
                    if response.status_code == 404:
                        response = await client.post(
                            f"{self.base_url}/v1/chat/completions",
                            headers=self._get_headers(),
                            json=openai_payload,
                        )

                    if response.status_code == 403 and ("cloudflare" in response.text.lower() or "challenge" in response.text.lower()):
                        raise RuntimeError("Cloudflare WAF Challenge (403 Forbidden) on ai.alamiaconnect.com. Disable Bot Fight Mode or set DNS to Grey Cloud.")
                    
                    if response.status_code != 200:
                        logger.error(f"Alamia AI error ({response.status_code}): {response.text[:300]}")
                        response.raise_for_status()

                    data = response.json()
                    
                    # Case A: Native Alamia Runtime response {"message": {"content": "..."}, "metadata": {...}}
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
                    
                    # Case B: Standard OpenAI response {"choices": [{"message": {"content": "..."}}], "usage": {...}}
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
                        raise ValueError(f"Unrecognized response format from AI runtime: {data}")

            except Exception as e:
                last_err = e
                if "Cloudflare" in str(e):
                    break
                logger.warning(f"Inference connection attempt {attempt}/2 failed: {e}. Retrying in 1s...")
                import asyncio
                await asyncio.sleep(1.0)

        raise last_err or RuntimeError("Failed to complete inference request.")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> AsyncGenerator[str, None]:
        """Stream chat tokens via Server-Sent Events."""
        target_model = model or self.default_model
        payload = {
            "messages": messages,
            "task": "dialogue",
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/stream",
                headers=self._get_headers(),
                json=payload,
            ) as response:
                if response.status_code == 404:
                    # Fallback to /v1/chat/completions
                    pass
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk_str = line[6:].strip()
                        if chunk_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(chunk_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue
