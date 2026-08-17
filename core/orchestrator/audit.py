"""
Central Audit Log Manager.
Records all system events, agent execution steps, approvals, and AI usage metrics
with automated credential redaction and data sanitization.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from core.models.task import AuditEvent
from core.logging.logger import redact_sensitive_text

SENSITIVE_KEY_NAMES = {
    "password", "admin_password", "wp_app_password", "app_password",
    "secret", "auth_secret_key", "token", "access_token", "auth_token",
    "api_key", "apikey", "authorization", "x_admin_token", "x-admin-token",
    "client_secret", "private_key"
}


def sanitize_audit_data(val: Any) -> Any:
    """Recursively redacts secrets and sensitive keys from audit event details."""
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            k_clean = str(k).lower().strip()
            if any(s in k_clean for s in SENSITIVE_KEY_NAMES):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_audit_data(v)
        return sanitized
    elif isinstance(val, list):
        return [sanitize_audit_data(item) for item in val]
    elif isinstance(val, str):
        return redact_sensitive_text(val)
    return val


class AuditTrail:
    def __init__(self):
        self._events: List[AuditEvent] = []

    def record(self, agent_id: str, action: str, details: Optional[Dict[str, Any]] = None, user_id: Optional[str] = "system") -> AuditEvent:
        clean_details = sanitize_audit_data(details or {})
        clean_user = redact_sensitive_text(user_id or "system")

        event = AuditEvent(
            event_id=f"aud-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=agent_id,
            action=action,
            details=clean_details,
            user_id=clean_user
        )
        self._events.append(event)
        return event

    def get_history(self, agent_id: Optional[str] = None, limit: int = 100) -> List[AuditEvent]:
        events = self._events
        if agent_id:
            events = [e for e in events if e.agent_id == agent_id]
        return sorted(events, key=lambda x: x.timestamp, reverse=True)[:limit]
