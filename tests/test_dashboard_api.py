"""
Unit tests for Dashboard API backend endpoints.
"""

import unittest
from fastapi.testclient import TestClient
from dashboard.api import app


class TestDashboardAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        from dashboard.api import generate_admin_token
        from config.settings import ADMIN_EMAIL
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_serve_dashboard_ui(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("AI Digital Marketing Command Center", resp.text)

    def test_health_check(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")

    def test_get_overview(self):
        resp = self.client.get("/api/overview")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("stats", data)
        self.assertFalse(data["stats"]["ads_live_execution"])

    def test_list_agents(self):
        resp = self.client.get("/api/agents")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(len(data["agents"]), 2)

    def test_agent_toggle(self):
        resp = self.client.post("/api/agents/toggle", json={"agent_id": "blog-agent", "action": "pause"}, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["agent"]["paused"])

        resp_resume = self.client.post("/api/agents/toggle", json={"agent_id": "blog-agent", "action": "resume"}, headers=self.auth_headers)
        self.assertEqual(resp_resume.status_code, 200)
        self.assertFalse(resp_resume.json()["agent"]["paused"])

    def test_create_and_list_tasks(self):
        resp = self.client.post("/api/tasks/create", json={
            "agent_id": "blog-agent",
            "task_type": "status",
            "input_data": {"action": "status"},
            "requires_approval": False
        }, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        task_id = resp.json()["task"]["task_id"]

        resp_list = self.client.get("/api/tasks")
        self.assertEqual(resp_list.status_code, 200)
        task_ids = [t["task_id"] for t in resp_list.json()["tasks"]]
        self.assertIn(task_id, task_ids)

    def test_approvals_workflow_api(self):
        resp = self.client.post("/api/tasks/create", json={
            "agent_id": "blog-agent",
            "task_type": "status",
            "input_data": {"action": "status"},
            "requires_approval": True
        }, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        task_id = resp.json()["task"]["task_id"]

        resp_appr_list = self.client.get("/api/approvals")
        self.assertEqual(resp_appr_list.status_code, 200)
        pending_ids = [a["task_id"] for a in resp_appr_list.json()["approvals"]]
        self.assertIn(task_id, pending_ids)

        resp_approve = self.client.post("/api/approvals/approve", json={
            "task_id": task_id,
            "approver": "test_admin",
            "comment": "Approved in unit test"
        }, headers=self.auth_headers)
        self.assertEqual(resp_approve.status_code, 200)
        self.assertIn(resp_approve.json()["task"]["status"], ["APPROVED", "COMPLETED"])

    def test_schedules_api(self):
        resp = self.client.get("/api/schedules")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["count"], 2)

    def test_ai_usage_metrics(self):
        resp = self.client.get("/api/metrics/ai-usage")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("total_tokens_consumed", resp.json())

    def test_system_health_api(self):
        resp = self.client.get("/api/system-health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["overall"], "HEALTHY")
        self.assertIn("ads_safety_guard", data["components"])

    def test_settings_api(self):
        resp = self.client.get("/api/settings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        flags = [s["safety_flag"] for s in data["settings"]]
        self.assertTrue(any("DISABLED" in f for f in flags))

    def test_external_link_report_has_live_urls(self):
        resp = self.client.get("/api/agents/external-link-building-agent/report")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("external_link_metrics", data)
        elm = data["external_link_metrics"]
        self.assertIn("directory_citations", elm)
        self.assertIn("web2_published_articles", elm)
        # Verify direct URLs exist
        citations = elm["directory_citations"]
        self.assertTrue(any("yellowpages.com.au" in c["url"] for c in citations))
        self.assertTrue(all("target_url" in c for c in citations))

    def test_external_link_custom_outreach(self):
        resp = self.client.post("/api/agents/external-link/custom-outreach", json={
            "target_websites": ["https://melbournetraveler.com/luxury-chauffeurs"],
            "landing_page_url": "https://corporatecarsmelbourne.com.au/services/airport-transfers",
            "anchor_text": "Melbourne Airport Transfers",
            "topic": "Airport Travel Guide",
            "use_ai": False
        }, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["output"]["processed_count"], 1)

    def test_external_link_daily_batch(self):
        resp = self.client.post("/api/agents/external-link/daily-batch?batch_size=7", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["output"]["batch_count"], 7)


if __name__ == "__main__":
    unittest.main()

