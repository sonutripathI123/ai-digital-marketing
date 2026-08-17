"""
Unit & Integration Tests for Agent #19: Page SEO Doctor & Google Algorithm Optimizer Agent (`page-optimizer-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.page_optimizer_agent import PageOptimizerAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestPageOptimizerAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = PageOptimizerAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "page-optimizer-agent")
        self.assertEqual(meta.name, "Page SEO Doctor & Google Algorithm Optimizer Agent")
        self.assertEqual(meta.category, "SEO & Content")
        self.assertTrue(meta.enabled)
        self.assertIn("audit_page", meta.supported_actions)
        self.assertIn("heading_optimizer", meta.supported_actions)
        self.assertIn("hcu_content_gap", meta.supported_actions)

    def test_run_task_rule_based(self):
        task = AgentTask(
            task_id="test-page-opt-1",
            agent_id="page-optimizer-agent",
            task_type="audit_page",
            input_data={
                "action": "audit_page",
                "url": "https://corporatecarsmelbourne.com.au/chauffeur-vs-rideshare-airport-fitzroy/",
                "focus_keyword": "chauffeur vs rideshare melbourne",
                "location": "Melbourne, Victoria",
                "site_id": "ccm",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertEqual(output["audited_url"], "https://corporatecarsmelbourne.com.au/chauffeur-vs-rideshare-airport-fitzroy/")
        self.assertGreater(output["overall_health_score"], 0)
        self.assertIn("grade", output)
        self.assertIn("algorithm_scores", output)
        self.assertIn("optimized_headings_recommendations", output)
        self.assertIn("internal_linking_recommendations", output)
        self.assertIn("ready_to_paste_schema_json", output)
        self.assertIn("executive_action_checklist", output)

    def test_multi_site_adaptation(self):
        task = AgentTask(
            task_id="test-page-opt-opal",
            agent_id="page-optimizer-agent",
            task_type="audit_page",
            input_data={
                "action": "audit_page",
                "url": "https://www.opalchauffeurs.com.au/services/airport-transfers/",
                "focus_keyword": "airport transfers melbourne",
                "location": "Melbourne, Victoria",
                "site_id": "opal",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        output = res["output"]
        self.assertEqual(output["target_brand"], "Opal Chauffeurs")
        self.assertEqual(output["target_domain"], "https://www.opalchauffeurs.com.au")
        self.assertIn("Opal Chauffeurs", output["ready_to_paste_schema_json"])

    def test_fastapi_audit_endpoint(self):
        resp = self.client.post("/api/agents/page-optimizer/audit", json={
            "url": "https://corporatecarsmelbourne.com.au/chauffeur-melbourne-airport/",
            "focus_keyword": "melbourne airport chauffeur",
            "location": "Melbourne, VIC",
            "site_id": "ccm",
            "use_ai": False
        }, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("output", data)
        self.assertGreater(data["output"]["overall_health_score"], 0)

    def test_fastapi_history_endpoint(self):
        resp = self.client.get("/api/agents/page-optimizer/history")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("reports", data)


if __name__ == "__main__":
    unittest.main()
