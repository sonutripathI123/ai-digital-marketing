"""
Mock AI Provider Adapter for deterministic offline unit testing.
Does not make network calls or spend tokens.
"""

import json
import time
from typing import Optional
from core.ai_layer.base import BaseAIProvider, LLMRequest, LLMResponse, TaskComplexity


class MockAIProvider(BaseAIProvider):
    def __init__(self, default_response: str = "Mock AI response content."):
        self._default_response = default_response

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(self, request: LLMRequest, model_override: Optional[str] = None) -> LLMResponse:
        start = time.time()
        model_name = model_override or "mock-model"

        if request.json_output:
            response_text = json.dumps({
                "caption": "Executive transfer in Melbourne. Punctual and luxury.",
                "hashtags": "#MelbourneChauffeur #CorporateTravel",
                "cta": "Book at corporatecarsmelbourne.com.au",
                "keyword": "airport transfer",
                "title_hint": "Executive Airport Transfers",
                "content_html": "<p>Mock blog post content.</p>",
                "meta_description": "Mock description",
                "focus_keyword": "airport transfer",
                "slug": "mock-post",
                "category": "Airport Transfers"
            })
        else:
            response_text = self._default_response

        parsed = None
        if request.json_output:
            try:
                parsed = json.loads(response_text)
            except Exception:
                parsed = None

        latency = (time.time() - start) * 1000

        return LLMResponse(
            content=response_text,
            parsed_json=parsed,
            model_used=model_name,
            provider=self.provider_name,
            tokens_in=len(request.user_prompt.split()),
            tokens_out=len(response_text.split()),
            cost_usd=0.0,
            latency_ms=latency,
            success=True
        )
