"""Exchanging and storing the Meta access token the social agent publishes with.

A token pasted into a terminal is the fragile part of this job, not the API
call. Windows consoles cap what can be pasted into a hidden prompt, PowerShell
reformats text when it pipes into a native command -- a 282 character token
arrived as 112 -- and the only symptom either produces is Facebook answering
"Error validating application. Invalid application ID.", which points at the
wrong thing entirely. A browser paste has none of those limits, so the token
comes in over HTTP from the dashboard and everything else happens here.

Two rules the caller depends on:

  * The short-lived token Graph API Explorer issues is exchanged for a
    long-lived one first. Storing the short-lived one means publishing stops
    working an hour later with nothing to say why.
  * The new token is checked for every permission the publisher needs before
    anything is written. A token missing instagram_content_publish or
    pages_manage_posts would silently end posting, so it is refused rather
    than saved.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("meta_token")

GRAPH = "https://graph.facebook.com/v19.0"
FETCH_TIMEOUT_SECONDS = 20

# What the publisher actually uses. Losing any of these stops it working.
REQUIRED_PERMISSIONS: Tuple[str, ...] = (
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "instagram_basic",
    "instagram_content_publish",
)

# Wanted, but their absence only costs a reading feature, not publishing.
OPTIONAL_PERMISSIONS: Tuple[str, ...] = (
    "pages_read_user_content",
    "instagram_manage_insights",
)

# Meta user tokens are far longer than this; anything shorter is a truncated
# paste, and saving it would produce a confusing error much later.
MIN_TOKEN_LENGTH = 150


def _env_path(social_agent_dir: Path) -> Path:
    return Path(social_agent_dir) / ".env"


def exchange_for_long_lived(short_token: str, app_id: str, app_secret: str
                            ) -> Tuple[Optional[str], Optional[str]]:
    """Trade a short-lived token for one that does not expire."""
    import requests

    try:
        res = requests.get(
            f"{GRAPH}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": short_token,
            },
            timeout=FETCH_TIMEOUT_SECONDS,
        )
    except Exception as e:
        return None, f"Could not reach the Meta Graph API: {e}"

    if res.status_code != 200:
        try:
            message = res.json().get("error", {}).get("message", "")
        except Exception:
            message = res.text[:200]
        return None, f"Meta refused the exchange: {message}"

    token = res.json().get("access_token")
    if not token:
        return None, "Meta returned no access_token in the exchange response."
    return token, None


def describe_token(token: str) -> Dict[str, Any]:
    """The permissions on a token and whether it expires."""
    import requests

    granted: List[str] = []
    expires_at: Optional[int] = None
    try:
        res = requests.get(f"{GRAPH}/me/permissions",
                           params={"access_token": token}, timeout=FETCH_TIMEOUT_SECONDS)
        if res.status_code == 200:
            granted = sorted(
                p["permission"] for p in res.json().get("data", [])
                if p.get("status") == "granted"
            )
    except Exception as e:
        logger.warning("Could not read token permissions: %s", e)

    try:
        res = requests.get(f"{GRAPH}/debug_token",
                           params={"input_token": token, "access_token": token},
                           timeout=FETCH_TIMEOUT_SECONDS)
        if res.status_code == 200:
            expires_at = res.json().get("data", {}).get("expires_at")
    except Exception as e:
        logger.warning("Could not debug token: %s", e)

    return {
        "granted": granted,
        "missing_required": [p for p in REQUIRED_PERMISSIONS if p not in granted],
        "missing_optional": [p for p in OPTIONAL_PERMISSIONS if p not in granted],
        "expires_at": expires_at,
        "never_expires": expires_at == 0,
    }


def install_meta_token(short_token: str, social_agent_dir: Path,
                       env_key: str = "META_USER_TOKEN") -> Dict[str, Any]:
    """Exchange, verify and store a Meta token. Returns a report, never raises.

    The stored token is replaced only when the exchange succeeds and every
    required permission is present.
    """
    from dotenv import dotenv_values

    token = "".join((short_token or "").split())  # strip any pasted line breaks
    if len(token) < MIN_TOKEN_LENGTH:
        return {
            "ok": False,
            "received_length": len(token),
            "error": (
                f"That is {len(token)} characters. A Meta token is longer than "
                f"{MIN_TOKEN_LENGTH}, so this paste was cut short. Nothing was changed."
            ),
        }

    env_file = _env_path(social_agent_dir)
    if not env_file.exists():
        return {"ok": False, "error": f"No .env found at {env_file}."}

    config = dotenv_values(str(env_file))
    app_id, app_secret = config.get("META_APP_ID"), config.get("META_APP_SECRET")
    if not (app_id and app_secret):
        return {"ok": False, "error": "META_APP_ID or META_APP_SECRET is missing from .env."}

    long_token, error = exchange_for_long_lived(token, app_id, app_secret)
    if error:
        return {"ok": False, "received_length": len(token), "error": error}

    report = describe_token(long_token)
    if report["missing_required"]:
        return {
            "ok": False,
            "received_length": len(token),
            "granted": report["granted"],
            "missing_required": report["missing_required"],
            "error": (
                "Refusing to save: this token is missing "
                + ", ".join(report["missing_required"])
                + ". Publishing would stop working. Generate a new token with "
                  "those permissions ticked."
            ),
        }

    backup = env_file.with_suffix(f".env.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}")
    try:
        shutil.copy2(env_file, backup)
    except Exception as e:
        return {"ok": False, "error": f"Could not back up .env, so nothing was changed: {e}"}

    try:
        lines = env_file.read_text(encoding="utf-8").splitlines(keepends=True)
        replaced = False
        for index, line in enumerate(lines):
            if line.startswith(f"{env_key}="):
                lines[index] = f"{env_key}={long_token}\n"
                replaced = True
        if not replaced:
            lines.append(f"{env_key}={long_token}\n")
        env_file.write_text("".join(lines), encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Could not write .env: {e}"}

    logger.info("Stored a new %s (%d chars) for the social agent", env_key, len(long_token))
    return {
        "ok": True,
        "received_length": len(token),
        "stored_length": len(long_token),
        "granted": report["granted"],
        "missing_optional": report["missing_optional"],
        "never_expires": report["never_expires"],
        "expires_at": report["expires_at"],
        "backup": os.path.basename(str(backup)),
        "message": (
            "Token exchanged for a long-lived one and saved. "
            + ("It does not expire. " if report["never_expires"] else
               "Warning: Meta says this token still has an expiry. ")
            + (f"Still missing (optional): {', '.join(report['missing_optional'])}."
               if report["missing_optional"] else "All permissions present.")
        ),
    }
