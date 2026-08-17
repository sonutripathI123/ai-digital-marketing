"""
Centralized Structured Logging & Per-Agent Logging with Automated Secret Redaction.
"""

import re
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from config.settings import LOGS_DIR

# --- Compiled Regex Patterns for Secret & Credential Redaction ---
REDACTION_PATTERNS = [
    # Private Keys & Service Account Certificates (PEM format)
    (re.compile(r"-----BEGIN (?:[A-Z0-9_\-]+ )*PRIVATE KEY-----[\s\S]+?-----END (?:[A-Z0-9_\-]+ )*PRIVATE KEY-----", re.DOTALL), "[REDACTED PRIVATE KEY]"),
    (re.compile(r"-----BEGIN [A-Z0-9_ -]+-----[\s\S]+?-----END [A-Z0-9_ -]+-----", re.DOTALL), "[REDACTED CERTIFICATE/KEY]"),

    # Known AI Provider API Keys
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{8,}\b"), "sk-ant-[REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"), "sk-[REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"), "AIza[REDACTED]"),

    # Authorization & Bearer / Basic Headers
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_\-\.]{8,}\b"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/=]{8,}\b"), "Basic [REDACTED]"),
    (re.compile(r"(?i)\b(Authorization|x-admin-token)\s*:\s*['\"]?[A-Za-z0-9_\-\.\+/= ]{8,}['\"]?"), r"\1: [REDACTED]"),

    # Key-Value Pair Secrets (JSON, Logs, CLI Output)
    (
        re.compile(
            r"(?i)\b(password|admin_password|wp_app_password|app_password|secret|api_key|apikey|access_token|auth_token|auth_secret_key|client_secret|refresh_token)\b\s*[:=]\s*['\"]?([^\s'\",;&]+)['\"]?"
        ),
        r"\1=[REDACTED]"
    ),

    # Database URLs with Passwords
    (
        re.compile(r"(?i)\b(postgresql|postgres|mysql|sqlite|mongodb)(?:\+[^:]+)?://([^:]+):([^@]+)@"),
        r"\1://\2:***@"
    ),
]


def redact_sensitive_text(text: Optional[str]) -> str:
    """
    Sanitizes any string, removing API keys, tokens, credentials, and private keys
    while preserving useful operational context for debugging.
    """
    if not text:
        return ""
    sanitized = str(text)
    for pattern, replacement in REDACTION_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class RedactingFormatter(logging.Formatter):
    """Logging Formatter that scrubs sensitive credentials from all log outputs."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return redact_sensitive_text(original)


def get_agent_logger(agent_id: str) -> logging.Logger:
    """Returns a dedicated logger for a specific agent, writing to logs/agents/<agent_id>.log with secret redaction."""
    logger_name = f"agent.{agent_id}"
    logger = logging.getLogger(logger_name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = RedactingFormatter("%(asctime)s [%(levelname)s] [agent:%(name)s] %(message)s")

        agent_log_file = LOGS_DIR / "agents" / f"{agent_id}.log"
        handler = RotatingFileHandler(agent_log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(fmt)
        logger.addHandler(handler)

        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(console)

    return logger


def get_central_logger() -> logging.Logger:
    """Returns the central Command Center logger, writing to logs/command_center.log with secret redaction."""
    logger = logging.getLogger("command_center")

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = RedactingFormatter("%(asctime)s [%(levelname)s] [central] %(message)s")

        central_log_file = LOGS_DIR / "command_center.log"
        handler = RotatingFileHandler(central_log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(fmt)
        logger.addHandler(handler)

        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(console)

    return logger
