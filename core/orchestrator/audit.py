"""
Central Audit Log Manager.
Records all system events, agent execution steps, approvals, and AI usage metrics.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from core.models.task import AuditEvent


class AuditTrail:
    def __init__(self):
        self._events: List[AuditEvent] = []

    def record(self, agent_id: str, action: str, details: Optional[Dict[str, Any]] = None, user_id: Optional[str] = "system") -> AuditEvent:
        event = AuditEvent(
            event_id=f"aud-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=agent_id,
            action=action,
            details=details or {},
            user_id=user_id
        )
        self._events.append(event)
        return event

    def get_history(self, agent_id: Optional[str] = None, limit: int = 100) -> List[AuditEvent]:
        events = self._events
        if agent_id:
            events = [e for e in events if e.agent_id == agent_id]
        return sorted(events, key=lambda x: x.timestamp, reverse=True)[:limit]
