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

# Load .env if present in workspace root or sub-agents
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / "blog-agent" / ".env")
load_dotenv(ROOT_DIR / "corporate-cars-social-agent" / ".env")

# --- Security Flags ---
ADS_LIVE_EXECUTION_ENABLED: bool = os.getenv("ADS_LIVE_EXECUTION_ENABLED", "false").lower() in ("true", "1", "yes")
ALLOW_LIVE_PUBLISHING: bool = os.getenv("ALLOW_LIVE_PUBLISHING", "false").lower() in ("true", "1", "yes")

# --- Default AI Provider & Model Settings ---
DEFAULT_PROVIDER: str = os.getenv("DEFAULT_AI_PROVIDER", "anthropic")

# Models for task complexity routing
MODEL_CONFIG: Dict[str, Dict[str, Any]] = {
    "ROUTINE": {
        "provider": os.getenv("MODEL_ROUTINE_PROVIDER", "anthropic"),
        "primary_model": os.getenv("MODEL_ROUTINE_PRIMARY", "claude-3-5-haiku-20241022"),
        "fallback_model": os.getenv("MODEL_ROUTINE_FALLBACK", "claude-3-5-sonnet-20241022"),
    },
    "STANDARD": {
        "provider": os.getenv("MODEL_STANDARD_PROVIDER", "anthropic"),
        "primary_model": os.getenv("MODEL_STANDARD_PRIMARY", "claude-3-5-sonnet-20241022"),
        "fallback_model": os.getenv("MODEL_STANDARD_FALLBACK", "claude-3-7-sonnet-20250219"),
    },
    "COMPLEX": {
        "provider": os.getenv("MODEL_COMPLEX_PROVIDER", "anthropic"),
        "primary_model": os.getenv("MODEL_COMPLEX_PRIMARY", "claude-3-7-sonnet-20250219"),
        "fallback_model": os.getenv("MODEL_COMPLEX_FALLBACK", "claude-3-opus-20240229"),
    },
}

# Estimated Token Cost Table per 1,000 tokens (USD)
TOKEN_PRICING: Dict[str, Dict[str, float]] = {
    "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.0040},
    "claude-3-5-sonnet-20241022": {"input": 0.0030, "output": 0.0150},
    "claude-3-7-sonnet-20250219": {"input": 0.0030, "output": 0.0150},
    "claude-3-opus-20240229": {"input": 0.0150, "output": 0.0750},
    "gemini-2.5-flash": {"input": 0.00015, "output": 0.0006},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.0050},
    "gemini-2.0-flash-thinking": {"input": 0.00015, "output": 0.0006},
    "mock-model": {"input": 0.0, "output": 0.0},
}

# --- Database & Log Paths ---
DATABASE_URL: str = os.getenv("COMMAND_CENTER_DB", f"sqlite:///{(ROOT_DIR / 'logs' / 'command_center.db').as_posix()}")
LOGS_DIR: Path = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
(LOGS_DIR / "agents").mkdir(parents=True, exist_ok=True)
