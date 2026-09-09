"""
Export saved per-site agent credentials as Render environment variables.

Why this exists
---------------
Credentials saved through the dashboard's "Connect" form land in
STATE_DIR/websites_registry.json. That file is gitignored and lives on the
instance filesystem, so on a host without a persistent disk (Render's free
plan) every restart and deploy wipes it — which is why agents that were
connected show up as "not connected" again later.

Render environment variables are not files, so they survive restarts. This
script reads the registry and prints the exact env var names each agent
actually looks for, so the values can be pasted into
Render -> Environment -> Add Environment Variable once and stay put.

Usage
-----
    python scripts/export_render_env.py              # masked preview only
    python scripts/export_render_env.py --write      # also write the values to
                                                     # logs/render-env-export.txt

The output file contains live secrets in plain text. logs/ is gitignored, but
delete the file once the values are in Render.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import LOGS_DIR  # noqa: E402
from config.websites import WebsiteManager  # noqa: E402

OUTPUT_FILE = LOGS_DIR / "render-env-export.txt"

# The site whose social credentials use un-prefixed env var names.
# Must match PRIMARY_SOCIAL_SITE_ID in corporate-cars-social-agent/site_config.py.
PRIMARY_SITE_ID = "ccm"

# Agents that read credentials from the environment, and how each stored
# credential key maps to the env var name that agent actually reads.
#
# "site_scoped": the env var is prefixed with the site id, so several websites
# can each hold their own value.
# "global": the agent reads one un-prefixed name, so it supports a single
# website only — flagged in the report when more than one site has values.
SOCIAL_KEYS = {
    "meta_access_token": "META_ACCESS_TOKEN",
    "facebook_token": "META_ACCESS_TOKEN",
    "access_token": "META_ACCESS_TOKEN",
    "facebook_page_id": "META_PAGE_ID",
    "page_id": "META_PAGE_ID",
    "instagram_account_id": "INSTAGRAM_BUSINESS_ACCOUNT_ID",
    "instagram_business_account_id": "INSTAGRAM_BUSINESS_ACCOUNT_ID",
    "linkedin_token": "LINKEDIN_ACCESS_TOKEN",
    "linkedin_access_token": "LINKEDIN_ACCESS_TOKEN",
    "linkedin_org_urn": "LINKEDIN_ORGANIZATION_URN",
    "linkedin_organization_urn": "LINKEDIN_ORGANIZATION_URN",
    "posts_per_day_per_platform": "POSTS_PER_DAY_PER_PLATFORM",
    "posts_per_week_per_platform": "POSTS_PER_WEEK_PER_PLATFORM",
}

GOOGLE_ADS_KEYS = {
    "developer_token": "GOOGLE_ADS_DEVELOPER_TOKEN",
    "client_id": "GOOGLE_ADS_CLIENT_ID",
    "client_secret": "GOOGLE_ADS_CLIENT_SECRET",
    "refresh_token": "GOOGLE_ADS_REFRESH_TOKEN",
    "customer_id": "GOOGLE_ADS_CUSTOMER_ID",
    "login_customer_id": "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
}

BLOG_KEYS = {
    "wp_username": "WP_USER",
    "wp_user": "WP_USER",
    "wp_app_password": "WP_APP_PASSWORD",
    "wp_password": "WP_APP_PASSWORD",
}

AGENT_RULES = {
    "corporate-cars-social-agent": {"keys": SOCIAL_KEYS, "scope": "site_scoped"},
    "blog-agent": {"keys": BLOG_KEYS, "scope": "site_scoped"},
    "google-ads-monitoring-agent": {"keys": GOOGLE_ADS_KEYS, "scope": "global"},
    "google-ads-optimization-agent": {"keys": GOOGLE_ADS_KEYS, "scope": "global"},
}

# Agents whose code reads neither environment variables nor the per-site
# credential store, so exporting anything for them has no effect today.
NO_ENV_WIRING = {
    "ga4-reporting-agent": "reads no credentials; reports fallback data",
    "gsc-agent": "reads no credentials; reports fallback data",
    "meta-ads-monitoring-agent": "reads no credentials",
    "reputation-agent": "reads no credentials",
}

SKIP_KEYS = {"updated_at", "is_connected", "platforms"}


def env_prefix(site_id: str) -> str:
    """'sydney-cars' -> 'SYDNEY_CARS_'. Matches the agents' own derivation."""
    return re.sub(r"[^A-Z0-9]+", "_", site_id.upper()).strip("_") + "_"


SECRET_HINTS = ("token", "secret", "password", "key")

# Values that look like placeholders rather than real credentials. Pasting one
# of these into Render makes the agent fail with a confusing auth error.
PLACEHOLDER_HINTS = ("demo", "test", "placeholder", "changeme", "your_", "xxxx", "sample", "dummy")


def is_secret(env_name: str) -> bool:
    return any(hint in env_name.lower() for hint in SECRET_HINTS)


def looks_like_placeholder(value: str) -> bool:
    return any(hint in str(value).lower() for hint in PLACEHOLDER_HINTS)


def mask(env_name: str, value: str) -> str:
    """Mask secrets; show non-secret settings (ids, cadence) in full."""
    text = str(value)
    if not is_secret(env_name):
        return text
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:3]}{'*' * 8}{text[-3:]}"


def collect(manager: WebsiteManager) -> tuple[list, list, list]:
    """Returns (exports, collisions, notes).

    exports: (env_name, value, site_id, agent_id, stored_key)
    """
    exports: list = []
    seen: dict = {}
    collisions: list = []
    notes: list = []

    for site in manager.list_all():
        credentials = site.agent_credentials or {}
        for agent_id, stored in credentials.items():
            if agent_id in NO_ENV_WIRING:
                if any(k not in SKIP_KEYS for k in stored):
                    notes.append(
                        f"{site.site_id}/{agent_id}: has saved values but the agent "
                        f"{NO_ENV_WIRING[agent_id]} — nothing to export yet."
                    )
                continue

            rule = AGENT_RULES.get(agent_id)
            if not rule:
                notes.append(f"{site.site_id}/{agent_id}: no known env mapping, skipped.")
                continue

            for stored_key, value in (stored or {}).items():
                if stored_key in SKIP_KEYS or value in (None, ""):
                    continue
                suffix = rule["keys"].get(stored_key)
                if not suffix:
                    continue

                if rule["scope"] == "global":
                    env_name = suffix
                elif site.site_id == PRIMARY_SITE_ID and agent_id == "corporate-cars-social-agent":
                    # The primary site's social credentials use bare names so
                    # the original single-brand .env keeps working.
                    env_name = suffix
                else:
                    env_name = env_prefix(site.site_id) + suffix

                previous = seen.get(env_name)
                if previous:
                    if str(previous[1]) != str(value):
                        collisions.append((env_name, previous[2], site.site_id))
                    # Same value from another agent (the two Google Ads agents
                    # share one credential set): already covered, list once.
                    continue
                seen[env_name] = (env_name, value, site.site_id)
                exports.append((env_name, str(value), site.site_id, agent_id, stored_key))

    exports.sort(key=lambda row: row[0])
    return exports, collisions, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help=f"write real values to {OUTPUT_FILE} (contains secrets; delete after use)",
    )
    args = parser.parse_args()

    manager = WebsiteManager()
    exports, collisions, notes = collect(manager)

    print(f"Registry: {manager.storage_file}")
    print(f"Websites: {', '.join(s.site_id for s in manager.list_all()) or '(none)'}")
    print()

    if not exports:
        print("No exportable credentials found in the registry.")
    else:
        print(f"{len(exports)} environment variable(s) to add in Render:")
        print()
        width = max(len(row[0]) for row in exports)
        for env_name, value, site_id, agent_id, stored_key in exports:
            flag = "   <-- looks like a placeholder" if looks_like_placeholder(value) else ""
            print(f"  {env_name:<{width}}  = {mask(env_name, value):<20}  ({site_id}){flag}")

    if collisions:
        print()
        print("COLLISIONS — this agent reads one un-prefixed env var, so only a")
        print("single website's value can be live at a time:")
        for env_name, first_site, other_site in collisions:
            print(f"  {env_name}: kept '{first_site}', skipped '{other_site}'")

    if notes:
        print()
        print("Notes:")
        for note in notes:
            print(f"  - {note}")

    if args.write and exports:
        lines = [
            "# Render environment variables exported from the website registry.",
            "# Add these under Render -> your service -> Environment.",
            "# CONTAINS SECRETS IN PLAIN TEXT — delete this file once they are set.",
            "",
        ]
        current_site = None
        # Group by website for the file, so each block can be pasted per site.
        for env_name, value, site_id, agent_id, _key in sorted(
            exports, key=lambda row: (row[2], row[0])
        ):
            if site_id != current_site:
                if current_site is not None:
                    lines.append("")
                lines.append(f"# --- {site_id} ---")
                current_site = site_id
            lines.append(f"{env_name}={value}")
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print()
        print(f"Wrote real values to: {OUTPUT_FILE}")
        print("Delete that file once the values are in Render.")
    elif exports:
        print()
        print("Values are masked above. Re-run with --write to get the real values.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
