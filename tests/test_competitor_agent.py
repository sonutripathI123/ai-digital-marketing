"""
Unit & Integration Tests for Agent #2: Competitor Analysis Agent (`competitor-analysis-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.competitor_agent import CompetitorAnalysisAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestCompetitorAnalysisAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = CompetitorAnalysisAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "competitor-analysis-agent")
        self.assertEqual(meta.name, "Competitor Analysis Agent")
        self.assertEqual(meta.category, "SEO & Content")
        self.assertTrue(meta.enabled)
        self.assertIn("analyze", meta.supported_actions)

    def test_run_task_rule_based(self):
        task = AgentTask(
            task_id="test-comp-1",
            agent_id="competitor-analysis-agent",
            task_type="analyze",
            input_data={
                "action": "analyze",
                "competitor_urls": ["comp1.com", "comp2.com"],
                "target_keyword": "airport transfer melbourne",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertEqual(output["target_keyword"], "airport transfer melbourne")
        self.assertEqual(output["competitors_analyzed_count"], 2)
        self.assertGreater(len(output["actionable_recommendations"]), 0)

    def test_orchestrator_execution(self):
        task = self.orchestrator.create_task(
            agent_id="competitor-analysis-agent",
            task_type="analyze",
            input_data={"target_keyword": "corporate chauffeur melbourne"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        self.assertIn("competitor_insights", completed_task.output_data)

    def test_fastapi_endpoints(self):
        resp_create = self.client.post("/api/tasks/create", json={
            "agent_id": "competitor-analysis-agent",
            "task_type": "analyze",
            "input_data": {"competitor_urls": ["luxurydriver.com"]},
            "requires_approval": False
        }, headers=self.auth_headers)
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}", headers=self.auth_headers)
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "competitor-analysis-agent")


if __name__ == "__main__":
    unittest.main()
