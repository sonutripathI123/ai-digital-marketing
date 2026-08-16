"""
Groq Provider Adapter Interface.

Supports ultra-fast Llama-3.3-70B, Llama-3.1-8B, Mixtral-8x7B.
Reads GROQ_API_KEY securely from environment or runtime parameter.
"""

import os
import time
import logging
from typing import Optional

from config.settings import TOKEN_PRICING
from core.ai_layer.base import BaseAIProvider, LLMRequest, LLMResponse

logger = logging.getLogger("groq_provider")


class GroqProvider(BaseAIProvider):
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("GROQ_API_KEY", "")

    @property
    def provider_name(self) -> str:
        return "groq"

    def set_api_key(self, api_key: str) -> None:
        self._api_key = api_key

    def generate(self, request: LLMRequest, model_override: Optional[str] = None) -> LLMResponse:
        start_time = time.time()
        model_name = model_override or request.preferred_model or "llama-3.3-70b-versatile"

        if not self._api_key:
            return LLMResponse(
                content="",
                model_used=model_name,
                provider=self.provider_name,
                success=False,
                error_message="GROQ_API_KEY is not configured in environment. Please add it via the AI Vault.",
                latency_ms=(time.time() - start_time) * 1000
            )

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

            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                content = resp_data["choices"][0]["message"]["content"]
                usage = resp_data.get("usage", {})
                in_tok = usage.get("prompt_tokens", 0)
                out_tok = usage.get("completion_tokens", 0)

                pricing = TOKEN_PRICING.get(model_name, {"input": 0.00059, "output": 0.00079})
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
            logger.error(f"Groq API call failed: {e}")
            return LLMResponse(
                content="",
                model_used=model_name,
                provider=self.provider_name,
                success=False,
                error_message=str(e),
                latency_ms=(time.time() - start_time) * 1000
            )
