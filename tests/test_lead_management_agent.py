"""
Unit & Integration Tests for Agent #14: Lead Management Agent (`lead-management-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.lead_management_agent import LeadManagementAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestLeadManagementAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = LeadManagementAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "lead-management-agent")
        self.assertEqual(meta.name, "Lead Management Agent")
        self.assertEqual(meta.category, "Sales & CRM")
        self.assertTrue(meta.enabled)
        self.assertIn("process_lead", meta.supported_actions)

    def test_run_task_rule_based_process(self):
        task = AgentTask(
            task_id="test-lead-1",
            agent_id="lead-management-agent",
            task_type="process_lead",
            input_data={
                "action": "process_lead",
                "client_name": "Test Client",
                "service_type": "Airport Transfer",
                "estimated_value_usd": 300.0,
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        # The agent no longer echoes a client name and a score back from the
        # caller's own input. It reads the website's real form submissions, so
        # the contract is that it either reports them or says it could not.
        self.assertIn("live_data_connected", output)
        self.assertIsInstance(output["recent_leads"], list)
        # A score or deal value must never appear -- those literals were read
        # by the monthly report and printed as revenue.
        blob = str(output)
        self.assertNotIn("lead_score", blob)
        self.assertNotIn("estimated_value_usd", blob)
        self.assertNotIn("total_pipeline_value_usd", blob)
        if not output["live_data_connected"]:
            self.assertEqual(output["recent_leads"], [])
            self.assertTrue(output["live_error"])

    def test_run_task_draft_followup(self):
        task = AgentTask(
            task_id="test-lead-draft-1",
            agent_id="lead-management-agent",
            task_type="draft_followup",
            input_data={
                "action": "draft_followup",
                "email": "someone@example.com",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        output = res["output"]
        self.assertIn("draft_email", output)
        self.assertTrue(output["draft_email"])
        # `approval_required` implied the draft could then be sent from here.
        # No mail transport is wired to this dashboard, so it cannot be.
        self.assertFalse(output["can_send_from_here"])
        # The old template quoted a price for an enquiry nobody had read.
        self.assertNotIn("$", output["draft_email"])

    def test_orchestrator_execution(self):
        task = self.orchestrator.create_task(
            agent_id="lead-management-agent",
            task_type="process_lead",
            input_data={"action": "lead_report"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        # `processed_lead` was the caller's own input echoed back with a score
        # attached. The report now describes real submissions, or says it could
        # not read them.
        self.assertIn("pipeline_summary", completed_task.output_data)
        self.assertIn("live_data_connected", completed_task.output_data)

    def test_fastapi_endpoints(self):
        resp_create = self.client.post("/api/tasks/create", json={
            "agent_id": "lead-management-agent",
            "task_type": "process_lead",
            "input_data": {"client_name": "API Test Client"},
            "requires_approval": False
        }, headers=self.auth_headers)
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}", headers=self.auth_headers)
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "lead-management-agent")


if __name__ == "__main__":
    unittest.main()
