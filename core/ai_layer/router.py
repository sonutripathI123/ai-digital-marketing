"""
Intelligent Model Router.

Selects appropriate provider and model based on task complexity (ROUTINE, STANDARD, COMPLEX),
enforces primary/fallback model routing, calculates costs, tracks latency, and handles failsafes.
"""

import logging
from typing import Dict, Optional
from config.settings import MODEL_CONFIG
from core.ai_layer.base import BaseAIProvider, LLMRequest, LLMResponse, TaskComplexity
from core.ai_layer.providers.anthropic_provider import AnthropicProvider
from core.ai_layer.providers.gemini_provider import GeminiProvider
from core.ai_layer.providers.mock_provider import MockAIProvider

logger = logging.getLogger("model_router")


class ModelRouter:
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self._providers: Dict[str, BaseAIProvider] = {
            "anthropic": AnthropicProvider(),
            "gemini": GeminiProvider(),
            "mock": MockAIProvider(),
        }

    def register_provider(self, name: str, provider: BaseAIProvider) -> None:
        self._providers[name.lower()] = provider

    def get_provider(self, name: str) -> BaseAIProvider:
        if self.use_mock:
            return self._providers["mock"]
        return self._providers.get(name.lower(), self._providers["anthropic"])

    def route_and_execute(self, request: LLMRequest) -> LLMResponse:
        """
        Determines the optimal model & provider for the given LLMRequest complexity,
        executes the generation, and handles automatic fallback if the primary fails.
        """
        task_type_str = request.task_type.value if isinstance(request.task_type, TaskComplexity) else str(request.task_type)
        config_entry = MODEL_CONFIG.get(task_type_str, MODEL_CONFIG["STANDARD"])

        provider_name = config_entry.get("provider", "anthropic")
        primary_model = request.preferred_model or config_entry.get("primary_model", "claude-3-5-sonnet-20241022")
        fallback_model = config_entry.get("fallback_model", "claude-3-7-sonnet-20250219")

        provider = self.get_provider(provider_name)
        logger.info(f"Routing request [{task_type_str}] -> Provider: {provider.provider_name}, Primary Model: {primary_model}")

        # Primary execution
        response = provider.generate(request, model_override=primary_model)

        # Fallback execution if primary failed and non-mock
        if not response.success and not self.use_mock:
            logger.warning(f"Primary model {primary_model} failed: {response.error_message}. Attempting fallback model {fallback_model}.")
            fallback_provider = self.get_provider("anthropic")  # Fallback to robust provider
            response = fallback_provider.generate(request, model_override=fallback_model)
            response.retry_count += 1

        return response
