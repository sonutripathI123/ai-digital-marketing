"""
Unit & Integration Tests for Agent #15: Monthly Marketing Report Agent (`monthly-report-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.monthly_report_agent import MonthlyReportAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestMonthlyReportAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = MonthlyReportAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "monthly-report-agent")
        self.assertEqual(meta.name, "Monthly Marketing Report Agent")
        self.assertEqual(meta.category, "Executive Reporting")
        self.assertTrue(meta.enabled)
        self.assertIn("generate_report", meta.supported_actions)

    def test_run_task_rule_based_report(self):
        task = AgentTask(
            task_id="test-mreport-1",
            agent_id="monthly-report-agent",
            task_type="generate_report",
            input_data={
                "action": "generate_report",
                "month": "August 2026",
                "format": "markdown",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertEqual(output["reporting_period"], "August 2026")
        self.assertIn("executive_summary", output)
        self.assertIn("channel_performance", output)
        self.assertIn("seo_and_content", output["channel_performance"])

    def test_orchestrator_execution(self):
        task = self.orchestrator.create_task(
            agent_id="monthly-report-agent",
            task_type="generate_report",
            input_data={"month": "August 2026"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        self.assertIn("channel_performance", completed_task.output_data)

    def test_fastapi_endpoints(self):
        resp_create = self.client.post("/api/tasks/create", json={
            "agent_id": "monthly-report-agent",
            "task_type": "generate_report",
            "input_data": {"month": "August 2026"},
            "requires_approval": False
        })
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}")
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "monthly-report-agent")


if __name__ == "__main__":
    unittest.main()
