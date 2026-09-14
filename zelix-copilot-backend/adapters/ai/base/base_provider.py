"""Base AI Provider Implementation helper."""

from typing import Any, Dict, Iterator, List, Optional, Type
from pydantic import BaseModel
from core.ai.models import ChatMessage, ChatResponse
from core.ai.provider import AIModelProvider


class BaseAIModelProvider(AIModelProvider):
    """Base convenience class providing default implementations for providers."""

    def __init__(self, name: str, models: Optional[List[str]] = None) -> None:
        self._name = name
        self._models = models or ["default-model"]

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def supported_models(self) -> List[str]:
        return self._models
