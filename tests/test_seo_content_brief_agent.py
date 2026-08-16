"""
Unit & Integration Tests for Agent #3: SEO Content Brief Agent (`seo-content-brief-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.seo_content_brief_agent import SEOContentBriefAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestSEOContentBriefAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = SEOContentBriefAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "seo-content-brief-agent")
        self.assertEqual(meta.name, "SEO Content Brief Agent")
        self.assertEqual(meta.category, "SEO & Content")
        self.assertTrue(meta.enabled)
        self.assertIn("create_brief", meta.supported_actions)

    def test_run_task_rule_based(self):
        task = AgentTask(
            task_id="test-brief-1",
            agent_id="seo-content-brief-agent",
            task_type="create_brief",
            input_data={
                "action": "create_brief",
                "target_keyword": "executive car hire melbourne",
                "location": "Melbourne CBD",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertEqual(output["target_keyword"], "executive car hire melbourne")
        self.assertGreater(len(output["title_suggestions"]), 0)
        self.assertGreater(len(output["structured_outline"]), 0)

    def test_orchestrator_execution(self):
        task = self.orchestrator.create_task(
            agent_id="seo-content-brief-agent",
            task_type="create_brief",
            input_data={"target_keyword": "corporate chauffeur melbourne"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        self.assertIn("structured_outline", completed_task.output_data)

    def test_fastapi_endpoints(self):
        resp_create = self.client.post("/api/tasks/create", json={
            "agent_id": "seo-content-brief-agent",
            "task_type": "create_brief",
            "input_data": {"target_keyword": "airport transfer south yarra"},
            "requires_approval": False
        })
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}")
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "seo-content-brief-agent")


if __name__ == "__main__":
    unittest.main()
