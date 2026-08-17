"""
Comprehensive Automated Security Hardening & Regression Test Suite.
Tests secret redaction, audit trail sanitization, RBAC access control,
ads live execution safety guards, error isolation, and frontend protection.
"""

import unittest
from fastapi.testclient import TestClient

from config.settings import ADMIN_EMAIL, ADMIN_PASSWORD, ADS_LIVE_EXECUTION_ENABLED
from core.logging.logger import redact_sensitive_text, get_agent_logger, get_central_logger
from core.orchestrator.audit import AuditTrail
from core.orchestrator.master import MasterOrchestrator
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask, TaskStatus
from agents.google_ads_monitoring_agent import GoogleAdsMonitoringAgent
from agents.meta_ads_monitoring_agent import MetaAdsMonitoringAgent
from dashboard.api import app, generate_admin_token


class TestSecurityHardening(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.router = ModelRouter(use_mock=True)
        self.orchestrator = MasterOrchestrator(router=self.router)
        self.token = generate_admin_token(ADMIN_EMAIL)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    # 1. Secret & Credential Redaction Tests
    def test_redact_sensitive_text_api_keys(self):
        sample = "Error using key sk-ant-api03-1234567890abcdef1234 and openai sk-proj-12345678901234567890"
        redacted = redact_sensitive_text(sample)
        self.assertNotIn("sk-ant-api03-1234567890abcdef1234", redacted)
        self.assertNotIn("sk-proj-12345678901234567890", redacted)
        self.assertIn("sk-ant-[REDACTED]", redacted)
        self.assertIn("sk-[REDACTED]", redacted)

    def test_redact_sensitive_text_bearer_and_passwords(self):
        sample = "Authorization: Bearer abc123def456ghi789 and password='SuperSecretPassword123'"
        redacted = redact_sensitive_text(sample)
        self.assertNotIn("abc123def456ghi789", redacted)
        self.assertNotIn("SuperSecretPassword123", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_redact_sensitive_text_google_keys_and_pem(self):
        sample = "Gemini key AIzaSyABC1234567890123456789 and -----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgk\n-----END PRIVATE KEY-----"
        redacted = redact_sensitive_text(sample)
        self.assertNotIn("AIzaSyABC1234567890123456789", redacted)
        self.assertNotIn("MIIEvgIBADANBgk", redacted)
        self.assertIn("AIza[REDACTED]", redacted)
        self.assertIn("[REDACTED PRIVATE KEY]", redacted)

    # 2. Audit Trail Sanitization Tests
    def test_audit_trail_sanitizes_credentials(self):
        audit = AuditTrail()
        event = audit.record(
            agent_id="test-agent",
            action="TEST_ACTION",
            details={
                "api_key": "sk-ant-testsecretkey12345",
                "admin_password": "MySuperSecretPassword",
                "normal_field": "Valid Diagnostic Data",
                "nested": {
                    "token": "bearer-token-12345",
                    "safe_value": 42
                }
            },
            user_id="user-Bearer abcdef1234567890"
        )
        self.assertEqual(event.details["api_key"], "[REDACTED]")
        self.assertEqual(event.details["admin_password"], "[REDACTED]")
        self.assertEqual(event.details["normal_field"], "Valid Diagnostic Data")
        self.assertEqual(event.details["nested"]["token"], "[REDACTED]")
        self.assertEqual(event.details["nested"]["safe_value"], 42)
        self.assertNotIn("abcdef1234567890", event.user_id)

    # 3. Ads Safety Guards (Simulation Mode Enforced)
    def test_google_ads_mutation_blocked_by_guard(self):
        agent = GoogleAdsMonitoringAgent()
        task = AgentTask(
            task_id="sec-gads-1",
            agent_id="google-ads-monitoring-agent",
            task_type="create_campaign",
            input_data={"action": "create_campaign", "budget": 1000}
        )
        res = agent.run_task(task, self.router)
        self.assertEqual(res["output"]["status"], "BLOCKED_BY_SAFETY_GUARD")
        self.assertIn("Simulation Only", res["output"]["mode"])

    def test_meta_ads_mutation_blocked_by_guard(self):
        agent = MetaAdsMonitoringAgent()
        task = AgentTask(
            task_id="sec-mads-1",
            agent_id="meta-ads-monitoring-agent",
            task_type="create_meta_campaign",
            input_data={"action": "create_meta_campaign", "budget": 500}
        )
        res = agent.run_task(task, self.router)
        self.assertEqual(res["output"]["status"], "BLOCKED_BY_SAFETY_GUARD")
        self.assertIn("Simulation Only", res["output"]["mode"])

    # 4. RBAC Authorization & Protected Actions
    def test_unauthorized_user_blocked_from_mutating_actions(self):
        # Create task without auth -> 403 Forbidden
        resp1 = self.client.post("/api/tasks/create", json={
            "agent_id": "seo-keyword-agent",
            "task_type": "research",
            "input_data": {}
        })
        self.assertEqual(resp1.status_code, 403)

        # Save AI API key without auth -> 403 Forbidden
        resp2 = self.client.post("/api/ai/providers/save-key", json={
            "provider": "anthropic",
            "api_key": "sk-ant-test"
        })
        self.assertEqual(resp2.status_code, 403)

    def test_authorized_admin_can_access_protected_actions(self):
        resp = self.client.post("/api/tasks/create", json={
            "agent_id": "seo-keyword-agent",
            "task_type": "research",
            "input_data": {"seed_keyword": "chauffeur cars", "location": "Melbourne"},
            "requires_approval": False
        }, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)

    # 5. Frontend Secret Exposure Verification
    def test_settings_and_providers_do_not_leak_raw_secrets(self):
        resp_settings = self.client.get("/api/settings")
        self.assertEqual(resp_settings.status_code, 200)
        settings_text = str(resp_settings.json())
        self.assertNotIn(ADMIN_PASSWORD, settings_text)

        resp_session = self.client.get("/api/auth/session")
        self.assertEqual(resp_session.status_code, 200)
        session_text = str(resp_session.json())
        self.assertNotIn(ADMIN_PASSWORD, session_text)

    # 6. Error Isolation & Master Orchestrator Redaction
    def test_error_isolation_and_redaction_in_orchestrator(self):
        class FailingAgent:
            @property
            def metadata(self):
                from core.orchestrator.registry import AgentMetadata
                return AgentMetadata(
                    agent_id="failing-agent",
                    name="Failing Agent",
                    description="Simulates error",
                    category="Testing",
                    enabled=True,
                    supported_actions=["fail"]
                )

            def run_task(self, task, router):
                raise RuntimeError("Failed with key sk-ant-secret1234567890!")

        failing_agent = FailingAgent()
        self.orchestrator.register_agent(failing_agent)

        task = self.orchestrator.create_task(
            agent_id="failing-agent",
            task_type="fail",
            input_data={"action": "fail"},
            requires_approval=False
        )
        completed_task = self.orchestrator.execute_task(task.task_id)
        self.assertEqual(completed_task.status, TaskStatus.FAILED)
        self.assertNotIn("sk-ant-secret1234567890", completed_task.error_message)
        self.assertIn("sk-ant-[REDACTED]", completed_task.error_message)


if __name__ == "__main__":
    unittest.main()
