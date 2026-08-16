"""
Custom OpenAI-Compatible & Self-Hosted Provider Adapter Interface.

Supports Ollama, Mistral AI, OpenRouter, Perplexity, vLLM, and any self-hosted LLM endpoints.
Reads CUSTOM_API_KEY and CUSTOM_API_BASE_URL from environment or runtime parameter.
"""

import os
import time
import logging
from typing import Optional

from config.settings import TOKEN_PRICING
from core.ai_layer.base import BaseAIProvider, LLMRequest, LLMResponse

logger = logging.getLogger("custom_provider")


class CustomAIProvider(BaseAIProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or os.getenv("CUSTOM_API_KEY", "")
        self._base_url = base_url or os.getenv("CUSTOM_API_BASE_URL", "http://localhost:11434/v1")

    @property
    def provider_name(self) -> str:
        return "custom"

    def set_config(self, api_key: str, base_url: Optional[str] = None) -> None:
        self._api_key = api_key
        if base_url:
            self._base_url = base_url

    def generate(self, request: LLMRequest, model_override: Optional[str] = None) -> LLMResponse:
        start_time = time.time()
        model_name = model_override or request.preferred_model or "mistral-large-latest"

        url = self._base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            endpoint = f"{url}/chat/completions"
        else:
            endpoint = url

        try:
            import urllib.request
            import json

            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt}
                ],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens
            }

            headers = {
                "Content-Type": "application/json"
            }
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=45) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                content = resp_data["choices"][0]["message"]["content"]
                usage = resp_data.get("usage", {})
                in_tok = usage.get("prompt_tokens", 0)
                out_tok = usage.get("completion_tokens", 0)

                pricing = TOKEN_PRICING.get(model_name, {"input": 0.001, "output": 0.002})
                cost = (in_tok * pricing["input"] + out_tok * pricing["output"]) / 1000.0

                return LLMResponse(
                    content=content,
                    model_used=model_name,
                    provider=self.provider_name,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    total_tokens=in_tok + out_tok,
                    cost_usd=cost,
                    latency_ms=(time.time() - start_time) * 1000,
                    success=True
                )

        except Exception as e:
            logger.error(f"Custom LLM API call failed: {e}")
            return LLMResponse(
                content="",
                model_used=model_name,
                provider=self.provider_name,
                success=False,
                error_message=str(e),
                latency_ms=(time.time() - start_time) * 1000
            )
