"""Who a task is actually for.

Eight agents carried Corporate Cars Melbourne as the default site: its domain,
its GA4 property, its brand name. When a task arrived for any other site --
including a brand-new one added from the admin panel -- the default won and the
agent audited, reported on, and named CCM under the other site's heading. Adding
a second client was therefore enough to show that client another business's
traffic.

The rule here is that there is no default site. A task either names a site the
registry knows, or the agent says so and reports nothing. `not_configured` is
the shape to return in that case: it matches how the connected agents already
report a missing credential, so the panels render it without special-casing.
"""

from typing import Any, Dict, Optional

from core.logging.logger import get_agent_logger

logger = get_agent_logger("site-context")


def resolve_site(site_id: Optional[str], site_profile: Any = None) -> Optional[Any]:
    """The website profile for this task, or None if there isn't one.

    Never falls back to another site. A caller that gets None must report that
    the site is not configured rather than carrying on with someone else's.
    """
    if site_profile is not None:
        return site_profile
    if not site_id:
        return None
    try:
        from config.websites import WebsiteManager

        return WebsiteManager().get(str(site_id).strip().lower())
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Could not read the website registry for '%s': %s", site_id, e)
        return None


def site_identity(site_id: Optional[str], site_profile: Any = None) -> Dict[str, Any]:
    """Brand name and domain for this site, or empty strings and known=False."""
    profile = resolve_site(site_id, site_profile)
    if not profile:
        return {"known": False, "site_id": site_id, "name": "", "domain": "", "location": ""}
    return {
        "known": True,
        "site_id": profile.site_id,
        "name": profile.name or "",
        "domain": (profile.domain or "").rstrip("/"),
        "location": getattr(profile, "location", "") or "",
    }


def not_configured(site_id: Optional[str], what: str, how: str) -> Dict[str, Any]:
    """The answer when a site has not connected the thing an agent needs.

    Reported rather than substituted. `what` names the missing piece and `how`
    says where to add it, so the panel can show a next step instead of a blank.
    """
    label = site_id or "this website"
    return {
        "live_data_connected": False,
        "data_source": "NOT CONFIGURED",
        "site_id": site_id,
        "measured": False,
        "live_error": f"{what} is not configured for '{label}'.",
        "how_to_fix": how,
        "note": (
            f"Nothing is shown for '{label}' until {what.lower()} is connected. "
            f"Another website's data is never substituted."
        ),
    }
