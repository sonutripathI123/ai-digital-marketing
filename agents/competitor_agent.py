"""
Agent #2: Competitor Analysis Agent (`competitor-analysis-agent`).

Fetches competitor pages and reports what is measurably on them — title and meta
lengths, heading structure, word count, Schema.org types, keyword placement,
image alt coverage, page weight and response time — alongside the same
measurements of your own page, so the gaps are differences rather than guesses.

This agent previously reported a "Domain Authority" computed as
`34 + (index * 6) + (len(domain) % 7)` — the length of the domain name — and a
"difficulty to outrank" derived from it, plus four content gaps and a list of
weaknesses that were the same hardcoded strings for every competitor. It made no
network requests at all, and seven of the ten domains it named do not resolve.
Nothing here is inferred: a page that cannot be fetched is reported as
unreachable rather than described.
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

from agents.base import AgentInterface
from config.settings import LOGS_DIR, ROOT_DIR
from config.websites import WebsiteManager
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("competitor-analysis-agent")

HISTORY_FILE = LOGS_DIR / "competitor_analysis_history.json"

FETCH_TIMEOUT_SECONDS = 15
FETCH_USER_AGENT = "AI-Digital-Marketing-OS/1.0 (SEO competitor audit; +https://corporatecarsmelbourne.com.au)"


def fetch_page(url: str) -> Dict[str, Any]:
    """Retrieve a page, or say why it could not be retrieved.

    Never raises. A failure returns reachable=False with the reason, so the
    caller reports "unreachable" rather than describing a page nobody saw.
    """
    import requests

    started = time.time()
    try:
        resp = requests.get(
            url,
            timeout=FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": FETCH_USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            allow_redirects=True,
        )
    except Exception as e:
        return {
            "reachable": False,
            "error": f"{type(e).__name__}: {str(e)[:160]}",
            "response_seconds": round(time.time() - started, 2),
        }

    elapsed = round(time.time() - started, 2)
    if resp.status_code >= 400:
        return {
            "reachable": False,
            "error": f"Responded HTTP {resp.status_code}",
            "status_code": resp.status_code,
            "response_seconds": elapsed,
            "final_url": resp.url,
        }

    return {
        "reachable": True,
        "status_code": resp.status_code,
        "html": resp.text,
        "page_bytes": len(resp.content),
        "response_seconds": elapsed,
        "final_url": resp.url,
    }


def measure_page(html: str, url: str, target_keyword: str) -> Dict[str, Any]:
    """Facts read off the page. Every value here came from the markup."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Read JSON-LD before stripping scripts. Stripping first removed the very
    # nodes the schema scan then looked for, so every page — including ones
    # carrying a full Yoast schema graph — was reported as declaring none.
    schema_types: List[str] = []

    def _collect_type(value: Any) -> None:
        for t in (value if isinstance(value, list) else [value]):
            if isinstance(t, str) and t not in schema_types:
                schema_types.append(t)

    for node in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = node.string or node.get_text() or ""
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            continue
        for entry in (parsed if isinstance(parsed, list) else [parsed]):
            if not isinstance(entry, dict):
                continue
            _collect_type(entry.get("@type"))
            for sub in entry.get("@graph", []) or []:
                if isinstance(sub, dict):
                    _collect_type(sub.get("@type"))
                    # Yoast nests FAQ questions one level deeper again.
                    for item in (sub.get("mainEntity") or []) if isinstance(sub.get("mainEntity"), list) else []:
                        if isinstance(item, dict):
                            _collect_type(item.get("@type"))

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = (soup.title.get_text(strip=True) if soup.title else "") or ""
    meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    meta_desc = (meta_desc_tag.get("content") or "").strip() if meta_desc_tag else ""

    site_name_tag = soup.find("meta", attrs={"property": "og:site_name"})
    site_name = (site_name_tag.get("content") or "").strip() if site_name_tag else ""

    h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2s = [h.get_text(strip=True) for h in soup.find_all("h2")]

    body_text = soup.get_text(separator=" ", strip=True)
    words = re.findall(r"[A-Za-z']+", body_text)
    word_count = len(words)

    kw = target_keyword.strip().lower()
    lower_text = body_text.lower()

    host = urlparse(url).netloc.lower()
    internal_links = external_links = 0
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        link_host = urlparse(urljoin(url, href)).netloc.lower()
        if not link_host or link_host == host:
            internal_links += 1
        else:
            external_links += 1

    images = soup.find_all("img")
    # alt="" is the correct markup for a purely decorative image, so it is
    # counted apart from an image with no alt attribute at all. Lumping them
    # together reports valid markup as a defect.
    images_no_alt_attribute = sum(1 for i in images if i.get("alt") is None)
    images_empty_alt = sum(1 for i in images if i.get("alt") is not None and not i["alt"].strip())

    return {
        "page_title": title,
        "title_length": len(title),
        "meta_description": meta_desc,
        "meta_description_length": len(meta_desc),
        "og_site_name": site_name,
        "h1_count": len(h1s),
        "h1_text": h1s[0] if h1s else "",
        "h2_count": len(h2s),
        "word_count": word_count,
        "schema_types": schema_types,
        "has_faq_schema": any(t.lower() == "faqpage" for t in schema_types),
        "has_localbusiness_schema": any("localbusiness" in t.lower() for t in schema_types),
        "keyword_in_title": bool(kw) and kw in title.lower(),
        "keyword_in_h1": bool(kw) and any(kw in h.lower() for h in h1s),
        "keyword_in_meta_description": bool(kw) and kw in meta_desc.lower(),
        "keyword_occurrences": lower_text.count(kw) if kw else 0,
        "internal_links": internal_links,
        "external_links": external_links,
        "images_total": len(images),
        "images_no_alt_attribute": images_no_alt_attribute,
        "images_empty_alt": images_empty_alt,
        "images_missing_alt": images_no_alt_attribute + images_empty_alt,
    }


def compare_pages(mine: Optional[Dict[str, Any]], theirs: Dict[str, Any], target_keyword: str) -> List[str]:
    """Differences between the two measured pages, stated as facts.

    Each line is something both pages were measured for. Nothing appears here
    that was not read off the markup.
    """
    gaps: List[str] = []

    if theirs.get("has_faq_schema") and not (mine or {}).get("has_faq_schema"):
        gaps.append("They publish FAQPage schema and your page does not — they are eligible for FAQ rich results, you are not.")
    if theirs.get("has_localbusiness_schema") and not (mine or {}).get("has_localbusiness_schema"):
        gaps.append("They declare LocalBusiness schema and your page does not.")

    their_words = theirs.get("word_count", 0)
    my_words = (mine or {}).get("word_count", 0)
    if mine and their_words > my_words * 1.3 and their_words > 300:
        gaps.append(f"Their page runs {their_words:,} words against your {my_words:,} — {their_words - my_words:,} more.")
    elif mine and my_words > their_words * 1.3 and my_words > 300:
        gaps.append(f"Your page is longer: {my_words:,} words against their {their_words:,}. Depth is not the gap here.")

    if theirs.get("keyword_in_title") and not (mine or {}).get("keyword_in_title"):
        gaps.append(f"'{target_keyword}' is in their page title and missing from yours.")
    if theirs.get("keyword_in_h1") and not (mine or {}).get("keyword_in_h1"):
        gaps.append(f"'{target_keyword}' is in their H1 and missing from yours.")

    their_kw = theirs.get("keyword_occurrences", 0)
    my_kw = (mine or {}).get("keyword_occurrences", 0)
    if mine and their_kw > my_kw + 2:
        gaps.append(f"They mention '{target_keyword}' {their_kw} times; your page mentions it {my_kw}.")

    if theirs.get("h2_count", 0) > (mine or {}).get("h2_count", 0) + 3:
        gaps.append(f"They structure the page with {theirs['h2_count']} H2 subheadings against your {(mine or {}).get('h2_count', 0)}.")

    if theirs.get("internal_links", 0) > (mine or {}).get("internal_links", 0) * 1.5 and theirs.get("internal_links", 0) > 20:
        gaps.append(f"They carry {theirs['internal_links']} internal links against your {(mine or {}).get('internal_links', 0)}.")

    if not gaps:
        gaps.append("No measurable on-page gap against this competitor on the fields checked.")
    return gaps


def load_competitor_history() -> List[Dict[str, Any]]:
    """Loads historical keyword competitor intelligence reports."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read competitor analysis history: {e}")
    return []


def save_competitor_history(reports: List[Dict[str, Any]]) -> None:
    """Saves competitor analysis reports to disk."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(reports, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save competitor analysis history: {e}")


class CompetitorAnalysisAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="competitor-analysis-agent",
            name="Competitor Analysis Agent",
            description="Finds and analyzes top ranking competitors by keyword, audits SEO positioning, reveals content gaps, and builds counter-strategies.",
            category="SEO & Content",
            enabled=True,
            paused=False,
            # One operation exists: fetch the pages and compare them. The other
            # four names were rendered as separate chips on the agent card, all
            # opening the same form, and run_task never branched on `action` —
            # so every one of them did the same thing under a different label.
            supported_actions=["find_by_keyword"],
            version="1.1.0"
        )

    def _discover_competitors_for_keyword(self, target_keyword: str, location: str, custom_urls: Optional[List[str]] = None) -> List[str]:
        """Discovers or normalizes competitor URLs for the given keyword and location."""
        if custom_urls and len(custom_urls) > 0 and any(u.strip() for u in custom_urls):
            cleaned = []
            for u in custom_urls:
                u = u.strip()
                if not u:
                    continue
                if not u.startswith("http://") and not u.startswith("https://"):
                    u = "https://" + u
                cleaned.append(u)
            if cleaned:
                return cleaned

        # Fallback suggestions only. These are not search results — the agent
        # does not query a SERP — and the previous list named ten domains of
        # which seven no longer resolve, so every run spent its time reporting
        # dead sites. Only domains that still answer are kept. Save your real
        # competitors against the site (Connect > Competitor Analysis) and those
        # are used instead of this list.
        kw_lower = target_keyword.lower()

        if "tour" in kw_lower or "winery" in kw_lower or "wine" in kw_lower:
            return [
                "https://yarravalleywinetours.com.au",
                "https://melbourneairportchauffeurs.com.au",
            ]
        return [
            "https://melbourneairportchauffeurs.com.au",
            "https://chauffeurcarsmelbourne.com.au",
            "https://yarravalleywinetours.com.au",
        ]

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "find_by_keyword")).lower().strip()
        target_keyword = str(input_data.get("target_keyword", "corporate chauffeur melbourne")).strip()
        location = str(input_data.get("location", "Melbourne")).strip()
        site_id = str(input_data.get("site_id") or input_data.get("site") or "ccm").strip()
        use_ai = bool(input_data.get("use_ai", False))

        raw_competitor_urls = input_data.get("competitor_urls") or input_data.get("competitor_url") or []
        if isinstance(raw_competitor_urls, str):
            raw_competitor_urls = [raw_competitor_urls] if raw_competitor_urls.strip() else []

        # Retrieve active site profile
        site_mgr = WebsiteManager()
        site_profile = site_mgr.get(site_id) or site_mgr.get("ccm")

        # Competitors the operator saved against this website beat the built-in
        # suggestions. Without this the agent could only ever look at a fixed
        # list that knows nothing about who this site actually competes with.
        url_source = "operator-supplied URLs"
        if not raw_competitor_urls and site_profile:
            saved = (site_profile.agent_credentials or {}).get("competitor-analysis-agent", {}) or {}
            saved_urls = saved.get("competitor_urls") or ""
            if isinstance(saved_urls, str):
                saved_urls = [u.strip() for u in re.split(r"[\n,]+", saved_urls) if u.strip()]
            if saved_urls:
                raw_competitor_urls = saved_urls
                url_source = "saved against this website"

        if not raw_competitor_urls:
            url_source = "built-in suggestion list (not live search results)"

        competitor_urls = self._discover_competitors_for_keyword(target_keyword, location, raw_competitor_urls)
        my_brand = site_profile.name if site_profile else "Corporate Cars Melbourne"
        my_domain = site_profile.domain if site_profile else "https://corporatecarsmelbourne.com.au"

        logger.info(f"Executing CompetitorAnalysisAgent: action={action}, kw='{target_keyword}', location='{location}', competitors={competitor_urls}")

        # Measure our own page first, so every gap below is a comparison rather
        # than an assertion about a page nobody fetched.
        my_page: Optional[Dict[str, Any]] = None
        my_fetch = fetch_page(my_domain)
        if my_fetch.get("reachable"):
            try:
                my_page = measure_page(my_fetch["html"], my_fetch.get("final_url", my_domain), target_keyword)
                my_page["response_seconds"] = my_fetch["response_seconds"]
                my_page["page_kb"] = round(my_fetch["page_bytes"] / 1024)
            except Exception as e:
                logger.warning(f"Could not measure own page {my_domain}: {e}")
        else:
            logger.warning(f"Own page {my_domain} unreachable: {my_fetch.get('error')}")

        gap_insights: List[Dict[str, Any]] = []
        reachable_count = 0

        for url in competitor_urls:
            domain = urlparse(url).netloc or url.replace("https://", "").replace("http://", "").split("/")[0]
            fetched = fetch_page(url)

            if not fetched.get("reachable"):
                gap_insights.append({
                    "competitor_name": domain.replace("www.", ""),
                    "competitor_url": url,
                    "competitor_domain": domain,
                    "reachable": False,
                    "error": fetched.get("error"),
                    "content_gaps": [
                        f"This site could not be fetched ({fetched.get('error')}). "
                        f"Nothing about it can be measured, so nothing is reported."
                    ],
                    "counter_strategy": "Confirm this domain is still a live competitor before spending effort on it.",
                })
                continue

            try:
                measured = measure_page(fetched["html"], fetched.get("final_url", url), target_keyword)
            except Exception as e:
                logger.warning(f"Could not parse {url}: {e}")
                gap_insights.append({
                    "competitor_name": domain.replace("www.", ""),
                    "competitor_url": url,
                    "competitor_domain": domain,
                    "reachable": False,
                    "error": f"Page fetched but could not be parsed: {e}",
                    "content_gaps": ["Page fetched but could not be parsed."],
                    "counter_strategy": "",
                })
                continue

            reachable_count += 1
            gaps = compare_pages(my_page, measured, target_keyword)

            counter = []
            if measured.get("has_faq_schema") and not (my_page or {}).get("has_faq_schema"):
                counter.append("add FAQPage schema")
            if measured.get("word_count", 0) > (my_page or {}).get("word_count", 0):
                counter.append(f"expand the page past their {measured['word_count']:,} words")
            if measured.get("keyword_in_title") and not (my_page or {}).get("keyword_in_title"):
                counter.append(f"put '{target_keyword}' in your title tag")

            gap_insights.append({
                # The name on the page, not one assembled from the domain.
                "competitor_name": measured.get("og_site_name") or measured.get("page_title") or domain.replace("www.", ""),
                "competitor_url": url,
                "competitor_domain": domain,
                "reachable": True,
                "measured": measured,
                "response_seconds": fetched["response_seconds"],
                "page_kb": round(fetched["page_bytes"] / 1024),
                "content_gaps": gaps,
                "counter_strategy": (
                    "To close the measured gap: " + ", ".join(counter) + "."
                    if counter else "No on-page change is indicated by the fields measured."
                ),
            })

        recommendations = []
        if my_page is None:
            recommendations.append(
                f"Your own page at {my_domain} could not be fetched, so these competitors were "
                f"measured without a baseline to compare against."
            )
        else:
            missing_faq = [g for g in gap_insights if g.get("reachable") and g["measured"].get("has_faq_schema")]
            if missing_faq and not my_page.get("has_faq_schema"):
                recommendations.append(
                    f"{len(missing_faq)} of the reachable competitors publish FAQPage schema and you do not — "
                    f"they qualify for FAQ rich results on this query and you do not."
                )
            longer = [g for g in gap_insights if g.get("reachable") and g["measured"].get("word_count", 0) > my_page.get("word_count", 0)]
            if longer:
                deepest = max(longer, key=lambda g: g["measured"]["word_count"])
                recommendations.append(
                    f"The longest reachable competitor page runs {deepest['measured']['word_count']:,} words "
                    f"against your {my_page.get('word_count', 0):,}."
                )
            if not my_page.get("keyword_in_title"):
                recommendations.append(f"'{target_keyword}' does not appear in your page title.")
            if my_page.get("images_missing_alt"):
                recommendations.append(
                    f"{my_page['images_missing_alt']} of your {my_page['images_total']} images have no alt text."
                )
        unreachable = len(competitor_urls) - reachable_count
        if unreachable:
            recommendations.append(
                f"{unreachable} of the {len(competitor_urls)} competitor URLs could not be fetched and were not analysed."
            )
        if not recommendations:
            recommendations.append("No measurable on-page disadvantage found against the reachable competitors.")

        timestamp_iso = datetime.utcnow().isoformat() + "Z"
        analysis_id = f"comp-analysis-{int(datetime.utcnow().timestamp())}"

        result_payload = {
            "analysis_id": analysis_id,
            "timestamp": timestamp_iso,
            "action": action,
            "target_keyword": target_keyword,
            "location": location,
            "my_brand": my_brand,
            "my_domain": my_domain,
            "competitors_analyzed_count": len(competitor_urls),
            "competitors_reachable_count": reachable_count,
            "competitors_unreachable_count": len(competitor_urls) - reachable_count,
            "competitors_discovered": [urlparse(u).netloc or u for u in competitor_urls],
            "competitor_source": url_source,
            "my_page_measured": my_page,
            "competitor_insights": gap_insights,
            "identified_content_gaps_count": sum(len(g["content_gaps"]) for g in gap_insights),
            "actionable_recommendations": recommendations,
            # A statement of what was measured. The previous text promised
            # outranking "within 30-45 days", which nothing here supports.
            "win_strategy_summary": (
                f"Fetched {reachable_count} of {len(competitor_urls)} competitor pages and compared them "
                f"against {my_domain} on title, meta, headings, word count, Schema.org types, keyword "
                f"placement, internal links and image alt text. Figures below are measured, not estimated; "
                f"search volume, domain authority and traffic are not available from a page fetch and are "
                f"not shown."
            ),
        }

        # Optional AI Enrichment
        tokens_used = 0
        cost_usd = 0.0
        model_used = "deterministic-serp-competitor-engine"

        if use_ai:
            prompt = (
                f"You are a Senior SEO Strategist analyzing search competitors for brand '{my_brand}' ({my_domain}).\n"
                f"Target Keyword: '{target_keyword}'\n"
                f"Location: '{location}'\n"
                f"Competitors Discovered: {competitor_urls}\n\n"
                f"Provide a JSON response with:\n"
                f"1. 'competitive_edge': Specific 3-step action plan to outrank these competitors.\n"
                f"2. 'high_opportunity_keywords': 5 high-converting LSI search queries competitors missed.\n"
                f"3. 'content_differentiation_angle': Unique selling hook for {my_brand}."
            )
            llm_req = LLMRequest(
                user_prompt=prompt,
                task_type=TaskComplexity.STANDARD,
                json_output=True
            )
            try:
                response = router.route_and_execute(llm_req)
                model_used = response.model_used
                tokens_used = response.tokens_in + response.tokens_out
                cost_usd = response.cost_usd
                if response.parsed_json:
                    result_payload["ai_insights"] = response.parsed_json
                else:
                    result_payload["ai_summary"] = response.content
            except Exception as e:
                logger.warning(f"AI competitor analysis failed (fallback to rule engine): {e}")

        # Save to persistent history
        try:
            history = load_competitor_history()
            history_entry = {
                "analysis_id": analysis_id,
                "created_at": timestamp_iso,
                "target_keyword": target_keyword,
                "location": location,
                "site_id": site_id,
                "site_name": my_brand,
                "data": result_payload
            }
            history.insert(0, history_entry)
            save_competitor_history(history[:30])
        except Exception as e:
            logger.error(f"Failed to persist competitor analysis history: {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd
        }

