"""
Agent #17: External Link Building Agent (`external-link-building-agent`).

Keeps a register of the places this business has been submitted to, and checks
whether each one actually links back. It builds no links: submitting to a
directory means an account, a form and usually a CAPTCHA, none of which this
system can do.

The version this replaces claimed otherwise, and did so on a daily schedule.

Every run of `daily_batch` appended seven rows to a local JSON file, each with
a publication date of today, an anchor, a destination and a "content snippet",
and answered "Daily batch complete: 7 high-quality backlinks staged across
Australian directories & Web 2.0 platforms." Nothing was submitted anywhere.
Each run also incremented `total_active_backlinks` and `referring_domains`, so
the counters climbed by seven a day on their own. By the time this was read
they stood at 44 and 44.

Fetching the URLs behind those 44 settles it: of the first eight checked --
Yellow Pages, TrueLocal, HotFrog, LocalSearch, Word of Mouth, Yelp and two
invented Medium and LinkedIn article URLs -- not one page contains a link to
corporatecarsmelbourne.com.au. Most were directory home pages rather than a
listing at all.

The rest was the same in kind: domain authority from `50 + hash(domain) % 45`,
dofollow or nofollow decided by a row's position in a list, a fixed 78/22
ratio, a "spam score 0.4% (Safe)" and a domain authority of 34. None of it was
measured, and no backlink API is connected to measure it with.

What this agent does now is the part that is real and was missing: it fetches
each registered URL and reports whether the link is there. A link that was
never placed shows as not found, which is the only honest thing to say about
it.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from agents.base import AgentInterface
from config.settings import LOGS_DIR
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("external-link-building-agent")

HISTORY_FILE = LOGS_DIR / "external_links_history.json"
ARCHIVE_FILE = LOGS_DIR / "external_links_history.pre-verification.json"

FETCH_TIMEOUT_SECONDS = 15
VERIFY_LIMIT = 40

# Directories worth submitting to for an Australian local business. These are
# suggestions of where to go, not claims of having been there.
SUGGESTED_DIRECTORIES = [
    {"name": "Google Business Profile", "url": "https://business.google.com",
     "note": "The one that feeds Maps and the local pack. Start here."},
    {"name": "Yellow Pages Australia", "url": "https://www.yellowpages.com.au",
     "note": "Free listing; paid tiers exist."},
    {"name": "True Local", "url": "https://www.truelocal.com.au", "note": "Free listing."},
    {"name": "Hotfrog Australia", "url": "https://www.hotfrog.com.au", "note": "Free listing."},
    {"name": "Localsearch", "url": "https://www.localsearch.com.au", "note": "Free listing."},
    {"name": "Word of Mouth", "url": "https://www.wordofmouth.com.au",
     "note": "Review-led; useful alongside Google reviews."},
    {"name": "Yelp Australia", "url": "https://www.yelp.com.au", "note": "Free listing."},
    {"name": "Bing Places", "url": "https://www.bingplaces.com", "note": "Often skipped; cheap to do."},
    {"name": "Apple Business Connect", "url": "https://businessconnect.apple.com",
     "note": "Feeds Apple Maps, which chauffeur passengers use."},
]


def load_register() -> Dict[str, Any]:
    """The submission register, migrating the old fabricated file once.

    The previous version's file is not repaired in place: every row in it was
    generated rather than submitted, so keeping the rows would carry the claim
    forward. It is archived, and the caller is told.
    """
    if not HISTORY_FILE.exists():
        return {"submissions": [], "archived_previous": False}

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read the link register: {e}")
        return {"submissions": [], "archived_previous": False}

    # The old shape. Nothing in it was ever submitted anywhere.
    if "web2_published_articles" in data or "directory_citations" in data:
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            count = len(data.get("web2_published_articles", [])) + len(data.get("directory_citations", []))
            logger.warning(
                "Archived %d generated backlink rows from the previous version to %s; "
                "none of them were ever submitted.", count, ARCHIVE_FILE.name
            )
        except Exception as e:
            logger.warning(f"Could not archive the previous register: {e}")
            count = 0
        fresh = {"submissions": [], "archived_previous": True, "archived_rows": count}
        save_register(fresh)
        return fresh

    data.setdefault("submissions", [])
    data.setdefault("archived_previous", False)
    return data


def save_register(data: Dict[str, Any]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Could not save the link register: {e}")


def verify_backlink(page_url: str, target_domain: str) -> Dict[str, Any]:
    """Fetch a page and report whether it links to the target domain.

    This is the measurement the old agent never made. `found` is true only when
    the domain appears inside an href on the page, so a mention in body text is
    not counted as a link.
    """
    import requests

    host = urlparse(target_domain if "://" in target_domain else f"https://{target_domain}").netloc
    host = host.replace("www.", "").lower()

    result: Dict[str, Any] = {
        "url": page_url,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "found": False,
        "status_code": None,
        "rel": None,
        "anchor_text": None,
        "error": None,
    }

    try:
        res = requests.get(
            page_url if "://" in page_url else f"https://{page_url}",
            timeout=FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Marketing-Dashboard linkcheck)"},
        )
    except Exception as e:
        result["error"] = f"Could not fetch the page: {e}"
        return result

    result["status_code"] = res.status_code
    if res.status_code != 200:
        result["error"] = f"The page answered HTTP {res.status_code}."
        return result

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(res.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            if host in anchor["href"].lower():
                rel = anchor.get("rel") or []
                result["found"] = True
                # rel="nofollow" is the only thing that decides follow status.
                # The old agent decided it from a row's index in a list.
                result["rel"] = " ".join(rel) if rel else "follow"
                result["anchor_text"] = (anchor.get_text() or "").strip()[:80] or None
                break
    except Exception as e:
        result["error"] = f"The page could not be parsed: {e}"
    return result


def submissions_for_site(submissions: List[Dict[str, Any]], site_id: str,
                         site_domain: str) -> List[Dict[str, Any]]:
    """Only the pages registered for this website.

    The register began as one flat list for a single site, so older rows carry
    no site_id. Those are matched on the landing page they point at, which is
    the site they were registered for; a row that matches neither belongs to
    somebody else and is left out. Without this, a new client saw CCM's
    directory submissions listed as its own backlinks.
    """
    host = urlparse(site_domain).netloc.replace("www.", "").lower()
    mine = []
    for entry in submissions:
        stamped = (entry.get("site_id") or "").strip().lower()
        if stamped:
            if stamped == site_id:
                mine.append(entry)
            continue
        target = (entry.get("target_url") or "").lower()
        if host and host in target:
            mine.append(entry)
    return mine


def summarise(submissions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Counts over what was actually checked, with nothing inferred."""
    checked = [s for s in submissions if s.get("last_check")]
    found = [s for s in checked if s["last_check"].get("found")]
    follow = [s for s in found if (s["last_check"].get("rel") or "") == "follow"]
    unreachable = [s for s in checked if s["last_check"].get("error")]

    return {
        "registered": len(submissions),
        "checked": len(checked),
        "links_found": len(found),
        "links_not_found": len(checked) - len(found) - len(unreachable),
        "pages_unreachable": len(unreachable),
        "dofollow": len(follow),
        "nofollow": len(found) - len(follow),
        # Deliberately absent: domain authority, spam score and a dofollow
        # ratio. No backlink API is connected, and the figures that stood here
        # (DA 34, spam 0.4%, 78/22) were written into the source.
        "domain_authority": None,
        "spam_score": None,
        "note": (
            "Counts cover the pages in this register that were fetched. There is no "
            "backlink API connected, so this is not your whole backlink profile — it is "
            "what these specific submissions did or did not produce."
        ),
    }


def build_recommendations(submissions: List[Dict[str, Any]], summary: Dict[str, Any],
                          archived: int) -> List[str]:
    out: List[str] = []

    if archived:
        out.append(
            f"{archived} backlinks recorded by the previous version were archived, not "
            f"counted. They were generated by the agent itself and never submitted "
            f"anywhere; spot-checking eight of them found no link on any page."
        )

    if not submissions:
        out.append(
            "The register is empty. Submit the business to a directory by hand, then add "
            "the listing URL here so this agent can check the link actually appeared."
        )
        out.append(
            "Start with Google Business Profile — it feeds Maps and the local pack, and "
            "is worth more than the rest of this list combined."
        )
        return out

    missing = [s for s in submissions
               if s.get("last_check") and not s["last_check"].get("found")
               and not s["last_check"].get("error")]
    if missing:
        out.append(
            f"{len(missing)} registered page(s) load but carry no link back. Either the "
            f"listing was never approved, or the link was removed."
        )

    unreachable = [s for s in submissions if s.get("last_check", {}).get("error")]
    if unreachable:
        out.append(f"{len(unreachable)} page(s) could not be fetched; see each row for the reason.")

    nofollow = summary.get("nofollow") or 0
    if nofollow:
        out.append(
            f"{nofollow} of the links found are nofollow. They still send visitors, but "
            f"pass no ranking signal."
        )

    unchecked = summary["registered"] - summary["checked"]
    if unchecked:
        out.append(f"{unchecked} registered page(s) have never been checked. Run a verify.")
    return out


class ExternalLinkBuildingAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="external-link-building-agent",
            name="External Link Building Agent",
            description="Keeps a register of directory and outreach submissions and checks whether each one actually links back.",
            category="Off-Page SEO & Backlinks",
            enabled=True,
            paused=False,
            supported_actions=[
                "audit_backlink_profile",
                "verify_links",
                "register_submission",
                "draft_outreach",
                "daily_batch",
            ],
            version="2.0.0",
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "audit_backlink_profile")).lower().strip()
        # site_id defaulted to "ccm", and the brand and domain below fell back
        # to Corporate Cars Melbourne's, so a task naming no site -- or an
        # unknown one -- built outreach in CCM's name.
        from config.site_context import not_configured, resolve_site

        site_id = str(
            input_data.get("site_id") or input_data.get("site")
            or getattr(task, "site_id", None) or ""
        ).strip().lower()
        profile = resolve_site(site_id)
        if not profile:
            return {"output": not_configured(
                site_id, "A website",
                "Add this website in the admin panel before running link "
                "building for it."),
                "model_used": "none", "tokens_used": 0, "cost_usd": 0.0}

        brand = profile.name or site_id
        domain = (profile.domain or "").rstrip("/")
        location = getattr(profile, "location", "") or ""

        register = load_register()
        all_submissions: List[Dict[str, Any]] = register.get("submissions", [])
        submissions: List[Dict[str, Any]] = submissions_for_site(
            all_submissions, site_id, domain)
        archived = register.get("archived_rows", 0) if register.get("archived_previous") else 0

        logger.info(f"Executing ExternalLinkBuildingAgent: action={action}, site={site_id}")

        # ---- Record a submission the operator actually made ----
        if action == "register_submission":
            urls = input_data.get("urls") or input_data.get("target_websites") or []
            if isinstance(urls, str):
                urls = [u.strip() for u in re.split(r"[\n,]+", urls) if u.strip()]
            if not urls:
                return {"output": {"action": action, "error": "No URLs were given, so nothing was registered."},
                        "model_used": "none", "tokens_used": 0, "cost_usd": 0.0}

            added = []
            known = {s["url"] for s in submissions}
            for url in urls[:40]:
                url = url if "://" in url else f"https://{url}"
                if url in known:
                    continue
                entry = {
                    "url": url,
                    "platform": urlparse(url).netloc.replace("www.", ""),
                    "registered_at": datetime.now().isoformat(timespec="seconds"),
                    "site_id": site_id,
                    "target_url": input_data.get("landing_page_url") or f"{domain}/",
                    "note": input_data.get("note") or "",
                    # A page enters the register unverified. Nothing here says a
                    # link exists until one has been found on the page.
                    "last_check": None,
                }
                entry["last_check"] = verify_backlink(url, domain)
                submissions.append(entry)
                added.append(entry)

            all_submissions.extend(added)
            register["submissions"] = all_submissions
            save_register(register)
            found = [a for a in added if a["last_check"]["found"]]
            return {
                "output": {
                    "action": action,
                    "registered": len(added),
                    "links_already_found": len(found),
                    "entries": added,
                    "message": (
                        f"Registered {len(added)} page(s) and checked each one now. "
                        f"{len(found)} already carry a link back."
                    ),
                },
                "model_used": "link-verifier", "tokens_used": 0, "cost_usd": 0.0,
            }

        # ---- Draft an outreach email for a site, to send by hand ----
        if action in ("draft_outreach", "custom_site_outreach"):
            targets = input_data.get("target_websites") or input_data.get("urls") or []
            if isinstance(targets, str):
                targets = [t.strip() for t in re.split(r"[\n,]+", targets) if t.strip()]
            if not targets:
                return {"output": {"action": action, "error": "No target website was given."},
                        "model_used": "none", "tokens_used": 0, "cost_usd": 0.0}

            site = targets[0]
            host = urlparse(site if "://" in site else f"https://{site}").netloc.replace("www.", "")
            tokens_used, cost_usd, model_used = 0, 0.0, "template"
            draft = None

            try:
                response = router.route_and_execute(LLMRequest(
                    user_prompt=(
                        f"Write a short outreach email to the editor of {host}, from {brand}, "
                        f"a chauffeur company in {location} ({domain}). Propose one specific "
                        f"article idea that would genuinely suit their readers and mention that "
                        f"we would link to it. Do not invent statistics, awards, client names or "
                        f"traffic figures. Under 140 words, plain text, no subject line fluff."
                    ),
                    task_type=TaskComplexity.ROUTINE, json_output=False,
                ))
                draft = (response.content or "").strip()
                model_used = response.model_used
                tokens_used = response.tokens_in + response.tokens_out
                cost_usd = response.cost_usd
            except Exception as e:
                logger.warning(f"Outreach draft generation failed: {e}")

            return {
                "output": {
                    "action": action,
                    "target": host,
                    "draft_email": draft,
                    "draft_method": f"written by {model_used}" if draft else "no model ran",
                    # The old action reported "Successfully processed outreach &
                    # generated N contextual backlinks with live URLs" without
                    # contacting anybody.
                    "was_sent": False,
                    "send_note": (
                        "Nothing was sent and no link was created. Send this yourself, and if "
                        "they publish, register the URL here so the link can be checked."
                    ),
                },
                "model_used": model_used, "tokens_used": tokens_used, "cost_usd": cost_usd,
            }

        # ---- Verify everything in the register ----
        if action in ("verify_links", "daily_batch"):
            # daily_batch used to append seven invented rows per run. It now
            # re-checks what is registered, which is the only thing a daily job
            # here can honestly do.
            changes = []
            for entry in submissions[:VERIFY_LIMIT]:
                before = (entry.get("last_check") or {}).get("found")
                entry["last_check"] = verify_backlink(entry["url"], domain)
                after = entry["last_check"]["found"]
                if before is not None and before != after:
                    changes.append({"url": entry["url"], "was_found": before, "now_found": after})

            # The entries above are the same objects held in all_submissions,
            # so the re-checks are already recorded. Writing back the site's
            # slice instead would delete every other site's rows.
            register["submissions"] = all_submissions
            register["last_verified"] = datetime.now().isoformat(timespec="seconds")
            save_register(register)

            summary = summarise(submissions)
            return {
                "output": {
                    "action": action,
                    "checked": min(len(submissions), VERIFY_LIMIT),
                    "changes_since_last_check": changes,
                    "summary": summary,
                    "submissions": submissions,
                    "actionable_recommendations": build_recommendations(submissions, summary, archived),
                },
                "model_used": "link-verifier", "tokens_used": 0, "cost_usd": 0.0,
            }

        # ---- Default: the register as it stands ----
        summary = summarise(submissions)
        return {
            "output": {
                "action": action,
                "target_domain": domain,
                "creates_links": False,
                "creates_links_note": (
                    "This agent does not build backlinks. Submitting to a directory needs an "
                    "account, a form and usually a CAPTCHA. It records what you submitted and "
                    "checks whether the link appeared."
                ),
                "archived_previous_rows": archived,
                "backlink_health_summary": summary,
                "submissions": submissions,
                "suggested_directories": SUGGESTED_DIRECTORIES,
                "actionable_recommendations": build_recommendations(submissions, summary, archived),
            },
            "model_used": "link-verifier", "tokens_used": 0, "cost_usd": 0.0,
        }
