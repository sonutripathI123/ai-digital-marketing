"""
Corporate Cars Melbourne — Social Media Agent
Central configuration. Loads .env once; everything else imports from here.
"""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
load_dotenv("/etc/secrets/.env")
load_dotenv(BASE_DIR / ".env")
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / "blog-agent" / ".env")

# --- Core app settings ---
_raw_db = os.getenv("DATABASE_URL", "")
if not _raw_db or _raw_db == "sqlite:///social_agent.db":
    DATABASE_URL = f"sqlite:///{(BASE_DIR / 'social_agent.db').as_posix()}"
else:
    DATABASE_URL = _raw_db
IMAGE_LIBRARY_PATH = Path(os.getenv("IMAGE_LIBRARY_PATH", str(BASE_DIR / "images")))
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Australia/Melbourne"))
POSTS_PER_WEEK_PER_PLATFORM = int(os.getenv("POSTS_PER_WEEK_PER_PLATFORM", "2"))
DRY_RUN = os.getenv("DRY_RUN", "false").strip().lower() in ("1", "true", "yes")

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = Path(os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "agent.log")))

# --- Anthropic ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# --- Publishing ---
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "https://ai-digital-marketing-gm68.onrender.com/social-images").rstrip("/")

# Daemon: how often run_scheduler.py checks for due posts (minutes)
PUBLISH_CHECK_INTERVAL_MINUTES = int(os.getenv("PUBLISH_CHECK_INTERVAL_MINUTES", "5"))

# Retry policy for failed publishes
MAX_PUBLISH_ATTEMPTS = int(os.getenv("MAX_PUBLISH_ATTEMPTS", "5"))
RETRY_BASE_DELAY_SECONDS = int(os.getenv("RETRY_BASE_DELAY_SECONDS", "60"))

# --- Meta (Instagram + Facebook) ---
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_PAGE_ID = os.getenv("META_PAGE_ID", "")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

# --- LinkedIn ---
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_ORGANIZATION_URN = os.getenv("LINKEDIN_ORGANIZATION_URN", "")

# --- X (Twitter) ---
X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")

# --- Threads ---
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")

# --- Pinterest ---
PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "")
PINTEREST_BOARD_ID = os.getenv("PINTEREST_BOARD_ID", "")

WEBSITE_URL = "https://corporatecarsmelbourne.com.au"
BUSINESS_NAME = "Corporate Cars Melbourne"
