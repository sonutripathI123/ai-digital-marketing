"""
Bridge between the dashboard's per-site credential store and the blog agent.

The blog agent runs as a separate subprocess with its own working directory and
resolves WordPress credentials purely from site-prefixed environment variables
(`CCM_WP_USER` / `CCM_WP_APP_PASSWORD`). Those live in `blog-agent/.env`, which
is gitignored and excluded from the image — so on any deployment built from the
repository the variables are absent and every scheduled `write` run dies with
"Missing CCM_WP_USER / CCM_WP_APP_PASSWORD in environment", while the dashboard
still offers a "Connect WordPress" form whose saved values nothing ever reads.

This module closes that gap the same way `social_credentials_bridge` does for
the publisher: it projects each website's saved blog credentials into
`DATA_DIR/site_blog_credentials.json`, which both the adapter (as subprocess
environment) and the standalone CLI read. DATA_DIR is the persistent state
directory, so credentials saved in the UI survive a rebuild or a git pull.

Environment variables still win when set, so an operator who already supplies
`CCM_WP_USER` the old way loses nothing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import DATA_DIR

BLOG_AGENT_ID = "blog-agent"
BRIDGE_FILE = DATA_DIR / "site_blog_credentials.json"

# Credential keys the blog agent understands. The dashboard form posts the
# first spelling; the second is accepted because earlier saves used it.
_USER_KEYS = ("wp_username", "wp_user")
_PASSWORD_KEYS = ("wp_app_password", "wp_password")
_URL_KEYS = ("wp_url",)


def _first(creds: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
    for key in keys:
        value = creds.get(key)
        if value not in (None, ""):
            text = str(value).strip()
            if text and not text.startswith("•••"):
                return text
    return None


def _site_payload(site: Any) -> Dict[str, str]:
    """Saved WordPress credentials for one site, or {} if incomplete.

    A username without an application password cannot authenticate, so a
    half-filled form is treated as not configured rather than exported and
    failed on later.
    """
    creds = (site.agent_credentials or {}).get(BLOG_AGENT_ID, {}) or {}

    user = _first(creds, _USER_KEYS)
    password = _first(creds, _PASSWORD_KEYS)
    if not user or not password:
        return {}

    payload = {
        "wp_username": user,
        # WordPress prints application passwords in spaced groups of four and
        # operators paste them that way; the REST API wants them unspaced.
        "wp_app_password": password.replace(" ", ""),
    }

    url = _first(creds, _URL_KEYS) or (site.domain or "").strip()
    if url:
        payload["wp_url"] = url.rstrip("/")

    return payload


def load_bridge() -> Dict[str, Dict[str, str]]:
    """Everything the bridge file currently holds, keyed by lowercase site id."""
    try:
        with open(BRIDGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}

    if not isinstance(data, dict):
        return {}
    return {
        str(site_id).strip().lower(): creds
        for site_id, creds in data.items()
        if isinstance(creds, dict)
    }


def env_overrides(existing_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Site-prefixed WordPress variables for every site the bridge knows.

    Variables already present in `existing_env` are left alone, so an explicitly
    configured environment always beats the saved credential store.
    """
    env = os.environ if existing_env is None else existing_env
    overrides: Dict[str, str] = {}

    for site_id, creds in load_bridge().items():
        prefix = site_id.upper()
        user_var = f"{prefix}_WP_USER"
        password_var = f"{prefix}_WP_APP_PASSWORD"

        if env.get(user_var) and env.get(password_var):
            continue

        user = creds.get("wp_username")
        password = creds.get("wp_app_password")
        if user and password:
            overrides[user_var] = str(user)
            overrides[password_var] = str(password)

    return overrides


def connection_status(site_id: str, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Whether the blog agent can actually authenticate for this site.

    Reports the same truth the CLI acts on, so the dashboard card stops showing
    "Connected" merely because the site profile has a domain.
    """
    env = os.environ if env is None else env
    prefix = site_id.strip().upper()
    user_var = f"{prefix}_WP_USER"
    password_var = f"{prefix}_WP_APP_PASSWORD"

    if env.get(user_var) and env.get(password_var):
        return {"ready": True, "source": "environment", "missing": []}

    saved = load_bridge().get(site_id.strip().lower(), {})
    if saved.get("wp_username") and saved.get("wp_app_password"):
        return {"ready": True, "source": "saved_credentials", "missing": []}

    missing: List[str] = []
    if not env.get(user_var) and not saved.get("wp_username"):
        missing.append(user_var)
    if not env.get(password_var) and not saved.get("wp_app_password"):
        missing.append(password_var)

    return {"ready": False, "source": None, "missing": missing}


def sync_blog_credentials(websites_mgr: Any) -> Optional[Path]:
    """Rewrite the bridge file from the live website registry.

    Returns the path written, or None if it could not be written (the agent then
    falls back to site-prefixed environment variables).
    """
    export: Dict[str, Dict[str, str]] = {}
    for site in websites_mgr.list_all():
        payload = _site_payload(site)
        if payload:
            export[site.site_id.strip().lower()] = payload

    try:
        BRIDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(BRIDGE_FILE, "w", encoding="utf-8") as f:
            json.dump(export, f, indent=2)
        return BRIDGE_FILE
    except OSError:
        return None
