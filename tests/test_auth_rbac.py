"""
Unit and Integration Tests for Role-Based Access Control (RBAC) & Admin Authentication.
"""

import unittest
from fastapi.testclient import TestClient
from config.settings import ADMIN_EMAIL, ADMIN_PASSWORD
from dashboard.api import app, generate_admin_token, verify_token


class TestAuthRBAC(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.valid_token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.valid_token}"}

    def test_token_generation_and_verification(self):
        token = generate_admin_token(ADMIN_EMAIL)
        self.assertIsNotNone(token)
        payload = verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["email"], ADMIN_EMAIL)
        self.assertEqual(payload["role"], "admin")

    def test_invalid_token_verification(self):
        self.assertIsNone(verify_token("invalid.token.structure"))
        self.assertIsNone(verify_token(None))
        self.assertIsNone(verify_token(""))

    def test_login_success(self):
        resp = self.client.post("/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("token", data)
        self.assertEqual(data["role"], "admin")

    def test_login_failure_wrong_password(self):
        resp = self.client.post("/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "WrongPassword123"
        })
        self.assertEqual(resp.status_code, 401)
        data = resp.json()
        self.assertIn("Invalid", data["detail"])

    def test_login_failure_wrong_email(self):
        resp = self.client.post("/api/auth/login", json={
            "email": "intruder@gmail.com",
            "password": ADMIN_PASSWORD
        })
        self.assertEqual(resp.status_code, 401)

    def test_auth_session_unauthenticated(self):
        resp = self.client.get("/api/auth/session")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["is_admin"])
        self.assertEqual(data["role"], "viewer")

    def test_auth_session_authenticated(self):
        resp = self.client.get("/api/auth/session", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_admin"])
        self.assertEqual(data["role"], "admin")

    def test_public_read_endpoints_accessible_without_auth(self):
        # Visitors can view overview, telemetry, reports, tasks, websites
        endpoints = [
            "/api/overview",
            "/api/agents",
            "/api/tasks",
            "/api/approvals",
            "/api/websites",
            "/api/schedules",
            "/api/system-health",
            "/api/settings",
            "/api/agents/blog-agent/report",
            "/api/agents/corporate-cars-social-agent/report"
        ]
        for ep in endpoints:
            resp = self.client.get(ep)
            self.assertEqual(resp.status_code, 200, f"Endpoint {ep} should be publicly viewable")

    def test_protected_endpoints_blocked_without_auth(self):
        # Create task blocked
        resp1 = self.client.post("/api/tasks/create", json={
            "agent_id": "blog-agent",
            "task_type": "status",
            "input_data": {}
        })
        self.assertEqual(resp1.status_code, 403)

        # Agent toggle blocked
        resp2 = self.client.post("/api/agents/toggle", json={
            "agent_id": "blog-agent",
            "action": "pause"
        })
        self.assertEqual(resp2.status_code, 403)

        # Add blog topics blocked
        resp3 = self.client.post("/api/agents/blog-agent/topics/add", json={
            "site": "ccm",
            "raw_topics": "Test Topic"
        })
        self.assertEqual(resp3.status_code, 403)

        # Add website blocked
        resp4 = self.client.post("/api/websites", json={
            "site_id": "unauth-site",
            "name": "Unauth Site",
            "domain": "https://unauth.example.com",
            "location": "Melbourne"
        })
        self.assertEqual(resp4.status_code, 403)

    def test_protected_endpoints_succeed_with_admin_auth(self):
        # Create task with admin token
        resp = self.client.post("/api/tasks/create", json={
            "agent_id": "blog-agent",
            "task_type": "status",
            "input_data": {"action": "status"},
            "requires_approval": False
        }, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("task", resp.json())


if __name__ == "__main__":
    unittest.main()
