"""AI Model Provider Interface.

Defines the abstract interface for all AI / LLM model providers.
Core must NEVER directly depend on OpenAI, Anthropic, Ollama, etc.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Type
from pydantic import BaseModel
from core.ai.models import ChatMessage, ChatResponse, ToolCallRequest


class AIModelProvider(ABC):
    """Abstract base class for all AI model providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider implementation."""
        pass

    @property
    @abstractmethod
    def supported_models(self) -> List[str]:
        """List of supported model identifiers."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> ChatResponse:
        """Synchronous chat completion."""
        pass

    @abstractmethod
    def stream(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> Iterator[str]:
        """Stream text tokens incrementally."""
        pass

    @abstractmethod
    def structured_output(
        self,
        messages: List[ChatMessage],
        response_schema: Type[BaseModel],
        model: Optional[str] = None,
        **kwargs: Any
    ) -> BaseModel:
        """Generate guaranteed structured output conforming to a Pydantic schema."""
        pass

    @abstractmethod
    def tool_calling(
        self,
        messages: List[ChatMessage],
        tools: List[Dict[str, Any]],
        model: Optional[str] = None,
        **kwargs: Any
    ) -> ChatResponse:
        """Invoke chat with function / tool calling definitions."""
        pass
