"""
core/ai/provider.py
Abstract base class for all AI Model Providers (Local, BitNet, Cloud, Mock).
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field


class CompletionResult(BaseModel):
    content: str
    model: str = "default"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw_response: Optional[Dict[str, Any]] = None


class AIModelProvider(ABC):
    """Abstract interface for LLM / SLM inference providers."""

    @abstractmethod
    async def chat_complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> CompletionResult:
        pass

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        pass
