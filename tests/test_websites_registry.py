"""
Unit tests for Multi-Website Registry, Switching, and Site-Aware Telemetry.
"""

import unittest
from fastapi.testclient import TestClient
from config.websites import WebsiteProfile
from dashboard.api import app, websites_mgr


class TestWebsitesRegistry(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.mgr = websites_mgr
        self.mgr.delete_website("test-sydney-transfers")

    def tearDown(self):
        self.mgr.delete_website("test-sydney-transfers")

    def test_default_websites_present(self):
        sites = self.mgr.list_all()
        site_ids = [s.site_id for s in sites]
        self.assertIn("ccm", site_ids)
        self.assertIn("opal", site_ids)

    def test_api_list_websites(self):
        resp = self.client.get("/api/websites")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(data["count"], 2)
        site_ids = [s["site_id"] for s in data["websites"]]
        self.assertIn("ccm", site_ids)
        self.assertIn("opal", site_ids)

    def test_api_add_new_website(self):
        new_site_data = {
            "site_id": "test-sydney-transfers",
            "name": "Sydney Luxury Transfers",
            "domain": "https://sydneytransfers.example.com",
            "location": "Sydney, NSW",
            "niche": "Executive Airport Transfers",
            "default_category": "Chauffeur Services",
            "color_accent": "#10b981"
        }
        resp = self.client.post("/api/websites", json=new_site_data)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["website"]["site_id"], "test-sydney-transfers")

        # Verify retrieval
        detail_resp = self.client.get("/api/websites/test-sydney-transfers")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["website"]["name"], "Sydney Luxury Transfers")

        # Cleanup
        self.mgr.delete_website("test-sydney-transfers")

    def test_site_aware_overview(self):
        resp_ccm = self.client.get("/api/overview?site_id=ccm")
        self.assertEqual(resp_ccm.status_code, 200)
        data_ccm = resp_ccm.json()
        self.assertEqual(data_ccm["current_website"]["site_id"], "ccm")

        resp_opal = self.client.get("/api/overview?site_id=opal")
        self.assertEqual(resp_opal.status_code, 200)
        data_opal = resp_opal.json()
        self.assertEqual(data_opal["current_website"]["site_id"], "opal")

        resp_all = self.client.get("/api/overview?site_id=all")
        self.assertEqual(resp_all.status_code, 200)
        data_all = resp_all.json()
        self.assertEqual(data_all["current_website"]["site_id"], "all")

    def test_site_aware_blog_report(self):
        resp_ccm = self.client.get("/api/agents/blog-agent/report?site_id=ccm")
        self.assertEqual(resp_ccm.status_code, 200)
        data_ccm = resp_ccm.json()
        self.assertEqual(data_ccm["site_id"], "ccm")
        self.assertIn("blog_metrics", data_ccm)

        resp_opal = self.client.get("/api/agents/blog-agent/report?site_id=opal")
        self.assertEqual(resp_opal.status_code, 200)
        data_opal = resp_opal.json()
        self.assertEqual(data_opal["site_id"], "opal")
        self.assertEqual(data_opal["site_name"], "Opal Chauffeurs")

    def test_create_task_with_site_id(self):
        resp = self.client.post("/api/tasks/create", json={
            "agent_id": "seo-keyword-agent",
            "task_type": "research",
            "input_data": {"seed": "luxury transfers"},
            "site_id": "opal"
        })
        self.assertEqual(resp.status_code, 200)
        task = resp.json()["task"]
        self.assertEqual(task["input_data"]["site_id"], "opal")


if __name__ == "__main__":
    unittest.main()
