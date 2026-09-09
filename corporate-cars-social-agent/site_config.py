"""
Per-site social configuration resolver (multi-tenant).

Every website managed by the dashboard's website switcher gets fully isolated
social settings: its own platform credentials, its own posting cadence and its
own rate limits. Nothing here is hardcoded per brand — adding a new website
needs no code change at all.

Resolution order for any setting, most specific first:

  1. data/site_social_credentials.json — written by the dashboard "Connect"
     flow from WebsiteProfile.agent_credentials, keyed by site_id.
  2. Environment variable prefixed with the site id, e.g. OPAL_META_PAGE_ID.
  3. Bare environment variable (META_PAGE_ID) — only for the primary site,
     so the original single-brand .env keeps working unchanged.

So a brand-new site "sydney" starts publishing the moment either
SYDNEY_META_PAGE_ID / SYDNEY_META_ACCESS_TOKEN land in the environment, or its
credentials are saved through the dashboard.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

# Load the same .env chain as config.py, so this module resolves credentials
# correctly no matter which module imports it first.
try:
    from dotenv import load_dotenv

    for _env_file in ("/etc/secrets/.env", BASE_DIR / ".env", ROOT_DIR / ".env"):
        load_dotenv(_env_file)
except ImportError:
    pass

# The site whose credentials live under un-prefixed env var names.
PRIMARY_SITE_ID = os.getenv("PRIMARY_SOCIAL_SITE_ID", "ccm").strip().lower()

# Defaults applied to every site unless it overrides them.
DEFAULT_POSTS_PER_DAY_PER_PLATFORM = int(os.getenv("POSTS_PER_DAY_PER_PLATFORM", "1"))
DEFAULT_POSTS_PER_WEEK_PER_PLATFORM = int(os.getenv("POSTS_PER_WEEK_PER_PLATFORM", "2"))

# How late a campaign may still be published, in hours. A post that missed its
# window by more than this is dropped instead of firing at a useless hour.
# This is also what stops a redeploy (which restores the campaign file from git
# and can reset statuses) from re-publishing weeks-old campaigns.
DEFAULT_MAX_LATENESS_HOURS = int(os.getenv("SOCIAL_MAX_LATENESS_HOURS", "12"))

def _data_dir_candidates(filename: str) -> tuple:
    """Where to look for a shared data file, most authoritative first.

    DATA_DIR is set by the parent process (and inherited by this subprocess)
    when runtime state lives on a mounted disk rather than inside the repo.
    """
    candidates = []
    env_dir = (os.getenv("DATA_DIR") or "").strip()
    if env_dir:
        candidates.append(Path(env_dir).expanduser() / filename)
    candidates.append(ROOT_DIR / "data" / filename)
    candidates.append(BASE_DIR / "data" / filename)
    return tuple(candidates)


_CRED_FILE_CANDIDATES = _data_dir_candidates("site_social_credentials.json")


def state_dir() -> Path | None:
    """Writable directory for runtime state (the daily quota lock file).

    Returns the STATE_DIR mount when the parent process configured one, else
    None so callers keep using their existing repo-relative paths.
    """
    raw = (os.getenv("STATE_DIR") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return path

# Credential key -> the env var suffix it maps to.
_ENV_SUFFIX = {
    "meta_access_token": "META_ACCESS_TOKEN",
    "facebook_page_id": "META_PAGE_ID",
    "instagram_account_id": "INSTAGRAM_BUSINESS_ACCOUNT_ID",
    "linkedin_token": "LINKEDIN_ACCESS_TOKEN",
    "linkedin_org_urn": "LINKEDIN_ORGANIZATION_URN",
}

# Aliases accepted in the stored JSON, so the dashboard's own field names work.
_JSON_ALIASES = {
    "meta_access_token": ("meta_access_token", "facebook_token", "access_token"),
    "facebook_page_id": ("facebook_page_id", "page_id"),
    "instagram_account_id": ("instagram_account_id", "instagram_business_account_id", "ig_id"),
    "linkedin_token": ("linkedin_token", "linkedin_access_token"),
    "linkedin_org_urn": ("linkedin_org_urn", "linkedin_organization_urn", "org_id", "linkedin_org_id"),
}


def normalize_site_id(site_id: Optional[str]) -> str:
    """Lowercase slug, safe to use as an env var prefix and a dict key."""
    return (site_id or PRIMARY_SITE_ID).strip().lower() or PRIMARY_SITE_ID


def _env_prefix(site_id: str) -> str:
    """'sydney-cars' -> 'SYDNEY_CARS_' so any new slug maps to valid env names."""
    return re.sub(r"[^A-Z0-9]+", "_", site_id.upper()).strip("_") + "_"


def _load_stored_credentials() -> Dict[str, Dict[str, Any]]:
    for path in _CRED_FILE_CANDIDATES:
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {normalize_site_id(k): v for k, v in data.items() if isinstance(v, dict)}
        except Exception:
            continue
    return {}


def _stored_value(stored: Dict[str, Any], key: str) -> str:
    for alias in _JSON_ALIASES.get(key, (key,)):
        value = stored.get(alias)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _resolve(site_id: str, key: str, stored: Dict[str, Any]) -> str:
    """Stored JSON -> site-prefixed env var -> bare env var (primary site only)."""
    value = _stored_value(stored, key)
    if value:
        return value

    suffix = _ENV_SUFFIX[key]
    value = (os.getenv(_env_prefix(site_id) + suffix) or "").strip()
    if value:
        return value

    if site_id == PRIMARY_SITE_ID:
        return (os.getenv(suffix) or "").strip()
    return ""


def _resolve_int(site_id: str, suffix: str, stored: Dict[str, Any], stored_key: str, default: int) -> int:
    raw = stored.get(stored_key)
    if raw in (None, ""):
        raw = os.getenv(_env_prefix(site_id) + suffix)
    if raw in (None, "") and site_id == PRIMARY_SITE_ID:
        raw = os.getenv(suffix)
    try:
        parsed = int(str(raw).strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


@dataclass
class SiteSocialConfig:
    """Everything the publisher needs to post on behalf of one website."""

    site_id: str
    meta_access_token: str = ""
    facebook_page_id: str = ""
    instagram_account_id: str = ""
    linkedin_token: str = ""
    linkedin_org_urn: str = ""
    posts_per_day_per_platform: int = DEFAULT_POSTS_PER_DAY_PER_PLATFORM
    posts_per_week_per_platform: int = DEFAULT_POSTS_PER_WEEK_PER_PLATFORM
    max_lateness_hours: int = DEFAULT_MAX_LATENESS_HOURS
    raw: Dict[str, Any] = field(default_factory=dict)

    def can_publish(self, platform: str) -> bool:
        plat = (platform or "").strip().lower()
        if plat == "facebook":
            return bool(self.meta_access_token and self.facebook_page_id)
        if plat == "instagram":
            return bool(self.meta_access_token and self.instagram_account_id)
        if plat == "linkedin":
            return bool(self.linkedin_token and self.linkedin_org_urn)
        return False

    def missing_for(self, platform: str) -> str:
        """Human-readable list of what this site still needs for a platform."""
        plat = (platform or "").strip().lower()
        prefix = "" if self.site_id == PRIMARY_SITE_ID else _env_prefix(self.site_id)
        required = {
            "facebook": ("meta_access_token", "facebook_page_id"),
            "instagram": ("meta_access_token", "instagram_account_id"),
            "linkedin": ("linkedin_token", "linkedin_org_urn"),
        }.get(plat, ())
        missing = [prefix + _ENV_SUFFIX[key] for key in required if not getattr(self, key)]
        return ", ".join(missing) if missing else ""


def _as_org_urn(value: str) -> str:
    """Accept a bare org id or a full URN; always hand back a full URN."""
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("urn:li:organization:"):
        return value
    return f"urn:li:organization:{value.lstrip(':').split(':')[-1]}"


def get_site_social_config(site_id: Optional[str]) -> SiteSocialConfig:
    """Build the isolated social config for one website."""
    sid = normalize_site_id(site_id)
    stored = _load_stored_credentials().get(sid, {})

    return SiteSocialConfig(
        site_id=sid,
        meta_access_token=_resolve(sid, "meta_access_token", stored),
        facebook_page_id=_resolve(sid, "facebook_page_id", stored),
        instagram_account_id=_resolve(sid, "instagram_account_id", stored),
        linkedin_token=_resolve(sid, "linkedin_token", stored),
        linkedin_org_urn=_as_org_urn(_resolve(sid, "linkedin_org_urn", stored)),
        posts_per_day_per_platform=_resolve_int(
            sid, "POSTS_PER_DAY_PER_PLATFORM", stored,
            "posts_per_day_per_platform", DEFAULT_POSTS_PER_DAY_PER_PLATFORM,
        ),
        posts_per_week_per_platform=_resolve_int(
            sid, "POSTS_PER_WEEK_PER_PLATFORM", stored,
            "posts_per_week_per_platform", DEFAULT_POSTS_PER_WEEK_PER_PLATFORM,
        ),
        max_lateness_hours=_resolve_int(
            sid, "SOCIAL_MAX_LATENESS_HOURS", stored,
            "max_lateness_hours", DEFAULT_MAX_LATENESS_HOURS,
        ),
        raw=stored,
    )
