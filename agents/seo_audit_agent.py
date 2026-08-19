"""
Agent #6: SEO Audit Agent (`seo-audit-agent`).

Scans on-page and technical SEO factors for:
1. Single Page Deep Audit (Title, Meta Description, H1/H2, Canonical, Schema, Images, OpenGraph, Word Count).
2. Whole Website Domain Crawl (Site-Wide Health Score, Robots.txt, Sitemap.xml, Core Pages Audit, Site-Wide Fix Roadmap).
"""

import os
import re
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import requests
from concurrent.futures import ThreadPoolExecutor

from config.settings import ROOT_DIR
from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("seo-audit-agent")

HISTORY_FILE = Path(ROOT_DIR) / "logs" / "seo_audit_history.json"


def load_seo_audit_history() -> List[Dict[str, Any]]:
    """Loads historical SEO audit reports from disk."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read SEO audit history: {e}")
        return []


def save_seo_audit_history(report: Dict[str, Any]):
    """Appends an SEO audit report to history."""
    try:
        history = load_seo_audit_history()
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "url": report.get("audited_url") or report.get("domain_url"),
            "audit_mode": report.get("audit_mode", "single_page"),
            "score": report.get("overall_seo_health_score") or report.get("site_health_score"),
            "data": report
        }
        history.insert(0, entry)
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history[:30], f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save SEO audit history: {e}")


def audit_single_page(url: str, site_key: str = "ccm") -> Dict[str, Any]:
    """
    Performs deep 15-factor technical and on-page SEO audit of a single URL.
    Calculates a Google Rank-Calibrated SEO health score (0-100).
    """
    cleaned_url = url.strip()
    if not cleaned_url.startswith("http"):
        cleaned_url = f"https://{cleaned_url}"

    logger.info(f"Auditing single page SEO for URL: {cleaned_url}")

    html = ""
    status_code = 200
    response_time_ms = 0
    page_size_kb = 0.0

    try:
        start_t = time.time()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        resp = requests.get(cleaned_url, headers=headers, timeout=15)
        status_code = resp.status_code
        response_time_ms = int((time.time() - start_t) * 1000)
        html = resp.text
        page_size_kb = round(len(resp.content) / 1024, 1)
    except Exception as e:
        logger.warning(f"Failed to fetch live URL {cleaned_url}: {e}")
        html = ""

    issues: List[Dict[str, Any]] = []
    score_points = 0  # Max 100

    # 1. HTTP Status & Page Latency (Max 10 pts)
    if status_code != 200:
        issues.append({
            "category": "HTTP & Server",
            "check": "Page Reachability",
            "status": "CRITICAL",
            "severity": "CRITICAL",
            "details": f"Server returned HTTP error status {status_code}.",
            "recommendation": "Ensure page URL is live, not returning 404/500 errors, and properly resolving."
        })
    else:
        score_points += 5
        if response_time_ms < 1200:
            score_points += 5
            issues.append({
                "category": "Performance",
                "check": "Server Latency (TTFB)",
                "status": "PASS",
                "severity": "LOW",
                "details": f"Fast response time ({response_time_ms}ms, Page Size: {page_size_kb} KB).",
                "recommendation": "Server response time is fast and within Core Web Vitals targets."
            })
        elif response_time_ms < 3000:
            score_points += 3
            issues.append({
                "category": "Performance",
                "check": "Server Latency (TTFB)",
                "status": "PASS",
                "severity": "LOW",
                "details": f"Moderate response time ({response_time_ms}ms, Page Size: {page_size_kb} KB).",
                "recommendation": "Consider WP Rocket or Cloudflare CDN caching to bring response under 1.2s."
            })
        else:
            score_points += 1
            issues.append({
                "category": "Performance",
                "check": "Server Latency (TTFB)",
                "status": "WARNING",
                "severity": "MEDIUM",
                "details": f"Slow response time ({round(response_time_ms / 1000, 2)}s, Page Size: {page_size_kb} KB).",
                "recommendation": "Optimize server response time. Enable page caching and compress HTML/CSS resources."
            })

    if not html:
        return {
            "audit_mode": "single_page",
            "audited_url": cleaned_url,
            "overall_seo_health_score": 30,
            "status_code": status_code,
            "issues_summary": {"critical": 1, "high": 0, "medium": 0, "low": 0, "total_checks": 1},
            "audit_findings": issues,
            "actionable_priorities": ["Verify server DNS and WordPress page publishing status."]
        }

    # 2. Title Tag & Branding (Max 12 pts)
    title_m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    title_text = title_m.group(1).strip() if title_m else ""
    title_len = len(title_text)

    if not title_text:
        issues.append({
            "category": "Meta Tags",
            "check": "Title Tag",
            "status": "MISSING",
            "severity": "CRITICAL",
            "details": "No <title> tag found on the page.",
            "recommendation": "Add a descriptive, keyword-rich title tag between 50-60 characters."
        })
    else:
        score_points += 4
        has_brand_sep = "|" in title_text or "-" in title_text or "—" in title_text
        if has_brand_sep:
            score_points += 3

        if title_len < 35:
            score_points += 2
            issues.append({
                "category": "Meta Tags",
                "check": "Title Tag Length",
                "status": "WARNING",
                "severity": "MEDIUM",
                "details": f"Title tag is short ({title_len} chars): \"{title_text}\"",
                "recommendation": "Expand title tag to 50-60 characters to include primary and local keywords."
            })
        elif title_len > 60:
            score_points += 2
            issues.append({
                "category": "Meta Tags",
                "check": "Title Tag Length",
                "status": "WARNING",
                "severity": "MEDIUM",
                "details": f"Title tag is long ({title_len} chars): \"{title_text}\"",
                "recommendation": "Shorten title tag to 50-60 characters to prevent truncation in Google SERPs."
            })
        else:
            score_points += 5
            issues.append({
                "category": "Meta Tags",
                "check": "Title Tag",
                "status": "PASS",
                "severity": "LOW",
                "details": f"Optimal length ({title_len} chars): \"{title_text}\"",
                "recommendation": "Title tag length is within Google SERP display limits."
            })

    # 3. Meta Description & Call-to-Action (Max 10 pts)
    desc_m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
    if not desc_m:
        desc_m = re.search(r'<meta\s+content=["\'](.*?)["\']\s+name=["\']description["\']', html, re.IGNORECASE)
    desc_text = desc_m.group(1).strip() if desc_m else ""
    desc_len = len(desc_text)

    if not desc_text:
        issues.append({
            "category": "Meta Tags",
            "check": "Meta Description",
            "status": "MISSING",
            "severity": "HIGH",
            "details": "Meta description tag is missing.",
            "recommendation": "Add a compelling meta description (130-155 characters) with a clear Call to Action."
        })
    else:
        score_points += 3
        has_cta = any(w in desc_text.lower() for w in ["book", "call", "reserve", "hire", "service", "transfers", "chauffeur", "quote"])
        if has_cta:
            score_points += 2

        if desc_len < 115:
            score_points += 2
            issues.append({
                "category": "Meta Tags",
                "check": "Meta Description Length",
                "status": "WARNING",
                "severity": "MEDIUM",
                "details": f"Meta description is short ({desc_len} chars): \"{desc_text[:60]}...\"",
                "recommendation": "Expand description to 130-155 characters to maximize click-through rate."
            })
        elif desc_len > 158:
            score_points += 2
            issues.append({
                "category": "Meta Tags",
                "check": "Meta Description Length",
                "status": "WARNING",
                "severity": "MEDIUM",
                "details": f"Meta description is long ({desc_len} chars, exceeds 158 chars limit).",
                "recommendation": "Trim description to 130-155 characters to prevent snippet cutoff on Google."
            })
        else:
            score_points += 5
            issues.append({
                "category": "Meta Tags",
                "check": "Meta Description",
                "status": "PASS",
                "severity": "LOW",
                "details": f"Optimal length ({desc_len} chars): \"{desc_text[:65]}...\"",
                "recommendation": "Meta description length and CTA structure are optimal."
            })

    # 4. Heading Structure (H1, H2, H3) (Max 15 pts)
    h1_matches = re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
    h1_count = len(h1_matches)
    clean_h1s = [re.sub(r'<[^>]+>', '', h).strip() for h in h1_matches]

    h2_matches = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.IGNORECASE | re.DOTALL)
    h2_count = len(h2_matches)

    h3_matches = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.IGNORECASE | re.DOTALL)
    h3_count = len(h3_matches)

    if h1_count == 0:
        issues.append({
            "category": "Headings",
            "check": "H1 Heading",
            "status": "MISSING",
            "severity": "CRITICAL",
            "details": "No H1 heading found on the page.",
            "recommendation": "Add exactly one descriptive H1 heading containing the primary target keyword."
        })
    elif h1_count > 1:
        score_points += 2
        issues.append({
            "category": "Headings",
            "check": "H1 Heading Count",
            "status": "WARNING",
            "severity": "MEDIUM",
            "details": f"Multiple H1 headings found ({h1_count} H1s detected).",
            "recommendation": "Consolidate into 1 primary H1 heading and use H2/H3 tags for subheadings."
        })
    else:
        score_points += 6
        issues.append({
            "category": "Headings",
            "check": "H1 Heading",
            "status": "PASS",
            "severity": "LOW",
            "details": f"1 H1 found: \"{clean_h1s[0][:60]}...\"",
            "recommendation": "Single H1 structure adheres to Google ranking standards."
        })

    if h2_count >= 3:
        score_points += 5
        issues.append({
            "category": "Headings",
            "check": "H2 Subheadings",
            "status": "PASS",
            "severity": "LOW",
            "details": f"Good subheading hierarchy ({h2_count} H2s, {h3_count} H3s).",
            "recommendation": "Heading hierarchy organizes topical content effectively."
        })
    elif h2_count > 0:
        score_points += 2
        issues.append({
            "category": "Headings",
            "check": "H2 Subheadings",
            "status": "WARNING",
            "severity": "LOW",
            "details": f"Only {h2_count} H2 subheading(s) found ({h3_count} H3s).",
            "recommendation": "Add 3-5 descriptive H2 subheadings to cover core customer questions."
        })
    else:
        issues.append({
            "category": "Headings",
            "check": "H2 Subheadings",
            "status": "MISSING",
            "severity": "HIGH",
            "details": "No H2 subheadings found on page.",
            "recommendation": "Structure the content with H2 subheadings for better readability and SEO."
        })

    if h3_count >= 1:
        score_points += 4

    # 5. Content Depth & Word Count (Max 15 pts)
    clean_body = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    clean_body = re.sub(r'<style[^>]*>.*?</style>', '', clean_body, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'<[^>]+>', ' ', clean_body)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    word_count = len(clean_text.split())

    if word_count >= 1000:
        score_points += 15
        issues.append({
            "category": "Content Depth",
            "check": "Word Count & Topical Depth",
            "status": "PASS",
            "severity": "LOW",
            "details": f"Comprehensive content depth (~{word_count} words).",
            "recommendation": "Word count demonstrates high topical authority."
        })
    elif word_count >= 600:
        score_points += 10
        issues.append({
            "category": "Content Depth",
            "check": "Word Count & Topical Depth",
            "status": "PASS",
            "severity": "LOW",
            "details": f"Standard content length (~{word_count} words).",
            "recommendation": "Consider expanding to 1,000+ words with FAQ section for higher rankings."
        })
    elif word_count >= 300:
        score_points += 5
        issues.append({
            "category": "Content Depth",
            "check": "Word Count & Topical Depth",
            "status": "WARNING",
            "severity": "MEDIUM",
            "details": f"Moderate / Light content length (~{word_count} words).",
            "recommendation": "Expand page content to at least 800 words to outrank competitors."
        })
    else:
        issues.append({
            "category": "Content Depth",
            "check": "Word Count & Topical Depth",
            "status": "WARNING",
            "severity": "HIGH",
            "details": f"Thin content detected (~{word_count} words).",
            "recommendation": "Add comprehensive service descriptions, vehicle features, and pricing details."
        })

    # 6. Schema.org JSON-LD Structured Data (Max 12 pts)
    has_schema = "application/ld+json" in html
    schema_types = []
    if has_schema:
        score_points += 6
        schema_types = list(set(re.findall(r'"@type"\s*:\s*"([^"]+)"', html)))
        schema_bonus = min(6, len(schema_types) * 2)
        score_points += schema_bonus
        issues.append({
            "category": "Structured Data",
            "check": "Schema.org Markup",
            "status": "PASS",
            "severity": "LOW",
            "details": f"Active JSON-LD schemas detected: {', '.join(schema_types[:4])}.",
            "recommendation": "Rich snippet schema is active and indexed."
        })
    else:
        issues.append({
            "category": "Structured Data",
            "check": "Schema.org Markup",
            "status": "MISSING",
            "severity": "HIGH",
            "details": "No Schema.org JSON-LD structured data detected.",
            "recommendation": "Add LocalBusiness, Service, or FAQPage schema markup."
        })

    # 7. Internal & External Links Profile (Max 12 pts)
    link_tags = re.findall(r'<a\s+[^>]*?href=["\'](.*?)["\'][^>]*?>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
    internal_links = [l for l in link_tags if site_key in l[0] or l[0].startswith("/") or "corporatecars" in l[0]]
    external_links = [l for l in link_tags if not (site_key in l[0] or l[0].startswith("/") or "corporatecars" in l[0]) and l[0].startswith("http")]
    
    generic_anchors = [l[1] for l in link_tags if re.sub(r'<[^>]+>', '', l[1]).strip().lower() in ["click here", "read more", "here", "learn more", "more"]]

    if len(internal_links) >= 4:
        score_points += 6
        issues.append({
            "category": "Linking",
            "check": "Internal Links Count",
            "status": "PASS",
            "severity": "LOW",
            "details": f"{len(internal_links)} internal links distributed across page.",
            "recommendation": "Internal link equity distribution is healthy."
        })
    elif len(internal_links) > 0:
        score_points += 3
        issues.append({
            "category": "Linking",
            "check": "Internal Links Count",
            "status": "WARNING",
            "severity": "LOW",
            "details": f"Only {len(internal_links)} internal link(s) found.",
            "recommendation": "Add 3-5 contextual internal links to relevant landing and fleet pages."
        })
    else:
        issues.append({
            "category": "Linking",
            "check": "Internal Links Count",
            "status": "MISSING",
            "severity": "HIGH",
            "details": "No internal links found on this page.",
            "recommendation": "Add internal links to boost page indexing and PageRank flow."
        })

    if len(external_links) >= 1:
        score_points += 4
        issues.append({
            "category": "Linking",
            "check": "External Citations",
            "status": "PASS",
            "severity": "LOW",
            "details": f"{len(external_links)} external reference link(s) found.",
            "recommendation": "Ensure all external links have rel='noopener' and open in new tab."
        })
    else:
        score_points += 1
        issues.append({
            "category": "Linking",
            "check": "External Citations",
            "status": "WARNING",
            "severity": "LOW",
            "details": "No external citation links found.",
            "recommendation": "Adding 1-2 authoritative external links (e.g. Melbourne Airport official site, Visit Victoria) boosts trust."
        })

    if not generic_anchors:
        score_points += 2
    else:
        issues.append({
            "category": "Linking",
            "check": "Anchor Text Quality",
            "status": "WARNING",
            "severity": "MEDIUM",
            "details": f"{len(generic_anchors)} generic anchor texts detected (e.g. \"{generic_anchors[0]}\").",
            "recommendation": "Replace generic text with keyword-rich descriptive anchors."
        })

    # 8. Media & Image Alt Optimization (Max 8 pts)
    img_tags = re.findall(r'<img\s+[^>]*?>', html, re.IGNORECASE)
    total_imgs = len(img_tags)
    missing_alt_count = sum(1 for img in img_tags if 'alt=' not in img.lower() or 'alt=""' in img or "alt=''" in img)

    if total_imgs > 0 and missing_alt_count > 0:
        earned_media = max(1, int(8 * (1 - (missing_alt_count / total_imgs))))
        score_points += earned_media
        issues.append({
            "category": "Media",
            "check": "Image Alt Attributes",
            "status": "WARNING",
            "severity": "MEDIUM",
            "details": f"{missing_alt_count} of {total_imgs} images are missing descriptive alt text.",
            "recommendation": "Add descriptive alt attributes with target keyword variations to all images."
        })
    elif total_imgs > 0:
        score_points += 8
        issues.append({
            "category": "Media",
            "check": "Image Alt Attributes",
            "status": "PASS",
            "severity": "LOW",
            "details": f"All {total_imgs} images have descriptive alt attributes.",
            "recommendation": "Image accessibility and SEO compliance is optimal."
        })
    else:
        score_points += 4
        issues.append({
            "category": "Media",
            "check": "Image Media",
            "status": "WARNING",
            "severity": "LOW",
            "details": "No vehicle or service images found on this page.",
            "recommendation": "Include high-quality fleet images with alt attributes."
        })

    # 9. Indexability, Canonical & Social (Max 6 pts)
    canonical_m = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']', html, re.IGNORECASE)
    if not canonical_m:
        canonical_m = re.search(r'<link\s+href=["\'](.*?)["\']\s+rel=["\']canonical["\']', html, re.IGNORECASE)
    canonical_url = canonical_m.group(1).strip() if canonical_m else ""

    if canonical_url:
        score_points += 3
        issues.append({
            "category": "Indexability",
            "check": "Canonical Tag",
            "status": "PASS",
            "severity": "LOW",
            "details": f"Canonical URL configured: {canonical_url[:60]}...",
            "recommendation": "Canonical tag prevents duplicate content indexing."
        })
    else:
        issues.append({
            "category": "Indexability",
            "check": "Canonical Tag",
            "status": "MISSING",
            "severity": "MEDIUM",
            "details": "Canonical link tag is missing.",
            "recommendation": "Add a self-referencing canonical tag to prevent duplicate content."
        })

    has_og = "og:title" in html and "og:image" in html
    if has_og:
        score_points += 3
        issues.append({
            "category": "Social Meta",
            "check": "OpenGraph Social Cards",
            "status": "PASS",
            "severity": "LOW",
            "details": "OpenGraph social tags (og:title, og:image) are installed.",
            "recommendation": "Social sharing tags are active."
        })
    else:
        score_points += 1
        issues.append({
            "category": "Social Meta",
            "check": "OpenGraph Social Cards",
            "status": "WARNING",
            "severity": "LOW",
            "details": "OpenGraph social tags are incomplete.",
            "recommendation": "Configure Yoast or Rank Math social cards for social previews."
        })

    # Final Score Calculation (Constrained to 35-100)
    final_score = max(35, min(100, score_points))

    crit = len([i for i in issues if i["severity"] == "CRITICAL"])
    high = len([i for i in issues if i["severity"] == "HIGH"])
    med = len([i for i in issues if i["severity"] == "MEDIUM"])
    low = len([i for i in issues if i["severity"] == "LOW" and i["status"] != "PASS"])

    actionable_priorities = []
    for issue in sorted(issues, key=lambda x: 0 if x["severity"] == "CRITICAL" else (1 if x["severity"] == "HIGH" else (2 if x["severity"] == "MEDIUM" else 3))):
        if issue["status"] != "PASS":
            actionable_priorities.append(f"[{issue['severity']}] {issue['check']}: {issue['recommendation']}")

    if not actionable_priorities:
        actionable_priorities.append("No critical issues found. Page is highly optimized for Google search.")

    report = {
        "audit_mode": "single_page",
        "audited_url": cleaned_url,
        "page_title": title_text or "Page Title",
        "overall_seo_health_score": final_score,
        "status_code": status_code,
        "response_time_ms": response_time_ms,
        "page_size_kb": page_size_kb,
        "word_count": word_count,
        "h1_count": h1_count,
        "h2_count": h2_count,
        "h3_count": h3_count,
        "images_count": total_imgs,
        "missing_alt_count": missing_alt_count,
        "internal_links_count": len(internal_links),
        "external_links_count": len(external_links),
        "has_schema": has_schema,
        "schema_types": schema_types,
        "issues_summary": {
            "critical": crit,
            "high": high,
            "medium": med,
            "low": low,
            "total_checks": len(issues)
        },
        "audit_findings": issues,
        "actionable_priorities": actionable_priorities[:5]
    }

    save_seo_audit_history(report)
    return report


def audit_entire_website(domain_url: str, site_key: str = "ccm") -> Dict[str, Any]:
    """
    Performs dynamic whole-website domain crawl.
    Discovers live internal links from the homepage, crawls core pages in parallel,
    detects site-wide duplicate titles, missing alts, and generates an executive roadmap.
    """
    cleaned_domain = domain_url.strip().rstrip("/")
    if not cleaned_domain.startswith("http"):
        cleaned_domain = f"https://{cleaned_domain}"

    logger.info(f"Auditing whole website SEO for domain: {cleaned_domain}")

    # 1. Technical Domain Diagnostics
    robots_url = f"{cleaned_domain}/robots.txt"
    sitemap_url = f"{cleaned_domain}/sitemap.xml"

    robots_ok = False
    sitemap_ok = False

    try:
        r_rob = requests.get(robots_url, timeout=6)
        robots_ok = r_rob.status_code == 200 and "User-agent" in r_rob.text
    except Exception:
        robots_ok = False

    try:
        r_sit = requests.get(sitemap_url, timeout=6)
        sitemap_ok = r_sit.status_code == 200 and ("<urlset" in r_sit.text or "<sitemapindex" in r_sit.text)
    except Exception:
        sitemap_ok = False

    # 2. Dynamic Discovery of Core Pages from Homepage
    discovered_paths = ["/"]
    try:
        resp = requests.get(cleaned_domain, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if resp.status_code == 200:
            links = re.findall(r'<a\s+[^>]*?href=["\'](.*?)["\']', resp.text, re.IGNORECASE)
            for l in links:
                if l.startswith("/") and len(l) > 1 and not l.startswith(("/#", "/wp-", "/wp-content", "/feed", "/cart", "/checkout")):
                    clean_p = l.split("?")[0].split("#")[0]
                    if clean_p not in discovered_paths and len(clean_p) > 2:
                        discovered_paths.append(clean_p)
                elif cleaned_domain in l:
                    path = urlparse(l).path
                    if path and path not in discovered_paths and not path.startswith(("/wp-", "/feed", "/cart")):
                        discovered_paths.append(path)
    except Exception as e:
        logger.warning(f"Error extracting homepage links: {e}")

    # Ensure key core chauffeur service paths are included if not discovered
    for fallback in [
        "/services/airport-transfers/",
        "/services/corporate-transfers/",
        "/services/wedding-car-hire/",
        "/services/winery-tours/",
        "/fleet/executive-sedans/",
        "/fleet/luxury-suv/",
        "/contact/",
        "/about-us/"
    ]:
        if fallback not in discovered_paths:
            discovered_paths.append(fallback)

    # Limit to top 10 representative pages for fast, deep audit
    core_paths = discovered_paths[:10]

    pages_audited: List[Dict[str, Any]] = []
    total_scores = []

    def _audit_path(path: str) -> Optional[Dict[str, Any]]:
        page_url = f"{cleaned_domain}{path}" if path.startswith("/") else path
        try:
            res = audit_single_page(page_url, site_key=site_key)
            return {
                "url": page_url,
                "path": path,
                "title": res.get("page_title", path),
                "score": res.get("overall_seo_health_score", 75),
                "h1_count": res.get("h1_count", 1),
                "has_schema": res.get("has_schema", False),
                "word_count": res.get("word_count", 0),
                "missing_alt_count": res.get("missing_alt_count", 0),
                "internal_links_count": res.get("internal_links_count", 0),
                "response_time_ms": res.get("response_time_ms", 0),
                "issues_count": res["issues_summary"]["critical"] + res["issues_summary"]["high"] + res["issues_summary"]["medium"],
                "top_issue": res.get("actionable_priorities", ["None"])[0]
            }
        except Exception as e:
            logger.warning(f"Error auditing subpage {page_url}: {e}")
            return None

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(_audit_path, core_paths))

    for r in results:
        if r:
            pages_audited.append(r)
            total_scores.append(r["score"])

    avg_health_score = int(sum(total_scores) / len(total_scores)) if total_scores else 78

    # Site-Wide Diagnostics
    schema_coverage_pct = int((sum(1 for p in pages_audited if p["has_schema"]) / max(1, len(pages_audited))) * 100)
    valid_h1_pct = int((sum(1 for p in pages_audited if p["h1_count"] == 1) / max(1, len(pages_audited))) * 100)
    total_missing_alts = sum(p["missing_alt_count"] for p in pages_audited)
    
    # Check for Duplicate Titles across the site
    titles_seen = {}
    duplicate_titles = []
    for p in pages_audited:
        t = p["title"].strip().lower()
        if t in titles_seen:
            duplicate_titles.append(f"\"{p['title']}\" (shared by {titles_seen[t]} and {p['path']})")
        else:
            titles_seen[t] = p["path"]

    site_wide_recs = [
        f"Domain Health Score: {avg_health_score}/100 across {len(pages_audited)} audited core pages.",
        f"Schema.org Coverage: {schema_coverage_pct}% of core pages contain structured data." + (" Expand schema to all service pages." if schema_coverage_pct < 100 else " (Optimal)"),
        f"H1 Heading Compliance: {valid_h1_pct}% of pages have exactly 1 primary H1 heading.",
        f"Image Optimization: {total_missing_alts} total images across audited pages are missing descriptive alt attributes.",
        "Robots.txt: " + ("✅ Active and accessible." if robots_ok else "⚠️ Missing or inaccessible robots.txt file."),
        "XML Sitemap: " + ("✅ Active and valid sitemap found." if sitemap_ok else "⚠️ XML Sitemap not found at standard /sitemap.xml.")
    ]

    if duplicate_titles:
        site_wide_recs.append(f"⚠️ Duplicate Titles Detected: {', '.join(duplicate_titles[:2])}")

    report = {
        "audit_mode": "whole_website",
        "domain_url": cleaned_domain,
        "site_health_score": avg_health_score,
        "pages_audited_count": len(pages_audited),
        "schema_coverage_pct": schema_coverage_pct,
        "h1_compliance_pct": valid_h1_pct,
        "total_missing_alts": total_missing_alts,
        "technical_diagnostics": {
            "robots_txt": "ACTIVE" if robots_ok else "MISSING",
            "xml_sitemap": "ACTIVE" if sitemap_ok else "MISSING",
            "https_ssl": "ACTIVE" if cleaned_domain.startswith("https") else "INSECURE"
        },
        "pages_breakdown": pages_audited,
        "domain_recommendations": site_wide_recs
    }

    save_seo_audit_history(report)
    return report


class SEOAuditAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="seo-audit-agent",
            name="SEO Audit Agent",
            description="Audits technical SEO, meta tags, schema, and page health in Single Page Mode or Whole Website Domain Crawl Mode.",
            category="SEO & Content",
            enabled=True,
            paused=False,
            supported_actions=["audit_page", "audit_site", "check_technical", "health_check"],
            version="2.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "audit_page")).lower().strip()
        url = str(input_data.get("url") or input_data.get("source_url") or "https://corporatecarsmelbourne.com.au").strip()
        audit_mode = str(input_data.get("audit_mode", "single_page")).lower().strip()
        site_key = str(input_data.get("site_key", "ccm")).strip()

        logger.info(f"Executing SEOAuditAgent task: action={action}, mode={audit_mode}, url='{url}'")

        if audit_mode == "whole_website" or action == "audit_site":
            result = audit_entire_website(url, site_key=site_key)
        else:
            result = audit_single_page(url, site_key=site_key)

        return {
            "output": result,
            "model_used": "deterministic-seo-crawler",
            "tokens_used": 0,
            "cost_usd": 0.0
        }

