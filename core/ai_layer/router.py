"""
Intelligent Model Router.

Selects appropriate provider and model based on task complexity (ROUTINE, STANDARD, COMPLEX),
enforces primary/fallback model routing, calculates costs, tracks latency, and handles failsafes.
Supports Anthropic, Gemini, OpenAI, DeepSeek, Groq, Custom/Ollama providers.
"""

import os
import logging
from typing import Dict, Optional, Any, List
from config.settings import MODEL_CONFIG, DEFAULT_PROVIDER
from core.ai_layer.base import BaseAIProvider, LLMRequest, LLMResponse, TaskComplexity
from core.ai_layer.providers.anthropic_provider import AnthropicProvider
from core.ai_layer.providers.gemini_provider import GeminiProvider
from core.ai_layer.providers.openai_provider import OpenAIProvider
from core.ai_layer.providers.deepseek_provider import DeepSeekProvider
from core.ai_layer.providers.groq_provider import GroqProvider
from core.ai_layer.providers.custom_provider import CustomAIProvider
from core.ai_layer.providers.mock_provider import MockAIProvider

logger = logging.getLogger("model_router")


class ModelRouter:
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.primary_provider_name = os.getenv("DEFAULT_AI_PROVIDER", "anthropic").lower()
        self._providers: Dict[str, BaseAIProvider] = {
            "anthropic": AnthropicProvider(),
            "gemini": GeminiProvider(),
            "openai": OpenAIProvider(),
            "deepseek": DeepSeekProvider(),
            "groq": GroqProvider(),
            "custom": CustomAIProvider(),
            "mock": MockAIProvider(),
        }

    def register_provider(self, name: str, provider: BaseAIProvider) -> None:
        self._providers[name.lower()] = provider

    def set_primary_provider(self, name: str) -> bool:
        name = name.lower()
        if name in self._providers:
            self.primary_provider_name = name
            return True
        return False

    def update_provider_key(self, name: str, api_key: str, base_url: Optional[str] = None) -> bool:
        name = name.lower()
        if name not in self._providers:
            return False

        prov = self._providers[name]
        if hasattr(prov, "set_api_key"):
            prov.set_api_key(api_key)
        elif hasattr(prov, "set_config"):
            prov.set_config(api_key, base_url)
        elif hasattr(prov, "_api_key"):
            prov._api_key = api_key
        return True

    def get_provider(self, name: Optional[str] = None) -> BaseAIProvider:
        if self.use_mock:
            return self._providers["mock"]
        if not name or name == "default":
            name = self.primary_provider_name
        return self._providers.get(name.lower(), self._providers.get("anthropic", self._providers["mock"]))

    def get_all_providers_status(self) -> List[Dict[str, Any]]:
        """Returns structured metadata for all AI providers for dashboard presentation."""
        providers_info = [
            {
                "id": "anthropic",
                "name": "Anthropic Claude",
                "env_var": "ANTHROPIC_API_KEY",
                "is_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
                "masked_key": self._mask_key(os.getenv("ANTHROPIC_API_KEY")),
                "is_primary": self.primary_provider_name == "anthropic",
                "default_model": "claude-3-5-sonnet-20241022",
                "supported_models": [
                    "claude-3-5-sonnet-20241022",
                    "claude-3-7-sonnet-20250219",
                    "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229"
                ],
                "badge": "Anthropic Claude 3.5 Sonnet",
                "icon": "fa-solid fa-brain"
            },
            {
                "id": "gemini",
                "name": "Google Gemini",
                "env_var": "GEMINI_API_KEY",
                "is_configured": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
                "masked_key": self._mask_key(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
                "is_primary": self.primary_provider_name == "gemini",
                "default_model": "gemini-2.5-flash",
                "supported_models": [
                    "gemini-2.5-flash",
                    "gemini-1.5-pro",
                    "gemini-2.0-flash-thinking"
                ],
                "badge": "Gemini 2.5 Flash",
                "icon": "fa-brands fa-google"
            },
            {
                "id": "openai",
                "name": "OpenAI",
                "env_var": "OPENAI_API_KEY",
                "is_configured": bool(os.getenv("OPENAI_API_KEY")),
                "masked_key": self._mask_key(os.getenv("OPENAI_API_KEY")),
                "is_primary": self.primary_provider_name == "openai",
                "default_model": "gpt-4o",
                "supported_models": [
                    "gpt-4o",
                    "gpt-4o-mini",
                    "o1",
                    "o3-mini"
                ],
                "badge": "GPT-4o & GPT-4o-mini",
                "icon": "fa-solid fa-cube"
            },
            {
                "id": "deepseek",
                "name": "DeepSeek AI",
                "env_var": "DEEPSEEK_API_KEY",
                "is_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
                "masked_key": self._mask_key(os.getenv("DEEPSEEK_API_KEY")),
                "is_primary": self.primary_provider_name == "deepseek",
                "default_model": "deepseek-chat",
                "supported_models": [
                    "deepseek-chat",
                    "deepseek-reasoner"
                ],
                "badge": "DeepSeek-V3 & DeepSeek-R1",
                "icon": "fa-solid fa-microchip"
            },
            {
                "id": "groq",
                "name": "Groq Cloud",
                "env_var": "GROQ_API_KEY",
                "is_configured": bool(os.getenv("GROQ_API_KEY")),
                "masked_key": self._mask_key(os.getenv("GROQ_API_KEY")),
                "is_primary": self.primary_provider_name == "groq",
                "default_model": "llama-3.3-70b-versatile",
                "supported_models": [
                    "llama-3.3-70b-versatile",
                    "llama-3.1-8b-instant",
                    "mixtral-8x7b-32768"
                ],
                "badge": "Ultra-Fast Llama 3.3 (70B)",
                "icon": "fa-solid fa-bolt-lightning"
            },
            {
                "id": "custom",
                "name": "Custom / Ollama / Mistral",
                "env_var": "CUSTOM_API_KEY",
                "is_configured": bool(os.getenv("CUSTOM_API_KEY") or os.getenv("CUSTOM_API_BASE_URL")),
                "masked_key": self._mask_key(os.getenv("CUSTOM_API_KEY")),
                "base_url": os.getenv("CUSTOM_API_BASE_URL", "http://localhost:11434/v1"),
                "is_primary": self.primary_provider_name == "custom",
                "default_model": "mistral-large-latest",
                "supported_models": [
                    "mistral-large-latest",
                    "codestral-latest",
                    "llama3",
                    "custom-model"
                ],
                "badge": "OpenAI-Compatible & Local",
                "icon": "fa-solid fa-server"
            }
        ]
        return providers_info

    @staticmethod
    def _mask_key(key: Optional[str]) -> str:
        if not key:
            return "Not Configured"
        clean = key.strip()
        if len(clean) <= 8:
            return "••••••••"
        return f"{clean[:5]}••••••••{clean[-4:]}"

    def route_and_execute(self, request: LLMRequest) -> LLMResponse:
        """
        Determines the optimal model & provider for the given LLMRequest complexity,
        executes the generation, and handles automatic fallback if the primary fails.
        """
        task_type_str = request.task_type.value if isinstance(request.task_type, TaskComplexity) else str(request.task_type)
        config_entry = MODEL_CONFIG.get(task_type_str, MODEL_CONFIG["STANDARD"])

        provider_name = config_entry.get("provider", self.primary_provider_name)
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
