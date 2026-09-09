"""
Central Configuration for AI Digital Marketing Command Center.

Handles environment loading, model configuration, pricing tables,
security flags, and system paths.
"""

import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Root directory of the workspace
ROOT_DIR = Path(__file__).resolve().parent.parent

# Load .env if present in workspace root, sub-agents, or Render /etc/secrets
load_dotenv("/etc/secrets/.env")
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / "blog-agent" / ".env")
load_dotenv(ROOT_DIR / "corporate-cars-social-agent" / ".env")

# --- Security & Access Control ---
ADS_LIVE_EXECUTION_ENABLED: bool = os.getenv("ADS_LIVE_EXECUTION_ENABLED", "false").lower() in ("true", "1", "yes")
ALLOW_LIVE_PUBLISHING: bool = os.getenv("ALLOW_LIVE_PUBLISHING", "false").lower() in ("true", "1", "yes")
ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "sonutripathi9305@gmail.com").strip().lower()
ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "26032024")
AUTH_SECRET_KEY: str = os.getenv("AUTH_SECRET_KEY", "ai-marketing-auth-master-secret-9305")


# --- Default AI Provider & Model Settings ---
DEFAULT_PROVIDER: str = os.getenv("DEFAULT_AI_PROVIDER", "anthropic")

# Models for task complexity routing
MODEL_CONFIG: Dict[str, Dict[str, Any]] = {
    "ROUTINE": {
        "provider": os.getenv("MODEL_ROUTINE_PROVIDER", "anthropic"),
        "primary_model": os.getenv("MODEL_ROUTINE_PRIMARY", "claude-sonnet-4-6"),
        "fallback_model": os.getenv("MODEL_ROUTINE_FALLBACK", "claude-sonnet-4-6"),
    },
    "STANDARD": {
        "provider": os.getenv("MODEL_STANDARD_PROVIDER", "anthropic"),
        "primary_model": os.getenv("MODEL_STANDARD_PRIMARY", "claude-sonnet-4-6"),
        "fallback_model": os.getenv("MODEL_STANDARD_FALLBACK", "claude-sonnet-4-6"),
    },
    "COMPLEX": {
        "provider": os.getenv("MODEL_COMPLEX_PROVIDER", "anthropic"),
        "primary_model": os.getenv("MODEL_COMPLEX_PRIMARY", "claude-sonnet-4-6"),
        "fallback_model": os.getenv("MODEL_COMPLEX_FALLBACK", "claude-sonnet-4-6"),
    },
}

# Estimated Token Cost Table per 1,000 tokens (USD)
TOKEN_PRICING: Dict[str, Dict[str, float]] = {
    # Anthropic
    "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.0040},
    "claude-3-5-sonnet-20241022": {"input": 0.0030, "output": 0.0150},
    "claude-3-7-sonnet-20250219": {"input": 0.0030, "output": 0.0150},
    "claude-3-opus-20240229": {"input": 0.0150, "output": 0.0750},
    # Google Gemini
    "gemini-2.5-flash": {"input": 0.00015, "output": 0.0006},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.0050},
    "gemini-2.0-flash-thinking": {"input": 0.00015, "output": 0.0006},
    # OpenAI
    "gpt-4o": {"input": 0.0025, "output": 0.0100},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "o1": {"input": 0.0150, "output": 0.0600},
    "o3-mini": {"input": 0.0011, "output": 0.0044},
    # DeepSeek
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-reasoner": {"input": 0.00055, "output": 0.00219},
    # Groq (Llama / Mixtral)
    "llama-3.3-70b-versatile": {"input": 0.00059, "output": 0.00079},
    "llama-3.1-8b-instant": {"input": 0.00005, "output": 0.00008},
    "mixtral-8x7b-32768": {"input": 0.00024, "output": 0.00024},
    # Mistral / Custom
    "mistral-large-latest": {"input": 0.0020, "output": 0.0060},
    "mock-model": {"input": 0.0, "output": 0.0},
}

# --- Runtime state locations ---
#
# Everything the app writes at runtime lives under two directories:
#
#   STATE_DIR  website registry (saved agent credentials, invite tokens),
#              task history, agent report histories, SQLite DB, log files
#   DATA_DIR   social campaign queue, visitor telemetry, per-site social
#              credentials bridge
#
# Both default to folders inside the repo, which is fine locally. On a host
# with an ephemeral filesystem (e.g. Render without a persistent disk) that
# means every restart wipes saved credentials and history — point these at a
# mounted disk instead:
#
#   STATE_DIR=/var/data/state
#   DATA_DIR=/var/data/data
#
# Blog agent paths are deliberately not routed through here; it keeps its own
# layout under blog-agent/.
def _resolve_dir(env_var: str, default: Path) -> Path:
    raw = (os.getenv(env_var) or "").strip()
    path = Path(raw).expanduser() if raw else default
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Unwritable override (bad mount, typo): fall back to the repo folder
        # rather than crashing the whole app on boot.
        path = default
        path.mkdir(parents=True, exist_ok=True)
    return path


LOGS_DIR: Path = _resolve_dir("STATE_DIR", ROOT_DIR / "logs")
(LOGS_DIR / "agents").mkdir(parents=True, exist_ok=True)

DATA_DIR: Path = _resolve_dir("DATA_DIR", ROOT_DIR / "data")
REPO_DATA_DIR: Path = ROOT_DIR / "data"

DATABASE_URL: str = os.getenv("COMMAND_CENTER_DB", f"sqlite:///{(LOGS_DIR / 'command_center.db').as_posix()}")


def seed_data_dir() -> list:
    """Copy repo-committed data files into DATA_DIR on first boot.

    Files like the social campaign queue ship in the repo as a starting point.
    When DATA_DIR points at a freshly mounted disk it starts empty, so seed it
    once. Existing files are never overwritten — runtime state always wins,
    which is exactly what stops a redeploy from resurrecting old statuses.
    """
    if DATA_DIR.resolve() == REPO_DATA_DIR.resolve() or not REPO_DATA_DIR.exists():
        return []

    import shutil

    seeded = []
    for source in REPO_DATA_DIR.glob("*.json"):
        target = DATA_DIR / source.name
        if target.exists():
            continue
        try:
            shutil.copy2(source, target)
            seeded.append(source.name)
        except OSError:
            pass
    return seeded


SEEDED_DATA_FILES: list = seed_data_dir()
