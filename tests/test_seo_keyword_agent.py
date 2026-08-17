"""
Unit & Integration Tests for Agent #1: SEO Keyword Research Agent (`seo-keyword-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.seo_keyword_agent import SEOKeywordAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestSEOKeywordAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = SEOKeywordAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "seo-keyword-agent")
        self.assertEqual(meta.name, "SEO Keyword Research Agent")
        self.assertEqual(meta.category, "SEO & Content")
        self.assertTrue(meta.enabled)
        self.assertIn("research", meta.supported_actions)

    def test_run_task_rule_based(self):
        task = AgentTask(
            task_id="test-kw-1",
            agent_id="seo-keyword-agent",
            task_type="research",
            input_data={
                "action": "research",
                "seed_keyword": "airport transfer",
                "location": "Melbourne CBD",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertEqual(output["seed_keyword"], "airport transfer")
        self.assertEqual(output["target_location"], "Melbourne CBD")
        self.assertIn("primary_keyword", output)
        self.assertGreater(output["expanded_opportunities_count"], 0)

    def test_orchestrator_execution(self):
        task = self.orchestrator.create_task(
            agent_id="seo-keyword-agent",
            task_type="research",
            input_data={"seed_keyword": "corporate chauffeur", "location": "Tullamarine"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        self.assertIn("primary_keyword", completed_task.output_data)

    def test_fastapi_endpoints(self):
        resp_create = self.client.post("/api/tasks/create", json={
            "agent_id": "seo-keyword-agent",
            "task_type": "research",
            "input_data": {"seed_keyword": "wedding car hire", "location": "South Yarra"},
            "requires_approval": False
        }, headers=self.auth_headers)
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}", headers=self.auth_headers)
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "seo-keyword-agent")


if __name__ == "__main__":
    unittest.main()
