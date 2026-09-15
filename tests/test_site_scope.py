"""The per-site boundary.

check_site_access_permission sat in the codebase unused for the whole life of
the multi-tenant feature: a magic-link token issued for one website could read
every other website's leads, spend and credentials. These tests exist so that
regression is loud rather than silent.
"""
import os
import unittest

os.environ.setdefault("SCHEDULER_ENABLED", "false")

from fastapi.testclient import TestClient

from dashboard.api import (
    ADMIN_EMAIL,
    app,
    check_site_access_permission,
    generate_admin_token,
    generate_auth_token,
    site_ids_in_request,
)


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestSiteScopeHelper(unittest.TestCase):
    def test_no_session_holds_nothing(self):
        self.assertFalse(check_site_access_permission("ccm", None))

    def test_email_gate_visitor_holds_nothing(self):
        visitor = {"role": "visitor", "allowed_sites": [], "is_super_admin": False}
        self.assertFalse(check_site_access_permission("ccm", visitor))

    def test_grant_covers_only_the_granted_site(self):
        client = {"role": "client", "allowed_sites": ["opal"], "is_super_admin": False}
        self.assertTrue(check_site_access_permission("opal", client))
        self.assertFalse(check_site_access_permission("ccm", client))

    def test_portfolio_view_needs_every_site(self):
        client = {"role": "client", "allowed_sites": ["opal"], "is_super_admin": False}
        owner = {"role": "super_admin", "allowed_sites": ["*"], "is_super_admin": True}
        for alias in ("all", "*", "portfolio"):
            self.assertFalse(check_site_access_permission(alias, client), alias)
            self.assertTrue(check_site_access_permission(alias, owner), alias)


class TestSiteIdsInRequest(unittest.TestCase):
    """site_id arrives three ways; missing one would leave a way around."""

    def test_reads_the_path(self):
        found = site_ids_in_request("/api/sites/ccm/agents/integrations", None, None)
        self.assertEqual(found, {"ccm"})

    def test_reads_a_nested_body(self):
        body = {"agent_id": "blog-agent", "input_data": {"site_id": "CCM"}}
        self.assertEqual(site_ids_in_request("/api/tasks/create", None, body), {"ccm"})

    def test_ignores_requests_that_name_no_site(self):
        self.assertEqual(site_ids_in_request("/api/tasks", None, {"limit": 10}), set())


class TestSiteScopeOverHttp(unittest.TestCase):
    """The rule has to hold at the wire, not only in the helper."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client_headers = _headers(
            generate_auth_token(
                email="magic-link-client@example.com",
                role="client",
                allowed_sites=["opal"],
            )
        )
        cls.admin_headers = _headers(generate_admin_token(ADMIN_EMAIL))

    def test_client_cannot_read_another_site(self):
        for path in (
            "/api/overview?site_id=ccm",
            "/api/agents/lead-management-agent/report?site_id=ccm",
            "/api/sites/ccm/agents/integrations",
        ):
            resp = self.client.get(path, headers=self.client_headers)
            self.assertEqual(resp.status_code, 403, path)

    def test_client_cannot_queue_work_on_another_site(self):
        resp = self.client.post(
            "/api/tasks/create",
            headers=self.client_headers,
            json={
                "agent_id": "blog-agent",
                "task_type": "write",
                "site_id": "ccm",
                "input_data": {"action": "write", "site_id": "ccm"},
                "requires_approval": False,
            },
        )
        self.assertEqual(resp.status_code, 403)

    def test_client_can_use_its_own_site(self):
        resp = self.client.get("/api/overview?site_id=opal", headers=self.client_headers)
        self.assertEqual(resp.status_code, 200)

    def test_client_sees_only_its_own_site_listed(self):
        data = self.client.get("/api/websites", headers=self.client_headers).json()
        self.assertEqual([w["site_id"] for w in data["websites"]], ["opal"])

    def test_owner_still_reaches_every_site(self):
        for path in ("/api/overview?site_id=ccm", "/api/overview?site_id=opal"):
            resp = self.client.get(path, headers=self.admin_headers)
            self.assertEqual(resp.status_code, 200, path)

    def test_anonymous_caller_gets_no_site_data(self):
        resp = self.client.get("/api/overview?site_id=ccm")
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_session_is_not_told_it_owns_everything(self):
        data = self.client.get("/api/auth/session").json()
        self.assertEqual(data["allowed_sites"], [])


if __name__ == "__main__":
    unittest.main()
