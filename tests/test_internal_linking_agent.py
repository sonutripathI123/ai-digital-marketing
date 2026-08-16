"""
Unit & Integration Tests for Agent #5: Internal Linking Agent (`internal-linking-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.internal_linking_agent import InternalLinkingAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestInternalLinkingAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = InternalLinkingAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "internal-linking-agent")
        self.assertEqual(meta.name, "Internal Linking Agent")
        self.assertEqual(meta.category, "SEO & Content")
        self.assertTrue(meta.enabled)
        self.assertIn("scan_opportunities", meta.supported_actions)

    def test_run_task_rule_based(self):
        task = AgentTask(
            task_id="test-link-1",
            agent_id="internal-linking-agent",
            task_type="scan_opportunities",
            input_data={
                "action": "scan_opportunities",
                "source_url": "/blog/melbourne-airport-guide",
                "topic": "Airport Chauffeur",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertEqual(output["source_url"], "/blog/melbourne-airport-guide")
        self.assertGreater(output["total_opportunities_found"], 0)
        self.assertIn("linking_opportunities", output)

    def test_orchestrator_execution(self):
        task = self.orchestrator.create_task(
            agent_id="internal-linking-agent",
            task_type="scan_opportunities",
            input_data={"topic": "Corporate Travel"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        self.assertIn("linking_opportunities", completed_task.output_data)

    def test_fastapi_endpoints(self):
        resp_create = self.client.post("/api/tasks/create", json={
            "agent_id": "internal-linking-agent",
            "task_type": "scan_opportunities",
            "input_data": {"source_url": "/suburbs/south-yarra"},
            "requires_approval": False
        })
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}")
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "internal-linking-agent")


if __name__ == "__main__":
    unittest.main()
