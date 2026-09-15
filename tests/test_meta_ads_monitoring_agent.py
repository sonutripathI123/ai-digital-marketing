"""
Unit & Integration Tests for Agent #11: Meta Ads Monitoring Agent (`meta-ads-monitoring-agent`).
"""

import unittest
from fastapi.testclient import TestClient

from agents.meta_ads_monitoring_agent import MetaAdsMonitoringAgent
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from core.orchestrator.master import MasterOrchestrator
from dashboard.api import app


class TestMetaAdsMonitoringAgent(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.agent = MetaAdsMonitoringAgent()
        self.orchestrator.register_agent(self.agent)
        self.client = TestClient(app)
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_agent_metadata(self):
        meta = self.agent.metadata
        self.assertEqual(meta.agent_id, "meta-ads-monitoring-agent")
        self.assertEqual(meta.name, "Meta Ads Monitoring Agent")
        self.assertEqual(meta.category, "Paid Advertising")
        self.assertTrue(meta.enabled)
        self.assertIn("monitor_performance", meta.supported_actions)

    def test_run_task_rule_based(self):
        task = AgentTask(
            task_id="test-mads-1",
            agent_id="meta-ads-monitoring-agent",
            task_type="monitor_performance",
            input_data={
                "action": "monitor_performance",
                "ad_account_id": "act_987654321",
                "use_ai": False
            }
        )
        res = self.agent.run_task(task, self.router)
        self.assertIn("output", res)
        output = res["output"]
        self.assertIn("PROTECTED", output["safety_guard_status"])

        # These used to require a spend above zero and at least one placement,
        # and passed only because the agent carried two campaigns in its own
        # source -- $640 and $480, 50 conversions, a ROAS of 3.65 and 3.90 --
        # for an account it had never called. Whether this account runs ads is
        # Meta's business; the contract is that nothing is reported unless Meta
        # answered.
        self.assertIn("live_data_connected", output)
        self.assertIsInstance(output["campaign_performance"], list)
        blob = str(output)
        for invented in ("placement_performance", "roas_ratio", "Executive Chauffeur Branding",
                         "Corporate Event Transport", "Frequency is healthy"):
            self.assertNotIn(invented, blob)

        if output["live_data_connected"]:
            self.assertIn("total_spend", output["account_summary"])
        else:
            self.assertEqual(output["campaign_performance"], [])
            self.assertEqual(output["account_summary"], {})
            self.assertIsNone(output["ad_fatigue"])
            self.assertTrue(output["live_error"])

    def test_safety_guard_blocks_mutation(self):
        task = AgentTask(
            task_id="test-mads-block-1",
            agent_id="meta-ads-monitoring-agent",
            task_type="create_meta_campaign",
            input_data={
                "action": "create_meta_campaign",
                "campaign_name": "Unapproved Live Meta Campaign"
            }
        )
        res = self.agent.run_task(task, self.router)
        output = res["output"]
        self.assertEqual(output["status"], "BLOCKED_BY_SAFETY_GUARD")

    def test_orchestrator_execution(self):
        task = self.orchestrator.create_task(
            agent_id="meta-ads-monitoring-agent",
            task_type="monitor_performance",
            input_data={"ad_account_id": "act_987654321"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        self.assertIn("account_summary", completed_task.output_data)

    def test_fastapi_endpoints(self):
        resp_create = self.client.post("/api/tasks/create", json={
            "agent_id": "meta-ads-monitoring-agent",
            "task_type": "monitor_performance",
            "input_data": {"ad_account_id": "act_987654321"},
            "requires_approval": False
        }, headers=self.auth_headers)
        self.assertEqual(resp_create.status_code, 200)
        task_id = resp_create.json()["task"]["task_id"]

        resp_exec = self.client.post(f"/api/tasks/execute/{task_id}", headers=self.auth_headers)
        self.assertEqual(resp_exec.status_code, 200)
        data = resp_exec.json()
        self.assertEqual(data["task"]["status"], "COMPLETED")
        self.assertEqual(data["task"]["agent_id"], "meta-ads-monitoring-agent")


if __name__ == "__main__":
    unittest.main()
