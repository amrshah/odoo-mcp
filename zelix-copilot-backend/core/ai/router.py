"""
core/ai/router.py
Smart AI Model Router dispatching prompts based on skill requirements and latency preferences.
"""

from typing import Dict, List, Optional
from core.ai.provider import AIModelProvider, CompletionResult


class AIModelRouter:
    """Routes execution between fast local SLMs (BitNet / Qwen) and reasoning models."""

    def __init__(
        self,
        default_provider: AIModelProvider,
        skill_routes: Optional[Dict[str, str]] = None,
        provider_map: Optional[Dict[str, AIModelProvider]] = None,
    ) -> None:
        self.default_provider = default_provider
        self.skill_routes = skill_routes or {}
        self.provider_map = provider_map or {}

    def get_provider_for_skill(self, skill_id: str) -> AIModelProvider:
        return self.provider_map.get(skill_id, self.default_provider)

    def get_model_for_skill(self, skill_id: str) -> Optional[str]:
        return self.skill_routes.get(skill_id)

    async def complete_for_skill(
        self,
        skill_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> CompletionResult:
        provider = self.get_provider_for_skill(skill_id)
        model = self.get_model_for_skill(skill_id)
        return await provider.chat_complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )
