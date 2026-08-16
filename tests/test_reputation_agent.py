"""
Unit & Integration Tests for Agent #13: Review / Reputation Agent (`reputation-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.reputation_agent import ReviewReputationAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestReviewReputationAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = ReviewReputationAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "reputation-agent")
        self.assertEqual(meta.name, "Review / Reputation Agent")
        self.assertEqual(meta.category, "Customer Experience")
        self.assertTrue(meta.enabled)
        self.assertIn("fetch_reviews", meta.supported_actions)

    def test_run_task_rule_based_fetch(self):
        task = AgentTask(
            task_id="test-rep-1",
            agent_id="reputation-agent",
            task_type="fetch_reviews",
            input_data={
                "action": "fetch_reviews",
                "platform": "google",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertGreater(output["reputation_overview"]["average_rating"], 0)
        self.assertGreater(len(output["recent_reviews"]), 0)

    def test_run_task_draft_reply(self):
        task = AgentTask(
            task_id="test-rep-draft-1",
            agent_id="reputation-agent",
            task_type="draft_reply",
            input_data={
                "action": "draft_reply",
                "platform": "google",
                "rating": 5,
                "review_text": "Great service!",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        output = res["output"]
        self.assertTrue(output["approval_required"])
        self.assertIn("draft_response", output)

    def test_orchestrator_execution(self):
        task = self.orchestrator.create_task(
            agent_id="reputation-agent",
            task_type="fetch_reviews",
            input_data={"platform": "google"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        self.assertIn("reputation_overview", completed_task.output_data)

    def test_fastapi_endpoints(self):
        resp_create = self.client.post("/api/tasks/create", json={
            "agent_id": "reputation-agent",
            "task_type": "fetch_reviews",
            "input_data": {"platform": "trustpilot"},
            "requires_approval": False
        })
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}")
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "reputation-agent")


if __name__ == "__main__":
    unittest.main()
