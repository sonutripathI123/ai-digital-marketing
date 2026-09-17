"""
Agent #5: Internal Linking Agent (`internal-linking-agent`).

Scans website pages and live blog posts to:
1. Audit existing internal & external links for SEO quality, anchor text strength, and destination relevance.
2. Contextually discover high-impact internal linking opportunities from 300+ indexed landing pages.
3. Automatically apply selected internal links directly to WordPress in 1 click via REST API.
"""

import os
import re
import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin
import requests

from config.settings import ROOT_DIR
from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("internal-linking-agent")

BLOG_AGENT_DIR = Path(ROOT_DIR) / "blog-agent"


def _registry_domain(site_key: str) -> str:
    """This site's own domain, or empty. Never another site's."""
    from config.site_context import site_identity

    return site_identity(site_key)["domain"]


def _registry_name(site_key: str) -> str:
    from config.site_context import site_identity

    return site_identity(site_key)["name"]


def get_wp_client(site_key: str = "ccm") -> tuple[str, tuple[str, str], Dict[str, Any]]:
    """Returns base API url, auth tuple, and site config for WordPress REST API."""
    env_path = BLOG_AGENT_DIR / ".env"
    env_vars = {}
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()

    prefix = site_key.upper()
    user = env_vars.get(f"{prefix}_WP_USER") or os.environ.get(f"{prefix}_WP_USER", "")
    pw = env_vars.get(f"{prefix}_WP_APP_PASSWORD") or os.environ.get(f"{prefix}_WP_APP_PASSWORD", "")

    # Default URLs
    site_urls = {
        "ccm": "https://corporatecarsmelbourne.com.au",
        "opal": "https://www.opalchauffeurs.com.au"
    }
    # Unknown sites used to land on Corporate Cars Melbourne's WordPress,

    # so an internal-linking run for another client read CCM's posts.

    base_url = site_urls.get(site_key) or _registry_domain(site_key)
    api_url = base_url.rstrip("/") + "/wp-json/wp/v2"

    return api_url, (user, pw), {"name": _registry_name(site_key) or site_key, "base_url": base_url}


def load_candidate_internal_pages(site_key: str = "ccm") -> List[Dict[str, str]]:
    """Loads indexed target pages from local catalogs."""
    candidates: List[Dict[str, str]] = []
    seen_urls = set()

    # The seven "service pillar" URLs that used to be hardcoded here do not
    # exist on the site: /services/wedding-car-hire/, /services/winery-tours/,
    # /fleet/executive-sedans/ and /fleet/people-mover/ all answer 404, and the
    # rest only redirect. Suggesting them produced internal links to dead pages.
    # The CSVs below are exported from the live site, so they describe pages
    # that are actually there.

    # 1. Suburb Pages
    suburb_file = BLOG_AGENT_DIR / f"suburb_pages_{site_key}.csv"
    if suburb_file.exists():
        try:
            with open(suburb_file, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    url = (r.get("url") or "").strip()
                    kw = (r.get("keyword") or r.get("suburb") or "").strip()
                    if url and url.rstrip("/") not in seen_urls:
                        candidates.append({
                            "url": url,
                            "keyword": kw,
                            "category": "Suburb Landing Page"
                        })
                        seen_urls.add(url.rstrip("/"))
        except Exception as e:
            logger.warning(f"Could not load suburb pages CSV: {e}")

    # 3. All Pages CSV
    all_pages_file = BLOG_AGENT_DIR / f"all_pages_{site_key}.csv"
    if all_pages_file.exists():
        try:
            with open(all_pages_file, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    url = (r.get("url") or "").strip()
                    kw = (r.get("page_keyword") or r.get("suburb_guess") or "").strip()
                    if url and kw and url.rstrip("/") not in seen_urls:
                        candidates.append({
                            "url": url,
                            "keyword": kw,
                            "category": r.get("category") or "Indexed Page"
                        })
                        seen_urls.add(url.rstrip("/"))
        except Exception as e:
            logger.warning(f"Could not load all pages CSV: {e}")

    return candidates


LINK_CHECK_TIMEOUT_SECONDS = 10
LINK_CHECK_LIMIT = 40
LINK_CHECK_USER_AGENT = "AI-Digital-Marketing-OS/1.0 (internal link audit)"


def check_link_targets(hrefs: List[str], base_url: str) -> Dict[str, Dict[str, Any]]:
    """Resolve each link and report whether it actually loads.

    The audit graded anchor wording and never asked whether the target existed,
    so a link to a page returning 404 was reported as "Optimal". Results are
    keyed by the href exactly as it appeared in the markup.

    HEAD first because it is cheap; some servers reject it, so those fall back
    to GET. Anything that is neither an http(s) page — mailto:, tel:, #anchor —
    is skipped rather than guessed at.
    """
    import requests

    results: Dict[str, Dict[str, Any]] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": LINK_CHECK_USER_AGENT})

    seen: Dict[str, Dict[str, Any]] = {}
    checked = 0

    for href in hrefs:
        raw = (href or "").strip()
        if not raw or raw.startswith(("mailto:", "tel:", "javascript:", "#")):
            results[href] = {"checked": False, "reason": "not a page link"}
            continue

        absolute = urljoin(base_url.rstrip("/") + "/", raw)
        if not absolute.startswith(("http://", "https://")):
            results[href] = {"checked": False, "reason": "not a page link"}
            continue

        if absolute in seen:
            results[href] = seen[absolute]
            continue

        if checked >= LINK_CHECK_LIMIT:
            results[href] = {"checked": False, "reason": f"beyond the {LINK_CHECK_LIMIT}-link check limit"}
            continue

        checked += 1
        outcome: Dict[str, Any]
        try:
            resp = session.head(absolute, timeout=LINK_CHECK_TIMEOUT_SECONDS, allow_redirects=True)
            if resp.status_code in (403, 405, 501):  # server dislikes HEAD
                resp = session.get(absolute, timeout=LINK_CHECK_TIMEOUT_SECONDS, allow_redirects=True, stream=True)
                resp.close()
            outcome = {
                "checked": True,
                "status_code": resp.status_code,
                "is_broken": resp.status_code >= 400,
                "redirected": resp.url.rstrip("/") != absolute.rstrip("/"),
                "final_url": resp.url,
            }
        except Exception as e:
            outcome = {
                "checked": True,
                "status_code": None,
                "is_broken": True,
                "error": f"{type(e).__name__}: {str(e)[:100]}",
            }

        seen[absolute] = outcome
        results[href] = outcome

    return results


def audit_page_internal_links(url_or_slug: str, site_key: str = "ccm") -> Dict[str, Any]:
    """
    Fetches the live post/page by URL or slug from WordPress REST API,
    audits existing links, and discovers contextual internal linking opportunities.
    """
    api_url, auth, site_cfg = get_wp_client(site_key)

    # Normalize slug
    cleaned = url_or_slug.strip()
    if "/" in cleaned:
        path = urlparse(cleaned).path.strip("/")
        slug = path.split("/")[-1] if path else cleaned
    else:
        slug = cleaned

    logger.info(f"Auditing internal links for slug='{slug}', site='{site_key}'")

    post_data = None
    post_type = "post"

    # Try fetching as post with context=edit to get live raw content
    try:
        r = requests.get(f"{api_url}/posts", params={"slug": slug, "context": "edit"}, auth=auth, timeout=20)
        if r.status_code == 200 and r.json():
            post_data = r.json()[0]
            post_type = "post"
    except Exception as e:
        logger.warning(f"Error fetching WP post: {e}")

    # Try fetching as page if not found as post
    if not post_data:
        try:
            r = requests.get(f"{api_url}/pages", params={"slug": slug, "context": "edit"}, auth=auth, timeout=20)
            if r.status_code == 200 and r.json():
                post_data = r.json()[0]
                post_type = "page"
        except Exception as e:
            logger.warning(f"Error fetching WP page: {e}")

    # Fallback to public HTTP scrape if WP API didn't find or auth is missing
    raw_content = ""
    post_title = slug.replace("-", " ").title()
    post_id = None
    post_link = url_or_slug

    if post_data:
        post_id = post_data.get("id")
        post_title = (post_data.get("title") or {}).get("raw") or (post_data.get("title") or {}).get("rendered", post_title)
        raw_content = (post_data.get("content") or {}).get("raw") or (post_data.get("content") or {}).get("rendered", "")
        post_link = post_data.get("link", url_or_slug)
    else:
        # Direct fetch from public web
        try:
            target_url = url_or_slug if url_or_slug.startswith("http") else f"{site_cfg['base_url']}/{slug}/"
            resp = requests.get(target_url, timeout=15)
            if resp.status_code == 200:
                raw_content = resp.text
                post_link = target_url
        except Exception as e:
            logger.warning(f"Public fallback fetch failed: {e}")

    if not raw_content:
        # A page that could not be read has no links to audit. This used to
        # substitute an invented paragraph — "Welcome to {title}. We provide
        # premium airport transfers..." — and then audit that, so a URL that
        # does not exist still produced a confident report about its links.
        return {
            "post_id": post_id,
            "post_type": None,
            "post_title": post_title,
            "post_url": post_link,
            "slug": slug,
            "readable": False,
            "error": (
                f"Could not read '{url_or_slug}'. It was not found through the WordPress API "
                f"and the public URL returned no content. Check the slug, or that the blog "
                f"agent's WordPress credentials are set for this site."
            ),
            "existing_links_count": 0,
            "existing_links": [],
            "opportunities_count": 0,
            "opportunities": [],
            "audit_score": None,
            "seo_recommendations": [
                "Nothing was audited — the page could not be read.",
            ],
        }

    # 1. Audit Existing Links
    existing_links: List[Dict[str, Any]] = []
    link_pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href=(["\'])(.*?)\1[^>]*?>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    matches = link_pattern.findall(raw_content)

    for _, href, anchor_html in matches:
        clean_anchor = re.sub(r'<[^>]+>', '', anchor_html).strip()
        is_internal = site_cfg["base_url"].replace("http://", "").replace("https://", "") in href or href.startswith("/")
        
        # Determine anchor quality
        quality = "Optimal"
        verdict_badge = "success"
        notes = "Good descriptive anchor text pointing to a relevant target page."
        
        anchor_lower = clean_anchor.lower()
        if anchor_lower in ["click here", "read more", "here", "link", "this page", "website", "more"]:
            quality = "Generic Anchor"
            verdict_badge = "warning"
            notes = "Generic anchor text. Recommend replacing with a keyword-rich descriptive phrase."
        elif len(clean_anchor) > 60:
            quality = "Long Anchor"
            verdict_badge = "warning"
            notes = "Anchor text is unusually long. Shorten to 2-5 core keyword words."
        elif not is_internal:
            quality = "External Link"
            verdict_badge = "info"
            notes = "External authority citation. Ensure target opens in new tab or has rel='noopener'."

        existing_links.append({
            "href": href,
            "anchor_text": clean_anchor,
            "is_internal": is_internal,
            "quality": quality,
            "verdict_badge": verdict_badge,
            "notes": notes
        })

    # 1b. Do the targets actually load? Anchor wording was graded without ever
    # asking, so a link to a 404 came back "Optimal".
    link_status = check_link_targets([l["href"] for l in existing_links], site_cfg["base_url"])
    broken_links: List[Dict[str, Any]] = []
    for link in existing_links:
        status = link_status.get(link["href"], {})
        link["link_check"] = status
        if status.get("is_broken"):
            code = status.get("status_code")
            link["quality"] = "Broken Link"
            link["verdict_badge"] = "danger"
            link["notes"] = (
                f"Target returns HTTP {code}."
                if code else f"Target could not be reached ({status.get('error', 'no response')})."
            ) + " Fix or remove this link — it costs the reader and wastes crawl budget."
            broken_links.append({
                "href": link["href"],
                "anchor_text": link["anchor_text"],
                "status_code": code,
                "error": status.get("error"),
                "is_internal": link["is_internal"],
            })
        elif status.get("redirected"):
            link["notes"] += f" Redirects to {status.get('final_url')}."

    # 2. Discover New Contextual Linking Opportunities
    candidates = load_candidate_internal_pages(site_key)
    opportunities: List[Dict[str, Any]] = []

    # Strip existing HTML tags to search sentences
    clean_text = re.sub(r'<[^>]+>', ' ', raw_content)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    sentences = re.split(r'(?<=[.!?])\s+', clean_text)

    already_linked_urls = set()
    for l in existing_links:
        h = l["href"].rstrip("/").replace("http://", "https://").lower()
        already_linked_urls.add(h)
        parsed = urlparse(l["href"])
        if parsed.path:
            already_linked_urls.add(parsed.path.rstrip("/").lower())

    # Add self URL to avoid self-linking
    post_link_clean = post_link.rstrip("/").replace("http://", "https://").lower()
    already_linked_urls.add(post_link_clean)
    if urlparse(post_link).path:
        already_linked_urls.add(urlparse(post_link).path.rstrip("/").lower())

    for cand in candidates:
        cand_url = cand["url"].rstrip("/").replace("http://", "https://").lower()
        cand_path = urlparse(cand["url"]).path.rstrip("/").lower()
        if cand_url in already_linked_urls or (cand_path and cand_path in already_linked_urls):
            continue

        kw = cand["keyword"].strip()
        if not kw or len(kw) < 4:
            continue

        # Look for keyword match in sentences
        kw_regex = re.compile(rf'\b({re.escape(kw)})\b', re.IGNORECASE)
        for s in sentences:
            m = kw_regex.search(s)
            if m:
                matched_phrase = m.group(1)
                # Create snippet with highlighted phrase
                snippet = kw_regex.sub(rf'<mark style="background:rgba(245,158,11,0.3); color:#f59e0b; padding:2px 6px; border-radius:4px; font-weight:700;">\1</mark>', s)
                
                opportunities.append({
                    "target_url": cand["url"],
                    "target_keyword": kw.title(),
                    "category": cand.get("category", "Landing Page"),
                    "matched_anchor": matched_phrase,
                    "sentence_snippet": snippet.strip(),
                    "raw_sentence": s.strip(),
                    "relevance_score": 96 if "airport" in kw.lower() or "corporate" in kw.lower() or "fleet" in kw.lower() else 85,
                    "selected": len(opportunities) < 4  # pre-select top 4
                })
                break

        if len(opportunities) >= 8:
            break

    # If no natural matches, add strategic pillar suggestions
    if not opportunities:
        for p in [
            {"url": f"{site_cfg['base_url']}/services/airport-transfers/", "keyword": "Airport Transfers", "category": "Pillar"},
            {"url": f"{site_cfg['base_url']}/fleet/executive-sedans/", "keyword": "Executive Sedans", "category": "Fleet"}
        ]:
            opportunities.append({
                "target_url": p["url"],
                "target_keyword": p["keyword"],
                "category": p["category"],
                "matched_anchor": p["keyword"],
                "sentence_snippet": f"Add link to {p['keyword']} in conclusion CTA.",
                "raw_sentence": "",
                "relevance_score": 90,
                "selected": True
            })

    # Overall Audit Score
    existing_count = len(existing_links)
    audit_score = 100
    if existing_count == 0:
        audit_score = 45
    elif existing_count < 2:
        audit_score = 70
    elif any(l["quality"] == "Generic Anchor" for l in existing_links):
        audit_score = 80

    # A page carrying dead links is not a healthy page, whatever its anchor
    # wording. Before this, the score ignored them entirely.
    if broken_links:
        audit_score = min(audit_score, 55 if len(broken_links) > 1 else 65)

    return {
        "post_id": post_id,
        "post_type": post_type,
        "post_title": post_title,
        "post_url": post_link,
        "slug": slug,
        "existing_links_count": existing_count,
        "existing_links": existing_links,
        "opportunities_count": len(opportunities),
        "opportunities": opportunities,
        "audit_score": audit_score,
        "broken_links_count": len(broken_links),
        "broken_links": broken_links,
        "links_checked": sum(1 for s in link_status.values() if s.get("checked")),
        "seo_recommendations": (
            [
                f"{len(broken_links)} link{'s' if len(broken_links) != 1 else ''} on this page "
                f"{'do' if len(broken_links) != 1 else 'does'} not load: "
                f"{', '.join((b['href'] or '')[:60] for b in broken_links[:3])}. "
                f"Fix or remove {'them' if len(broken_links) != 1 else 'it'} first."
            ] if broken_links else []
        ) + [
            f"Current internal links found: {existing_count}. Google recommends 3 to 5 internal links per 1,000 words.",
            "Distribute links evenly across the Introduction, Body paragraphs, and Conclusion CTA.",
            "Use descriptive target keyword anchors (e.g. 'Melbourne Airport Transfers') rather than generic words."
        ]
    }


def apply_internal_links_to_page(
    post_id: int,
    post_type: str,
    links_to_apply: List[Dict[str, Any]],
    site_key: str = "ccm"
) -> Dict[str, Any]:
    """
    Applies selected internal links to a live WordPress post/page via REST API.
    """
    api_url, auth, site_cfg = get_wp_client(site_key)

    endpoint = f"{api_url}/posts/{post_id}" if post_type == "post" else f"{api_url}/pages/{post_id}"
    
    # 1. Fetch current editable content
    r = requests.get(endpoint, auth=auth, params={"context": "edit"}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to fetch {post_type} {post_id} from WordPress: HTTP {r.status_code}")

    post_json = r.json()
    content = (post_json.get("content") or {}).get("raw") or (post_json.get("content") or {}).get("rendered", "")

    applied_count = 0
    applied_details = []

    for item in links_to_apply:
        url = item.get("target_url")
        anchor = item.get("matched_anchor") or item.get("target_keyword")
        if not url or not anchor:
            continue

        if url in content:
            continue

        # Regex replace first occurrence outside of existing tags
        pattern = re.compile(rf'(?<!href=[\'"])(?<!>)\b({re.escape(anchor)})\b(?![^<]*>|</a>)', re.IGNORECASE)
        new_content, count = pattern.subn(rf'<a href="{url}" title="{anchor}">\1</a>', content, count=1)
        if count > 0:
            content = new_content
            applied_count += 1
            applied_details.append({"anchor": anchor, "url": url})

    # 2. Update post on WordPress
    update_payload = {"content": content}
    update_res = requests.post(endpoint, json=update_payload, auth=auth, timeout=30)
    if update_res.status_code not in (200, 201):
        raise RuntimeError(f"Failed to update WordPress post: HTTP {update_res.status_code} - {update_res.text[:200]}")

    logger.info(f"Successfully applied {applied_count} internal links to WP {post_type} {post_id}")

    return {
        "status": "success",
        "post_id": post_id,
        "post_type": post_type,
        "links_applied_count": applied_count,
        "applied_details": applied_details,
        "updated_url": post_json.get("link", "")
    }


class InternalLinkingAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="internal-linking-agent",
            name="Internal Linking Agent",
            description="Audits existing page links, finds contextual linking opportunities, and automatically applies links to WordPress in 1 click.",
            category="SEO & Content",
            enabled=True,
            paused=False,
            supported_actions=["audit_page", "scan_opportunities", "apply_links", "recommend_anchors"],
            version="2.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "audit_page")).lower().strip()
        # The default was a specific Corporate Cars Melbourne blog post, so a
        # task that named no URL analysed that post whichever site it was for.
        source_url = str(input_data.get("source_url") or input_data.get("url") or "").strip()
        site_key = str(input_data.get("site_key", "ccm")).strip()

        logger.info(f"Executing InternalLinkingAgent task: action={action}, source_url='{source_url}'")

        if action in ["audit_page", "audit_links", "scan_opportunities"]:
            audit_result = audit_page_internal_links(source_url, site_key=site_key)
            return {
                "output": audit_result,
                "model_used": "deterministic-link-audit-engine",
                "tokens_used": 0,
                "cost_usd": 0.0
            }

        elif action == "apply_links":
            post_id = int(input_data.get("post_id", 0))
            post_type = str(input_data.get("post_type", "post"))
            links_to_apply = input_data.get("links_to_apply", [])
            apply_result = apply_internal_links_to_page(post_id, post_type, links_to_apply, site_key=site_key)
            return {
                "output": apply_result,
                "model_used": "wordpress-rest-link-injector",
                "tokens_used": 0,
                "cost_usd": 0.0
            }

        return {
            "output": {"error": f"Unknown action: {action}"},
            "model_used": "none",
            "tokens_used": 0,
            "cost_usd": 0.0
        }

