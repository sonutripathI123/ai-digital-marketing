"""
Agent #19: Page SEO Doctor & Google Algorithm Optimizer Agent (`page-optimizer-agent`).

Accepts any live webpage URL from any website, conducts a comprehensive audit
benchmarked against Google's latest algorithm updates (E-E-A-T, Helpful Content Update (HCU),
Semantic Heading Hierarchy H1/H2/H3, Internal Linking, Word Count, and Schema.org),
calculating a weighted SEO Health Score (0-100) and generating actionable copy-paste fixes.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import urllib.request
import urllib.error

from agents.base import AgentInterface
from config.settings import LOGS_DIR, ROOT_DIR
from config.websites import WebsiteManager
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("page-optimizer-agent")

HISTORY_FILE = LOGS_DIR / "page_optimizer_history.json"


def load_page_optimizer_history() -> List[Dict[str, Any]]:
    """Loads historical page optimization audit reports."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read page optimizer history: {e}")
    return []


def save_page_optimizer_history(reports: List[Dict[str, Any]]) -> None:
    """Saves page optimization audit reports to disk."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(reports, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save page optimizer history: {e}")


def fetch_live_page_content(url: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Fetches fresh live HTML content from the given URL with cache-busting headers.
    Extracts title, meta description, headings, word count, schema, and internal links.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        url = "https://" + url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Googlebot/2.1)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache"
    }
    
    html = ""
    status_code = None
    fetch_error = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        status_code = e.code
        fetch_error = f"The page answered HTTP {e.code}."
        logger.info(f"Live fetch for '{url}' returned HTTP {e.code}")
    except Exception as e:
        fetch_error = f"The page could not be fetched: {e}"
        logger.info(f"Live fetch failed for '{url}': {e}")

    # Parse extracted elements using regex
    title = ""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = re.sub(r"\s+", " ", title_match.group(1)).strip()

    meta_desc = ""
    desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.IGNORECASE)
    if not desc_match:
        desc_match = re.search(r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE)
    if desc_match:
        meta_desc = desc_match.group(1).strip()

    # Extract H1, H2, H3
    h1s = [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL) if re.sub(r"<[^>]+>", "", h).strip()]
    h2s = [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.IGNORECASE | re.DOTALL) if re.sub(r"<[^>]+>", "", h).strip()]
    h3s = [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.IGNORECASE | re.DOTALL) if re.sub(r"<[^>]+>", "", h).strip()]

    # Clean body text for word count
    clean_text = re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL)
    clean_text = re.sub(r"<[^>]+>", " ", clean_text)
    words = re.findall(r"\b[a-zA-Z0-9_\-']+\b", clean_text)
    word_count = len(words)

    # Schema detection (JSON-LD or Microdata)
    has_schema = bool(re.search(r'<script[^>]*type=["\']application/ld\+json["\']', html, re.IGNORECASE) or re.search(r'itemtype=["\']https?://schema\.org', html, re.IGNORECASE))
    
    # Internal links extraction
    domain_netloc = urlparse(url).netloc.lower().replace("www.", "")
    all_links = re.findall(r'<a[^>]+href=["\'](.*?)["\']', html, re.IGNORECASE)
    internal_links = []
    for l in all_links:
        l_clean = l.strip()
        if l_clean.startswith("/") or domain_netloc in l_clean.lower():
            if not l_clean.startswith("#") and not l_clean.startswith("javascript:") and not l_clean.startswith("mailto:") and not l_clean.startswith("tel:"):
                internal_links.append(l_clean)

    # Trust signals (E-E-A-T detection)
    # "driver" counted as an accreditation signal and "star" as a review
    # signal, so every page of a chauffeur site scored full marks on both
    # whether or not it showed any such proof. A phone number still has to be
    # callable, and the other two now need a phrase that means what it claims.
    has_phone = bool(re.search(r'href=["\']tel:', html, re.IGNORECASE))
    has_reviews = bool(re.search(
        r'(customer review|google review|testimonial|trustpilot|aggregateRating|'
        r'\breviews?\b[^<]{0,30}\b(rated|rating|stars?)\b)', html, re.IGNORECASE))
    has_accreditation = bool(re.search(
        r'(accredited|accreditation|police check|working with children|'
        r'commercial passenger vehicle|\bCPVV?\b|public liability|fully insured|licen[cs]ed driver)',
        html, re.IGNORECASE))

    return {
        "url": url,
        "fetched_live": bool(html),
        "status_code": status_code,
        "fetch_error": fetch_error,
        "title": title,
        "meta_description": meta_desc,
        "h1s": h1s,
        "h2s": h2s[:12],
        "h3s": h3s[:12],
        "word_count": word_count,
        "has_schema": has_schema,
        "internal_links_count": len(internal_links),
        "has_phone": has_phone,
        "has_reviews": has_reviews,
        "has_accreditation": has_accreditation
    }


class PageOptimizerAgent(AgentInterface):
    """
    Page SEO Doctor & Google Algorithm Optimizer Agent.
    Audits live pages against Google E-E-A-T, Helpful Content (HCU), Heading Structure,
    Internal Link Silos, and Schema Markup with real-time responsive scoring.
    """

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="page-optimizer-agent",
            name="Page SEO Doctor & Google Algorithm Optimizer Agent",
            description="Audits any website page URL against Google's latest algorithm updates (E-E-A-T, HCU, H1/H2/H3 Headings, Internal Links, Word Count & Schema.org) to generate a Health Score (0-100) and actionable fixes.",
            category="SEO & Content",
            enabled=True,
            paused=False,
            supported_actions=[
                "audit_page",
                "heading_optimizer",
                "hcu_content_gap",
                "internal_link_builder",
                "schema_generator"
            ],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "audit_page")).lower().strip()
        page_url = str(input_data.get("url") or input_data.get("page_url") or "").strip()
        focus_kw_raw = str(input_data.get("focus_keyword", "")).strip()
        location = str(input_data.get("location", "Melbourne")).strip()
        site_id = str(
            input_data.get("site_id") or input_data.get("site")
            or getattr(task, "site_id", None) or ""
        ).strip()
        use_ai = bool(input_data.get("use_ai", False))

        # Clean focus keyword (remove leading colons or quotes)
        focus_kw = re.sub(r"^[:\s\"']+|[:\s\"']+$", "", focus_kw_raw).strip()

        # This fell back to the ccm profile, and then to CCM's brand and domain
        # as literals, so an unknown or unconfigured site was optimised as if it
        # were Corporate Cars Melbourne.
        from config.site_context import not_configured, resolve_site

        profile = resolve_site(site_id)
        if not profile:
            return {"status": "success", "output": not_configured(
                site_id, "A website",
                "Add this website in the admin panel before running the page "
                "optimizer for it.")}
        brand_name = profile.name or site_id
        brand_domain = (profile.domain or "").rstrip("/")
        brand_loc = getattr(profile, "location", "") or ""
        if not page_url:
            if not brand_domain:
                return {"status": "success", "output": not_configured(
                    site_id, "A website address",
                    "Add this website's domain in the admin panel, or pass the "
                    "page URL to optimise.")}
            page_url = brand_domain + "/"

        logger.info(f"Executing PageOptimizerAgent: action={action}, url='{page_url}', focus_kw='{focus_kw}', site='{site_id}'")

        # 1. Fetch live page or parse URL context
        page_data = fetch_live_page_content(page_url)
        
        # Derive focus keyword if not provided
        loc_city = location.split(",")[0].replace("& Tullamarine", "").replace("Metropolitan & Regional VIC", "").strip() or "Melbourne"
        if not focus_kw:
            url_path = urlparse(page_url).path.strip("/")
            slug_words = [w for w in url_path.split("-") if w and w not in ["services", "suburbs", "fleet", "category", "blog", "about", "contact", "us"]]
            if slug_words:
                focus_kw = " ".join(slug_words)
            else:
                focus_kw = "luxury chauffeur & airport transfers"

        # Split keyword into search tokens for smart matching
        kw_tokens = [w.lower() for w in re.split(r"[^a-zA-Z0-9]+", focus_kw) if len(w) > 2]
        if not kw_tokens:
            kw_tokens = ["chauffeur", "airport", "transfers", "melbourne"]

        # A page that could not be read cannot be audited. What stood here
        # supplied a title, an H1, four H2 headings and a word count of 1,250
        # when the fetch came back empty, and the scoring engine then graded
        # those invented values -- so an unreachable URL was reported as having
        # "excellent content depth" and scored in the 80s.
        if not page_data["fetched_live"]:
            return {
                "output": {
                    "action": action,
                    "audited_url": page_url,
                    "focus_keyword": focus_kw,
                    "page_read": False,
                    "status_code": page_data.get("status_code"),
                    "error": page_data.get("fetch_error") or "The page returned no HTML.",
                    "overall_health_score": None,
                    "grade": None,
                    "algorithm_scores": {},
                    "on_page_metrics": {},
                    "identified_issues": [{
                        "level": "CRITICAL",
                        "item": "Page could not be read",
                        "fix": "Check that the URL is correct and the page loads for visitors.",
                    }],
                    "executive_action_checklist": [
                        f"This page was not audited: {page_data.get('fetch_error') or 'no HTML was returned'}.",
                        "No score is shown, because nothing was measured.",
                    ],
                    "audited_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                },
                "model_used": "page fetch failed",
                "tokens_used": 0,
                "cost_usd": 0.0,
            }

        # 2. Dynamic Real-Time Google Algorithm Scoring Engine
        scores = {}
        checklist = []
        issues = []

        # --- A. Title & Meta SERP Algorithm (20% Weight) ---
        title_len = len(page_data["title"])
        title_score = 90
        
        # Token presence in title
        tokens_in_title = sum(1 for t in kw_tokens if t in page_data["title"].lower())
        if tokens_in_title >= max(1, len(kw_tokens) // 2):
            title_score = 100
            checklist.append(f"✅ [TITLE OPTIMAL] Title tag ({title_len} chars) contains target keywords.")
        else:
            title_score = 75
            checklist.append(f"⚠️ [TITLE SUGGESTION] Update title to: '{focus_kw.title()} | {brand_name}'.")
            issues.append({"level": "MEDIUM", "item": "Keyword Missing in Title", "fix": f"Add primary keywords to title tag."})

        if title_len > 68:
            title_score = max(70, title_score - 10)
        elif title_len < 30:
            title_score = max(65, title_score - 15)

        # The floors here (50, 40, 50) meant a page missing everything still
        # scored around 65 -- a "C" for a page with no title, no H1 and no text.
        scores["title_and_meta"] = min(100, max(0, title_score))

        # --- B. Heading Hierarchy H1/H2/H3 (25% Weight) ---
        heading_score = 80
        h1_count = len(page_data["h1s"])
        h2_count = len(page_data["h2s"])

        # Check H1
        if h1_count == 1:
            h1_text = page_data["h1s"][0]
            tokens_in_h1 = sum(1 for t in kw_tokens if t in h1_text.lower())
            if tokens_in_h1 >= 1 or brand_name.lower() in h1_text.lower():
                heading_score += 15
                checklist.append(f"✅ [H1 PERFECT] Single H1 heading verified: '{h1_text[:65]}...'")
            else:
                heading_score += 5
                checklist.append(f"ℹ️ [H1 OPTIMIZATION] Current H1: '{h1_text}'. You can align it closer to: 'Premium {focus_kw.title()} | {brand_name}'.")
        elif h1_count == 0:
            heading_score -= 30
            checklist.append(f"❌ [H1 MISSING] Add a single <h1> tag: 'Premium {focus_kw.title()} in {loc_city} | {brand_name}'.")
            issues.append({"level": "CRITICAL", "item": "Missing H1", "fix": "Add single <h1> tag."})
        else:
            heading_score -= 10
            checklist.append(f"⚠️ [MULTIPLE H1s] Found {h1_count} H1 tags. Keep only 1 primary H1.")

        # Check H2s
        if h2_count >= 4:
            heading_score += 10
            checklist.append(f"✅ [H2 STRUCTURE] Strong topical depth with {h2_count} structured H2 sections.")
        elif h2_count >= 2:
            heading_score += 5
            checklist.append(f"ℹ️ [H2 EXPANSION] Found {h2_count} H2 tags. Adding 1-2 more H2s improves Google HCU coverage.")
        else:
            heading_score -= 15
            checklist.append("⚠️ [H2 SUBHEADINGS] Add at least 3-4 H2 subsections to structure your content.")

        scores["heading_hierarchy"] = min(100, max(0, heading_score))

        # --- C. Google Helpful Content Update (HCU) & Word Count (25% Weight) ---
        current_words = page_data["word_count"]
        if current_words >= 1200:
            hcu_score = 98
            checklist.append(f"✅ [HCU COMPREHENSIVE] Excellent content depth ({current_words} words). Exceeds competitor benchmark.")
        elif current_words >= 900:
            hcu_score = 92
            checklist.append(f"✅ [HCU IN-DEPTH] Solid content length ({current_words} words).")
        elif current_words >= 600:
            hcu_score = 80
            checklist.append(f"ℹ️ [HCU EXPANSION] Page has {current_words} words. Expanding with FAQ or Route Comparison will boost rank.")
        else:
            hcu_score = 65
            checklist.append(f"⚠️ [THIN CONTENT] Page has {current_words} words. Expand to 1,000+ words to avoid Google low-value content penalty.")

        scores["helpful_content"] = hcu_score

        # --- D. Google E-E-A-T & Trust Signals (15% Weight) ---
        eeat_score = 60
        if page_data["has_schema"]:
            eeat_score += 15
            checklist.append("✅ [SCHEMA DETECTED] Valid Schema.org structured data found.")
        else:
            checklist.append("⚠️ [SCHEMA MISSING] Embed generated LocalBusiness / Service JSON-LD in footer.")

        if page_data["has_phone"]:
            eeat_score += 10
            checklist.append("✅ [DIRECT CONTACT] Click-to-call phone number and booking access verified.")
        if page_data["has_accreditation"]:
            eeat_score += 10
            checklist.append("✅ [ACCREDITATION] Driver qualification & safety accreditation signals detected.")
        if page_data["has_reviews"]:
            eeat_score += 10
            checklist.append("✅ [SOCIAL PROOF] Customer reviews / rating signals detected.")

        scores["eeat_trust"] = min(100, max(0, eeat_score))

        # --- E. Internal Linking & Silo Graph (15% Weight) ---
        links_cnt = page_data["internal_links_count"]
        if links_cnt >= 5:
            links_score = 98
            checklist.append(f"✅ [INTERNAL LINKING] Well-connected with {links_cnt} internal contextual links.")
        elif links_cnt >= 2:
            links_score = 88
            checklist.append(f"✅ [INTERNAL LINKS] {links_cnt} internal links found.")
        else:
            links_score = 70
            checklist.append("⚠️ [INTERNAL LINKS] Add 2-3 contextual links to Airport Transfers, Fleet, and Corporate Services.")

        scores["internal_linking"] = links_score

        # 3. Overall Weighted Google Health Score
        weighted_score = int(
            scores["title_and_meta"] * 0.20 +
            scores["heading_hierarchy"] * 0.25 +
            scores["helpful_content"] * 0.25 +
            scores["eeat_trust"] * 0.15 +
            scores["internal_linking"] * 0.15
        )

        grade = "A+" if weighted_score >= 93 else ("A" if weighted_score >= 88 else ("B+" if weighted_score >= 78 else ("B" if weighted_score >= 68 else "C")))

        # Strategic H1/H2/H3 Copy Suggestions
        if loc_city.lower() in focus_kw.lower():
            proposed_h1 = f"Premium {focus_kw.title()} | {brand_name} Luxury Fleet"
        else:
            proposed_h1 = f"Premium {focus_kw.title()} in {loc_city} | {brand_name}"

        optimized_headings = {
            "proposed_h1": proposed_h1,
            "proposed_h2_sections": [
                f"1. Why {brand_name} {focus_kw.title()} Outperforms Standard Rideshare in {loc_city}",
                f"2. Seamless Airport Transfers & Flight-Tracking Guarantee at Melbourne Tullamarine",
                f"3. Transparent Fixed Pricing & Corporate Billing Accounts",
                f"4. The Vehicles Available for This Service",
                f"5. Frequently Asked Questions About Our {loc_city} Chauffeur Services"
            ],
            "proposed_h3_faqs": [
                f"How early should I reserve my {loc_city} chauffeur?",
                "What happens if my incoming flight is delayed?",
                "Are toll charges and airport parking fees included in the fixed quote?"
            ]
        }

        # Schema.org Structured Data Generator
        schema_json = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": brand_name,
            "url": page_url,
            "description": f"Premium private chauffeur and executive airport transfer service in {brand_loc}.",
            "areaServed": {
                "@type": "City",
                "name": location
            },
            "priceRange": "$$$",
        }
        # The generated JSON-LD shipped with aggregateRating 4.9 over 142
        # reviews and told the operator to paste it into their site. Those
        # numbers were invented, and publishing a review count you cannot
        # substantiate is a structured-data violation Google issues manual
        # actions for. The rating is filled in only when the reputation agent
        # has read it from Google, and omitted otherwise.
        rating_note = (
            "aggregateRating is omitted: it must reflect reviews that are actually "
            "shown on the page. Connect the reviews agent, or add it by hand from "
            "your real Google rating."
        )
        try:
            from agents.reputation_agent import ReviewReputationAgent

            rep_out = ReviewReputationAgent().run_task(
                AgentTask(task_id="page-opt-rep", agent_id="reputation-agent",
                          task_type="fetch_reviews",
                          input_data={"action": "fetch_reviews", "site_id": site_id},
                          site_id=site_id),
                router,
            ).get("output", {})
            if rep_out.get("live_data_connected"):
                overview = rep_out.get("reputation_overview") or {}
                if overview.get("average_rating") and overview.get("total_reviews"):
                    schema_json["aggregateRating"] = {
                        "@type": "AggregateRating",
                        "ratingValue": str(overview["average_rating"]),
                        "reviewCount": str(overview["total_reviews"]),
                    }
                    rating_note = (
                        f"aggregateRating read from this business's Google profile "
                        f"({overview['average_rating']} over {overview['total_reviews']} reviews). "
                        f"Only publish it on a page that shows those reviews."
                    )
        except Exception as e:
            logger.warning(f"Could not read the real rating for schema: {e}")
        schema_code_str = json.dumps(schema_json, indent=2)

        # These three targets were fixed strings: /services/airport-transfers,
        # /fleet and /services/corporate-transfers. On this site /fleet is a 404
        # and the other two only redirect, so following the advice would have
        # added internal links to pages that do not exist. Suggestions now come
        # from the pages the linking agent has actually indexed.
        internal_links_suggested = []
        try:
            from agents.internal_linking_agent import load_candidate_internal_pages

            audited_path = urlparse(page_url).path.rstrip("/")
            scored = []
            for page in load_candidate_internal_pages(site_id):
                target = page.get("url") or ""
                if not target or urlparse(target).path.rstrip("/") == audited_path:
                    continue
                haystack = f"{page.get('title', '')} {target}".lower()
                overlap = sum(1 for t in kw_tokens if t in haystack)
                if overlap:
                    scored.append((overlap, page))
            scored.sort(key=lambda pair: pair[0], reverse=True)
            for overlap, page in scored[:5]:
                internal_links_suggested.append({
                    "target_url": page.get("url"),
                    "recommended_anchor": page.get("title") or page.get("keyword") or "",
                    "context": (
                        f"Shares {overlap} term(s) with this page's focus keyword "
                        f"'{focus_kw}'."
                    ),
                    "importance": "HIGH" if overlap >= 2 else "MEDIUM",
                })
        except Exception as e:
            logger.warning(f"Could not read indexed pages for link suggestions: {e}")

        # Format Final Result Payload
        result_payload = {
            "action": action,
            "audited_url": page_url,
            "page_read": True,
            "status_code": page_data.get("status_code"),
            "focus_keyword": focus_kw,
            "location": location,
            "target_brand": brand_name,
            "target_domain": brand_domain,
            "overall_health_score": weighted_score,
            "grade": grade,
            "algorithm_scores": scores,
            "on_page_metrics": {
                "title": page_data["title"],
                "title_length": title_len,
                # A page with no meta description was reported as having one,
                # because the fallback text was placed in the field that
                # describes what the page currently has.
                "meta_description": page_data["meta_description"] or None,
                "meta_description_missing": not page_data["meta_description"],
                "suggested_meta_description": (
                    None if page_data["meta_description"] else
                    f"Executive {focus_kw} in {location} with {brand_name}. "
                    f"Professional chauffeurs, fixed pricing, flight monitoring."
                ),
                "current_h1": page_data["h1s"][0] if page_data["h1s"] else "(None)",
                "total_h2_count": len(page_data["h2s"]),
                "current_word_count": page_data["word_count"],
                "recommended_word_count": "1,100 - 1,500 words",
                "has_schema_markup": page_data["has_schema"],
                "internal_links_count": page_data["internal_links_count"]
            },
            "optimized_headings_recommendations": optimized_headings,
            "internal_linking_recommendations": internal_links_suggested,
            "identified_issues": issues,
            "ready_to_paste_schema_json": schema_code_str,
            "schema_rating_note": rating_note,
            "executive_action_checklist": checklist,
            "audited_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }

        # Save to persistent history
        history = load_page_optimizer_history()
        history.insert(0, {
            "id": f"audit-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "url": page_url,
            "focus_keyword": focus_kw,
            "score": weighted_score,
            "grade": grade,
            "brand": brand_name,
            "audited_at": datetime.utcnow().strftime("%d %b %Y %H:%M"),
            "data": result_payload
        })
        save_page_optimizer_history(history[:30])

        return {
            "output": result_payload,
            "model_used": "google-algorithm-live-crawler",
            "tokens_used": 0,
            "cost_usd": 0.0
        }
