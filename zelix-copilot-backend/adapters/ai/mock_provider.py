"""
adapters/ai/mock_provider.py
Zero-cost Mock AI Provider for automated unit and integration tests.
"""

from typing import Any, Dict, List, Optional
from core.ai.provider import AIModelProvider, CompletionResult


class MockAIModelProvider(AIModelProvider):
    """Mock AI Provider returning deterministic synthetic responses."""

    def __init__(self, fixed_response: Optional[str] = None) -> None:
        self.fixed_response = fixed_response

    async def check_health(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": "mock"}

    async def chat_complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> CompletionResult:
        content = self.fixed_response or "Clinical assessment verified. Patient is in stable condition."
        return CompletionResult(
            content=content,
            model=model or "mock-slm",
            prompt_tokens=15,
            completion_tokens=20,
            total_tokens=35,
        )
