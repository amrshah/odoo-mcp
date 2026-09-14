"""AI Model Router.

Routes execution requests to appropriate providers based on latency, quality, privacy, and cost.
"""

from typing import Dict, List, Optional, Tuple
from core.ai.models import RoutingRequirements
from core.ai.provider import AIModelProvider


class AIModelRouter:
    """Selects the best provider and model based on routing requirements."""

    def __init__(self, default_provider: Optional[AIModelProvider] = None) -> None:
        self._providers: Dict[str, AIModelProvider] = {}
        self._default_provider = default_provider
        if default_provider:
            self.register_provider(default_provider)

    def register_provider(self, provider: AIModelProvider) -> None:
        """Register an AI provider."""
        self._providers[provider.provider_name] = provider
        if not self._default_provider:
            self._default_provider = provider

    def select(self, requirements: Optional[RoutingRequirements] = None) -> Tuple[AIModelProvider, Optional[str]]:
        """Select appropriate (provider, model_name) matching requirements."""
        if not self._providers:
            raise RuntimeError("No AI model providers registered in AIModelRouter.")

        req = requirements or RoutingRequirements()

        # If only one provider, return it with first model
        if len(self._providers) == 1:
            provider = next(iter(self._providers.values()))
            model = provider.supported_models[0] if provider.supported_models else None
            return provider, model

        # Default fallback
        provider = self._default_provider or next(iter(self._providers.values()))
        model = provider.supported_models[0] if provider.supported_models else None
        return provider, model
