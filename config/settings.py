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

# --- Database & Log Paths ---
DATABASE_URL: str = os.getenv("COMMAND_CENTER_DB", f"sqlite:///{(ROOT_DIR / 'logs' / 'command_center.db').as_posix()}")
LOGS_DIR: Path = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
(LOGS_DIR / "agents").mkdir(parents=True, exist_ok=True)
