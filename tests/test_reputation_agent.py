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
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

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
        # These used to require a rating above zero and a non-empty review list,
        # which held only while the agent returned a fixed 4.8 over 142 reviews
        # and three invented reviewers. Whether this profile has reviews is
        # Google's business; the contract is that nothing is reported unless
        # Google answered.
        self.assertIn("live_data_connected", output)
        self.assertIsInstance(output["recent_reviews"], list)
        if output["live_data_connected"]:
            self.assertIsNotNone(output["reputation_overview"]["average_rating"])
        else:
            self.assertEqual(output["recent_reviews"], [])
            self.assertIsNone(output["reputation_overview"]["average_rating"])
            self.assertTrue(output["live_error"])

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
        # `approval_required` implied the reply could then be published from
        # here. It cannot -- the Places API is read-only -- so the payload now
        # says that outright instead.
        self.assertIn("draft_response", output)
        self.assertTrue(output["draft_response"])
        self.assertFalse(output["can_publish_from_here"])
        self.assertIn("draft_method", output)

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
        }, headers=self.auth_headers)
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}", headers=self.auth_headers)
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "reputation-agent")


if __name__ == "__main__":
    unittest.main()
