"""
Bridge between the dashboard's per-site credential store and the social agent.

The social agent runs as a separate subprocess with its own working directory,
so it cannot import WebsiteManager. This module projects each website's saved
social credentials into `data/site_social_credentials.json`, which
`corporate-cars-social-agent/site_config.py` reads to decide which account to
post to and which quota to apply.

Called whenever a site's social credentials change, so the switcher and the
publisher never drift apart.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from config.settings import DATA_DIR, ROOT_DIR

SOCIAL_AGENT_ID = "corporate-cars-social-agent"
BRIDGE_FILE = DATA_DIR / "site_social_credentials.json"

# Credential keys the publisher understands. Anything else stays in the
# website registry and is ignored here.
_EXPORTED_KEYS = (
    "facebook_page_id",
    "facebook_token",
    "instagram_account_id",
    "linkedin_token",
    "linkedin_org_urn",
    "posts_per_day_per_platform",
    "posts_per_week_per_platform",
)


def _site_payload(site: Any) -> Dict[str, Any]:
    """Credentials for one site, falling back to its registry profile fields."""
    creds = (site.agent_credentials or {}).get(SOCIAL_AGENT_ID, {}) or {}
    payload = {key: creds[key] for key in _EXPORTED_KEYS if creds.get(key) not in (None, "")}

    # A LinkedIn company URL on the profile is not a credential, but the
    # organisation URN can be derived when the operator saved only the id.
    if "linkedin_org_urn" not in payload and creds.get("linkedin_org_id"):
        payload["linkedin_org_urn"] = creds["linkedin_org_id"]

    return payload


def social_connection_status(site_id: str) -> Dict[str, Any]:
    """What the publisher can actually do for this site, right now.

    Asks the publisher's own resolver, so the dashboard reports the same truth
    the daemon acts on — whether the credentials came from the UI or from
    site-prefixed environment variables.
    """
    import sys

    agent_dir = Path(ROOT_DIR) / SOCIAL_AGENT_ID
    if str(agent_dir) not in sys.path:
        sys.path.insert(0, str(agent_dir))

    platforms = ("facebook", "instagram", "linkedin")
    fallback = {
        "ready_platforms": [],
        "missing": {p: "credential resolver unavailable" for p in platforms},
        "posts_per_day_per_platform": 1,
        "posts_per_week_per_platform": 2,
    }
    try:
        from site_config import get_site_social_config

        cfg = get_site_social_config(site_id)
    except Exception:
        return fallback

    ready = [p for p in platforms if cfg.can_publish(p)]
    return {
        "ready_platforms": ready,
        "missing": {p: cfg.missing_for(p) for p in platforms if p not in ready},
        "posts_per_day_per_platform": cfg.posts_per_day_per_platform,
        "posts_per_week_per_platform": cfg.posts_per_week_per_platform,
    }


def sync_social_credentials(websites_mgr: Any) -> Path | None:
    """Rewrite the bridge file from the live website registry.

    Returns the path written, or None if it could not be written (the publisher
    then falls back to site-prefixed environment variables).
    """
    export: Dict[str, Dict[str, Any]] = {}
    for site in websites_mgr.list_all():
        payload = _site_payload(site)
        if payload:
            export[site.site_id.strip().lower()] = payload

    try:
        BRIDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(BRIDGE_FILE, "w", encoding="utf-8") as f:
            json.dump(export, f, indent=2)
        return BRIDGE_FILE
    except Exception:
        return None
