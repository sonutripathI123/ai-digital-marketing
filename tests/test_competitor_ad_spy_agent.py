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

        # These used to require google_ads_intelligence with ad_variations and
        # targeted_keywords, and meta_ads_intelligence with active_ads -- all of
        # which passed only because the agent wrote a competitor's ad copy,
        # sitelinks, CPCs and monthly spend into its own source and made no HTTP
        # request at all. Neither platform exposes those ads through an API, so
        # the contract now is that the agent says so.
        self.assertFalse(output["competitor_ads_readable"])
        self.assertNotIn("google_ads_intelligence", output)
        self.assertNotIn("meta_ads_intelligence", output)
        self.assertNotIn("winning_counter_strategy", output)

        blob = str(output)
        for invented in ("estimated_monthly_ad_spend", "estimated_cpc", "search_volume",
                         "started_running", "Running 45+ days"):
            self.assertNotIn(invented, blob)

        # The landing page is the one thing that can be observed, so it is
        # either measured or the reason it was not is given.
        landing = output["measured_landing_page"]
        if landing["measured"]:
            self.assertIn("page_title", landing)
            self.assertIn("word_count", landing)
        else:
            self.assertTrue(landing.get("error"))

        # The verification links are the honest deliverable: they work.
        links = output["verification_links"]
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
        resp = self.client.get("/api/agents/ad-spy/history", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("reports", data)


if __name__ == "__main__":
    unittest.main()
