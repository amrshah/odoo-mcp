"""Mock / Stub AI Model Provider for deterministic testing."""

import json
from typing import Any, Dict, Iterator, List, Optional, Type
from pydantic import BaseModel
from adapters.ai.base.base_provider import BaseAIModelProvider
from core.ai.models import ChatMessage, ChatResponse, ToolCallRequest


class MockAIModelProvider(BaseAIModelProvider):
    """Deterministic mock AI provider for behavioral testing."""

    def __init__(
        self,
        name: str = "mock-provider",
        canned_response: str = "Mock response",
        canned_tool_calls: Optional[List[ToolCallRequest]] = None,
    ) -> None:
        super().__init__(name=name, models=["mock-v1", "mock-v2"])
        self.canned_response = canned_response
        self.canned_tool_calls = canned_tool_calls or []
        self.call_history: List[List[ChatMessage]] = []

    def chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> ChatResponse:
        self.call_history.append(messages)
        return ChatResponse(
            content=self.canned_response,
            tool_calls=self.canned_tool_calls,
            model=model or self._models[0],
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        )

    def stream(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> Iterator[str]:
        self.call_history.append(messages)
        for word in self.canned_response.split():
            yield word + " "

    def structured_output(
        self,
        messages: List[ChatMessage],
        response_schema: Type[BaseModel],
        model: Optional[str] = None,
        **kwargs: Any
    ) -> BaseModel:
        self.call_history.append(messages)
        # Attempt to parse canned response as JSON into model
        try:
            data = json.loads(self.canned_response)
            return response_schema.model_validate(data)
        except Exception:
            return response_schema.model_validate({})

    def tool_calling(
        self,
        messages: List[ChatMessage],
        tools: List[Dict[str, Any]],
        model: Optional[str] = None,
        **kwargs: Any
    ) -> ChatResponse:
        self.call_history.append(messages)
        return ChatResponse(
            content=self.canned_response,
            tool_calls=self.canned_tool_calls,
            model=model or self._models[0],
            usage={"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
        )
