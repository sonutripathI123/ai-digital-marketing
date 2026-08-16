"""
Central Data Models for Task Management, Approval Workflows, and Audit Logging.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class AgentTask(BaseModel):
    task_id: str
    agent_id: str
    task_type: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    requires_approval: bool = False
    approval_comment: Optional[str] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    model_used: Optional[str] = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditEvent(BaseModel):
    event_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_id: str
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = "system"
