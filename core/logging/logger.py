"""
Centralized Structured Logging & Per-Agent Logging.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import LOGS_DIR


def get_agent_logger(agent_id: str) -> logging.Logger:
    """Returns a dedicated logger for a specific agent, writing to logs/agents/<agent_id>.log."""
    logger_name = f"agent.{agent_id}"
    logger = logging.getLogger(logger_name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] [agent:%(name)s] %(message)s")

        agent_log_file = LOGS_DIR / "agents" / f"{agent_id}.log"
        handler = RotatingFileHandler(agent_log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(fmt)
        logger.addHandler(handler)

        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(console)

    return logger


def get_central_logger() -> logging.Logger:
    """Returns the central Command Center logger, writing to logs/command_center.log."""
    logger = logging.getLogger("command_center")

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] [central] %(message)s")

        central_log_file = LOGS_DIR / "command_center.log"
        handler = RotatingFileHandler(central_log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(fmt)
        logger.addHandler(handler)

        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(console)

    return logger
