"""
Unit & Integration Tests for Agent #12: Social Media Analytics Agent (`social-analytics-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.social_analytics_agent import SocialAnalyticsAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestSocialAnalyticsAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = SocialAnalyticsAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "social-analytics-agent")
        self.assertEqual(meta.name, "Social Media Analytics Agent")
        self.assertEqual(meta.category, "Social Media")
        self.assertTrue(meta.enabled)
        self.assertIn("fetch_analytics", meta.supported_actions)

    def test_run_task_rule_based(self):
        task = AgentTask(
            task_id="test-sanalytics-1",
            agent_id="social-analytics-agent",
            task_type="fetch_analytics",
            input_data={
                "action": "fetch_analytics",
                "platform": "all",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertGreater(output["overall_summary"]["total_followers"], 0)
        self.assertGreater(len(output["platform_breakdown"]), 0)

    def test_orchestrator_execution(self):
        task = self.orchestrator.create_task(
            agent_id="social-analytics-agent",
            task_type="fetch_analytics",
            input_data={"platform": "instagram"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        self.assertIn("overall_summary", completed_task.output_data)

    def test_fastapi_endpoints(self):
        resp_create = self.client.post("/api/tasks/create", json={
            "agent_id": "social-analytics-agent",
            "task_type": "fetch_analytics",
            "input_data": {"platform": "linkedin"},
            "requires_approval": False
        }, headers=self.auth_headers)
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}", headers=self.auth_headers)
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "social-analytics-agent")


if __name__ == "__main__":
    unittest.main()
