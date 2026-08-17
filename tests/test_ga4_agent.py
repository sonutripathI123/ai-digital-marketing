"""
Unit & Integration Tests for Agent #8: GA4 Reporting Agent (`ga4-reporting-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.ga4_reporting_agent import GA4ReportingAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestGA4ReportingAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = GA4ReportingAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "ga4-reporting-agent")
        self.assertEqual(meta.name, "GA4 Reporting Agent")
        self.assertEqual(meta.category, "Analytics & Reporting")
        self.assertTrue(meta.enabled)
        self.assertIn("fetch_overview", meta.supported_actions)

    def test_run_task_rule_based(self):
        task = AgentTask(
            task_id="test-ga4-1",
            agent_id="ga4-reporting-agent",
            task_type="fetch_overview",
            input_data={
                "action": "fetch_overview",
                "property_name": "Corporate Cars Melbourne GA4",
                "date_range": "last_28_days",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertEqual(output["property_name"], "Corporate Cars Melbourne GA4")
        self.assertGreater(output["overview_metrics"]["total_users"], 0)
        self.assertGreater(len(output["acquisition_channel_breakdown"]), 0)
        self.assertGreater(len(output["top_landing_pages"]), 0)

    def test_orchestrator_execution(self):
        task = self.orchestrator.create_task(
            agent_id="ga4-reporting-agent",
            task_type="fetch_overview",
            input_data={"property_name": "Corporate Cars Melbourne GA4"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        self.assertIn("overview_metrics", completed_task.output_data)

    def test_fastapi_endpoints(self):
        resp_create = self.client.post("/api/tasks/create", json={
            "agent_id": "ga4-reporting-agent",
            "task_type": "fetch_overview",
            "input_data": {"property_name": "Corporate Cars Melbourne GA4"},
            "requires_approval": False
        }, headers=self.auth_headers)
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}", headers=self.auth_headers)
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "ga4-reporting-agent")


if __name__ == "__main__":
    unittest.main()
