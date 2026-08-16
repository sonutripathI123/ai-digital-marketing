"""
Rotating file + console logging. Call setup_logging() once at entry points.

NOTE: error alerting is console + log file for the MVP. To add email/Slack
alerts later, plug a handler in at the marked spot below (e.g. a handler that
POSTs records of level ERROR+ to a Slack webhook).
"""

import logging
from logging.handlers import RotatingFileHandler

from config import LOG_FILE, LOG_LEVEL

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    root.addHandler(file_handler)
    root.addHandler(console)

    # --- ALERTING HOOK ---------------------------------------------------
    # To get notified on publish failures, add a handler here filtered to
    # logging.ERROR, e.g. an SMTPHandler or a small Slack-webhook handler.
    # ----------------------------------------------------------------------

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
