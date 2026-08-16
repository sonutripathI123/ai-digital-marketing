"""
Unit tests for Task Lifecycle, Queue, Approval Workflow, and Audit Log.
"""

import unittest
from agents.blog_agent_adapter import BlogAgentAdapter
from core.ai_layer.router import ModelRouter
from core.models.task import TaskPriority, TaskStatus
from core.orchestrator.master import MasterOrchestrator


class TestTaskLifecycle(unittest.TestCase):
    def test_task_creation_queue_and_approval(self):
        router = ModelRouter(use_mock=True)
        orchestrator = MasterOrchestrator(router=router)
        orchestrator.register_agent(BlogAgentAdapter())

        task = orchestrator.create_task(
            agent_id="blog-agent",
            task_type="status",
            input_data={"action": "status"},
            requires_approval=True,
            priority=TaskPriority.HIGH
        )
        self.assertEqual(task.status, TaskStatus.AWAITING_APPROVAL)

        approved_task = orchestrator.approve_task(task.task_id, approver="admin", comment="Approved for test")
        self.assertIsNotNone(approved_task)
        self.assertEqual(approved_task.status, TaskStatus.APPROVED)

        executed_task = orchestrator.execute_task(task.task_id)
        self.assertEqual(executed_task.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(executed_task.output_data)

    def test_task_rejection(self):
        router = ModelRouter(use_mock=True)
        orchestrator = MasterOrchestrator(router=router)
        orchestrator.register_agent(BlogAgentAdapter())

        task = orchestrator.create_task(
            agent_id="blog-agent",
            task_type="status",
            input_data={"action": "status"},
            requires_approval=True
        )

        rejected_task = orchestrator.reject_task(task.task_id, rejecter="manager", comment="Rejecting for test")
        self.assertEqual(rejected_task.status, TaskStatus.REJECTED)

    def test_audit_trail_recording(self):
        router = ModelRouter(use_mock=True)
        orchestrator = MasterOrchestrator(router=router)
        orchestrator.register_agent(BlogAgentAdapter())

        task = orchestrator.create_task(
            agent_id="blog-agent",
            task_type="status",
            input_data={"action": "status"}
        )
        orchestrator.execute_task(task.task_id)

        history = orchestrator.audit.get_history(agent_id="blog-agent")
        self.assertGreaterEqual(len(history), 2)


if __name__ == "__main__":
    unittest.main()
