"""
Unit tests for Provider-Independent AI Abstraction Layer.
"""

import unittest
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.providers.anthropic_provider import calculate_cost
from core.ai_layer.providers.gemini_provider import GeminiProvider
from core.ai_layer.providers.mock_provider import MockAIProvider


class TestAILayer(unittest.TestCase):
    def test_mock_provider_generation(self):
        provider = MockAIProvider(default_response="Test response content")
        req = LLMRequest(user_prompt="Hello AI", task_type=TaskComplexity.ROUTINE)

        resp = provider.generate(req)
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "mock")
        self.assertEqual(resp.content, "Test response content")
        self.assertGreater(resp.tokens_in, 0)
        self.assertGreater(resp.tokens_out, 0)

    def test_mock_provider_json_output(self):
        provider = MockAIProvider()
        req = LLMRequest(user_prompt="Generate post", json_output=True)

        resp = provider.generate(req)
        self.assertTrue(resp.success)
        self.assertIsNotNone(resp.parsed_json)
        self.assertIn("caption", resp.parsed_json)

    def test_gemini_provider_interface_fallback_without_key(self):
        provider = GeminiProvider(api_key="")
        req = LLMRequest(user_prompt="Test Gemini")

        resp = provider.generate(req)
        self.assertFalse(resp.success)
        self.assertIn("GEMINI_API_KEY is not configured", resp.error_message)

    def test_anthropic_cost_calculation(self):
        cost = calculate_cost("claude-3-5-sonnet-20241022", tokens_in=1000, tokens_out=1000)
        self.assertEqual(cost, 0.018)


if __name__ == "__main__":
    unittest.main()
