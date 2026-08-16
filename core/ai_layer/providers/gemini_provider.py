"""
Google Gemini Provider Adapter Interface.

Prepared for future expansion. Reads GEMINI_API_KEY securely from environment.
If key is absent, returns a structured error response without crashing.
"""

import os
import time
from typing import Optional

from config import TOKEN_PRICING
from core.ai_layer.base import BaseAIProvider, LLMRequest, LLMResponse


class GeminiProvider(BaseAIProvider):
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    @property
    def provider_name(self) -> str:
        return "gemini"

    def generate(self, request: LLMRequest, model_override: Optional[str] = None) -> LLMResponse:
        start_time = time.time()
        model_name = model_override or request.preferred_model or "gemini-2.5-flash"

        if not self._api_key:
            return LLMResponse(
                content="",
                model_used=model_name,
                provider=self.provider_name,
                success=False,
                error_message="GEMINI_API_KEY is not configured in environment. Adapter interface is ready.",
                latency_ms=(time.time() - start_time) * 1000
            )

        # Future expansion: live google.genai / google.generativeai call when key is active
        return LLMResponse(
            content="[Gemini Provider Interface Ready - Live key integration pending]",
            model_used=model_name,
            provider=self.provider_name,
            success=True,
            latency_ms=(time.time() - start_time) * 1000
        )
