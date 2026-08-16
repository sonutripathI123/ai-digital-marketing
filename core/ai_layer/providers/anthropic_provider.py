"""
Anthropic Claude Provider Adapter.

Wraps the Anthropic API securely, supporting model overrides, JSON parsing,
token usage tracking, and cost calculation.
"""

import json
import os
import time
try:
    import anthropic
except ImportError:
    anthropic = None

from config import TOKEN_PRICING
from core.ai_layer.base import BaseAIProvider, LLMRequest, LLMResponse


def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    pricing = TOKEN_PRICING.get(model, {"input": 0.003, "output": 0.015})
    cost_in = (tokens_in / 1000.0) * pricing["input"]
    cost_out = (tokens_out / 1000.0) * pricing["output"]
    return round(cost_in + cost_out, 6)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


class AnthropicProvider(BaseAIProvider):
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def generate(self, request: LLMRequest, model_override: Optional[str] = None) -> LLMResponse:
        start_time = time.time()
        if not anthropic:
            return LLMResponse(
                content="",
                model_used=model_override or "claude-3-5-sonnet-20241022",
                provider=self.provider_name,
                success=False,
                error_message="anthropic package is not installed."
            )
        if not self._api_key or self._api_key.startswith("your_"):
            return LLMResponse(
                content="",
                model_used=model_override or "claude-3-5-sonnet-20241022",
                provider=self.provider_name,
                success=False,
                error_message="ANTHROPIC_API_KEY missing or placeholder in environment."
            )

        client = anthropic.Anthropic(api_key=self._api_key)
        model_name = model_override or request.preferred_model or "claude-3-5-sonnet-20241022"

        kwargs = {
            "model": model_name,
            "max_tokens": request.max_tokens,
            "messages": [{"role": "user", "content": request.user_prompt}],
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        retry_count = 0
        last_error = None

        for attempt in range(2):
            try:
                resp = client.messages.create(**kwargs)
                latency = (time.time() - start_time) * 1000
                text = "".join(b.text for b in resp.content if b.type == "text")

                tokens_in = getattr(resp.usage, "input_tokens", 0)
                tokens_out = getattr(resp.usage, "output_tokens", 0)
                cost = calculate_cost(model_name, tokens_in, tokens_out)

                parsed_json = None
                if request.json_output:
                    clean_text = _strip_fences(text)
                    try:
                        parsed_json = json.loads(clean_text)
                    except json.JSONDecodeError as e:
                        if attempt == 0:
                            retry_count += 1
                            continue
                        last_error = f"JSON decode error: {e}"

                return LLMResponse(
                    content=text,
                    parsed_json=parsed_json,
                    model_used=model_name,
                    provider=self.provider_name,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost,
                    latency_ms=latency,
                    success=True,
                    retry_count=retry_count
                )
            except Exception as e:
                last_error = str(e)
                retry_count += 1

        latency = (time.time() - start_time) * 1000
        return LLMResponse(
            content="",
            model_used=model_name,
            provider=self.provider_name,
            latency_ms=latency,
            success=False,
            error_message=f"Anthropic API call failed after retries: {last_error}",
            retry_count=retry_count
        )
