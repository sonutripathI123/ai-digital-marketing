"""
Unit & Integration Tests for Competitor Ad Spy & Intelligence Agent (`competitor-ad-spy-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.competitor_ad_spy_agent import CompetitorAdSpyAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestCompetitorAdSpyAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = CompetitorAdSpyAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "competitor-ad-spy-agent")
        self.assertEqual(meta.name, "Competitor Ad Spy & Intelligence Agent")
        self.assertEqual(meta.category, "Competitor & Ad Intelligence")
        self.assertTrue(meta.enabled)
        self.assertIn("spy_competitor_ads", meta.supported_actions)

    def test_run_task_ad_spy_execution(self):
        task = AgentTask(
            task_id="test-adspy-1",
            agent_id="competitor-ad-spy-agent",
            task_type="spy_competitor_ads",
            input_data={
                "action": "spy_competitor_ads",
                "competitor_url": "https://chauffeurcarsmelbourne.com.au/",
                "location": "Melbourne, Victoria",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertEqual(output["competitor_domain"], "chauffeurcarsmelbourne.com.au")
        self.assertIn("google_ads_intelligence", output)
        self.assertIn("meta_ads_intelligence", output)
        self.assertIn("winning_counter_strategy", output)

        # Verify Google Ads Section
        g_data = output["google_ads_intelligence"]
        self.assertGreaterEqual(len(g_data["ad_variations"]), 1)
        self.assertGreaterEqual(len(g_data["targeted_keywords"]), 1)
        self.assertTrue(any("headline_1" in ad for ad in g_data["ad_variations"]))

        # Verify Meta Ads Section
        m_data = output["meta_ads_intelligence"]
        self.assertGreaterEqual(len(m_data["active_ads"]), 1)
        self.assertTrue(any("primary_text" in ad for ad in m_data["active_ads"]))

        # Verify Official Transparency Verification Links
        self.assertIn("official_verification_links", output)
        links = output["official_verification_links"]
        self.assertIn("meta_ad_library", links)
        self.assertIn("google_ads_transparency", links)
        self.assertIn("facebook.com/ads/library", links["meta_ad_library"])
        self.assertIn("adstransparency.google.com", links["google_ads_transparency"])

    def test_api_ad_spy_analyze_endpoint(self):
        resp = self.client.post("/api/agents/ad-spy/analyze", json={
            "competitor_url": "https://melbournechauffeurcars.com.au/",
            "location": "Melbourne CBD",
            "use_ai": False
        }, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("output", data)
        self.assertEqual(data["output"]["competitor_domain"], "melbournechauffeurcars.com.au")

    def test_api_ad_spy_history_endpoint(self):
        resp = self.client.get("/api/agents/ad-spy/history")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("reports", data)


if __name__ == "__main__":
    unittest.main()
