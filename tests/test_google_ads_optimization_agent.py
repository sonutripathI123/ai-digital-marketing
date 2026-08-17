"""
Unit & Integration Tests for Agent #10: Google Ads Optimization Agent (`google-ads-optimization-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.google_ads_optimization_agent import GoogleAdsOptimizationAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestGoogleAdsOptimizationAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = GoogleAdsOptimizationAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "google-ads-optimization-agent")
        self.assertEqual(meta.name, "Google Ads Optimization Agent")
        self.assertEqual(meta.category, "Paid Advertising")
        self.assertTrue(meta.enabled)
        self.assertIn("recommend_optimizations", meta.supported_actions)

    def test_run_task_rule_based(self):
        task = AgentTask(
            task_id="test-gopt-1",
            agent_id="google-ads-optimization-agent",
            task_type="recommend_optimizations",
            input_data={
                "action": "recommend_optimizations",
                "account_id": "123-456-7890",
                "optimization_goal": "reduce_cpa",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertEqual(output["account_id"], "123-456-7890")
        self.assertIn("Requires Human Approval", output["approval_status"])
        self.assertGreater(len(output["recommended_negative_keywords"]), 0)
        self.assertGreater(len(output["proposed_bid_adjustments"]), 0)

    def test_orchestrator_execution(self):
        task = self.orchestrator.create_task(
            agent_id="google-ads-optimization-agent",
            task_type="recommend_optimizations",
            input_data={"account_id": "123-456-7890"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        self.assertIn("recommended_negative_keywords", completed_task.output_data)

    def test_fastapi_endpoints(self):
        resp_create = self.client.post("/api/tasks/create", json={
            "agent_id": "google-ads-optimization-agent",
            "task_type": "recommend_optimizations",
            "input_data": {"account_id": "123-456-7890"},
            "requires_approval": False
        }, headers=self.auth_headers)
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}", headers=self.auth_headers)
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "google-ads-optimization-agent")


if __name__ == "__main__":
    unittest.main()
