"""
Master Orchestrator for the AI Digital Marketing Command Center.

Coordinates task submission, agent execution, human approval workflows,
retry policies, centralized logging, and AI token/cost accounting.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger, get_central_logger
from core.models.task import AgentTask, TaskPriority, TaskStatus
from core.orchestrator.audit import AuditTrail
from core.orchestrator.queue import TaskQueue
from core.orchestrator.registry import AgentRegistry

central_logger = get_central_logger()


class MasterOrchestrator:
    def __init__(self, router: Optional[ModelRouter] = None):
        self.registry = AgentRegistry()
        self.queue = TaskQueue()
        self.audit = AuditTrail()
        self.router = router or ModelRouter()
        self._agent_instances: Dict[str, Any] = {}

    def register_agent(self, agent_instance: Any) -> None:
        """Register an agent implementation matching AgentInterface."""
        metadata = agent_instance.metadata
        self.registry.register(metadata)
        self._agent_instances[metadata.agent_id] = agent_instance
        central_logger.info(f"Registered agent implementation: {metadata.agent_id}")

    def create_task(
        self,
        agent_id: str,
        task_type: str,
        input_data: Dict[str, Any],
        requires_approval: bool = False,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> AgentTask:
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = AgentTask(
            task_id=task_id,
            agent_id=agent_id,
            task_type=task_type,
            input_data=input_data,
            status=TaskStatus.AWAITING_APPROVAL if requires_approval else TaskStatus.QUEUED,
            priority=priority,
            requires_approval=requires_approval,
        )
        self.queue.add(task)
        self.audit.record(agent_id, "TASK_CREATED", {"task_id": task_id, "requires_approval": requires_approval})
        central_logger.info(f"Created task {task_id} for agent {agent_id} (Status: {task.status.value})")
        return task

    def approve_task(self, task_id: str, approver: str = "human", comment: str = "") -> Optional[AgentTask]:
        task = self.queue.get(task_id)
        if task and task.status == TaskStatus.AWAITING_APPROVAL:
            task.status = TaskStatus.APPROVED
            task.approval_comment = comment
            self.audit.record(task.agent_id, "TASK_APPROVED", {"task_id": task_id, "approver": approver, "comment": comment}, user_id=approver)
            central_logger.info(f"Task {task_id} approved by {approver}")
            return task
        return None

    def reject_task(self, task_id: str, rejecter: str = "human", comment: str = "") -> Optional[AgentTask]:
        task = self.queue.get(task_id)
        if task and task.status == TaskStatus.AWAITING_APPROVAL:
            task.status = TaskStatus.REJECTED
            task.approval_comment = comment
            self.audit.record(task.agent_id, "TASK_REJECTED", {"task_id": task_id, "rejecter": rejecter, "comment": comment}, user_id=rejecter)
            central_logger.info(f"Task {task_id} rejected by {rejecter}")
            return task
        return None

    def execute_task(self, task_id: str) -> AgentTask:
        task = self.queue.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")

        agent_meta = self.registry.get(task.agent_id)
        if not agent_meta:
            task.status = TaskStatus.FAILED
            task.error_message = f"Agent {task.agent_id} not registered."
            return task

        if not agent_meta.enabled or agent_meta.paused:
            task.status = TaskStatus.FAILED
            task.error_message = f"Agent {task.agent_id} is disabled or paused."
            return task

        if task.requires_approval and task.status != TaskStatus.APPROVED:
            task.status = TaskStatus.FAILED
            task.error_message = f"Task {task_id} requires approval before execution."
            return task

        agent_logger = get_agent_logger(task.agent_id)
        agent_logger.info(f"Starting execution for task {task_id}")
        task.status = TaskStatus.RUNNING
        self.audit.record(task.agent_id, "TASK_RUNNING", {"task_id": task_id})

        agent_impl = self._agent_instances.get(task.agent_id)
        if not agent_impl:
            task.status = TaskStatus.FAILED
            task.error_message = f"No execution implementation registered for {task.agent_id}"
            return task

        try:
            result = agent_impl.run_task(task, self.router)
            task.status = TaskStatus.COMPLETED
            task.output_data = result.get("output", {})
            task.model_used = result.get("model_used")
            task.tokens_used = result.get("tokens_used", 0)
            task.cost_usd = result.get("cost_usd", 0.0)
            agent_logger.info(f"Completed task {task_id} successfully.")
            self.audit.record(task.agent_id, "TASK_COMPLETED", {
                "task_id": task_id,
                "model_used": task.model_used,
                "cost_usd": task.cost_usd,
            })
        except Exception as e:
            from core.logging.logger import redact_sensitive_text
            clean_err = redact_sensitive_text(str(e))
            task.retry_count += 1
            if task.retry_count <= task.max_retries:
                agent_logger.warning(f"Task {task_id} attempt {task.retry_count} failed: {clean_err}. Retrying.")
                self.audit.record(task.agent_id, "TASK_RETRY", {"task_id": task_id, "error": clean_err})
                return self.execute_task(task_id)
            else:
                task.status = TaskStatus.FAILED
                task.error_message = clean_err
                agent_logger.error(f"Task {task_id} permanently failed: {clean_err}")
                self.audit.record(task.agent_id, "TASK_FAILED", {"task_id": task_id, "error": clean_err})

        return task
