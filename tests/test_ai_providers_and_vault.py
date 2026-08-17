"""
Unit & Integration Tests for Multi-Provider AI Engine & API Key Vault.
"""

import os
import unittest
from fastapi.testclient import TestClient

from core.ai_layer.router import ModelRouter
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.providers.anthropic_provider import AnthropicProvider
from core.ai_layer.providers.gemini_provider import GeminiProvider
from core.ai_layer.providers.openai_provider import OpenAIProvider
from core.ai_layer.providers.deepseek_provider import DeepSeekProvider
from core.ai_layer.providers.groq_provider import GroqProvider
from core.ai_layer.providers.custom_provider import CustomAIProvider
from dashboard.api import app


class TestAIProvidersAndVault(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.client = TestClient(app)
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_providers_initialization(self):
        self.assertEqual(len(self.router._providers), 7)
        self.assertIn("anthropic", self.router._providers)
        self.assertIn("gemini", self.router._providers)
        self.assertIn("openai", self.router._providers)
        self.assertIn("deepseek", self.router._providers)
        self.assertIn("groq", self.router._providers)
        self.assertIn("custom", self.router._providers)
        self.assertIn("mock", self.router._providers)

    def test_provider_status_metadata(self):
        status_list = self.router.get_all_providers_status()
        self.assertEqual(len(status_list), 6)
        provider_ids = [p["id"] for p in status_list]
        self.assertIn("anthropic", provider_ids)
        self.assertIn("gemini", provider_ids)
        self.assertIn("openai", provider_ids)
        self.assertIn("deepseek", provider_ids)
        self.assertIn("groq", provider_ids)
        self.assertIn("custom", provider_ids)

    def test_switch_primary_provider(self):
        success = self.router.set_primary_provider("openai")
        self.assertTrue(success)
        self.assertEqual(self.router.primary_provider_name, "openai")
        self.assertEqual(self.router.get_provider().provider_name, "openai")

        # Reset back to anthropic
        self.router.set_primary_provider("anthropic")
        self.assertEqual(self.router.primary_provider_name, "anthropic")

    def test_fastapi_get_providers_endpoint(self):
        resp = self.client.get("/api/ai/providers")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("providers", data)
        self.assertIn("primary_provider", data)

    def test_fastapi_save_key_endpoint(self):
        resp = self.client.post("/api/ai/providers/save-key", json={
            "provider": "deepseek",
            "api_key": "sk-testdeepseekkey12345678",
            "default_model": "deepseek-chat",
            "is_primary": False
        }, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["provider"], "deepseek")

    def test_fastapi_set_primary_endpoint(self):
        resp = self.client.post("/api/ai/providers/set-primary", json={
            "provider": "anthropic"
        }, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["primary_provider"], "anthropic")

    def test_fastapi_test_key_endpoint(self):
        resp = self.client.post("/api/ai/providers/test", json={
            "provider": "openai",
            "api_key": "sk-testopenaikey1234"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")


if __name__ == "__main__":
    unittest.main()
