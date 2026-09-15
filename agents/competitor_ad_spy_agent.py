"""
Agent: Competitor Ad Spy & Intelligence Agent (`competitor-ad-spy-agent`).

Competitor ad creatives, keywords and budgets cannot be read programmatically,
and this agent no longer pretends otherwise.

  * Google's Ads Transparency Center has no public API. The page is a
    JavaScript application; there is nothing to query.
  * Meta's Ad Library API (`ads_archive`) returns only political and
    social-issue ads outside the EU. An Australian chauffeur company's ads are
    not in it.

So this agent does three things it can actually do: it measures the
competitor's live landing page, it hands over the two official links where a
person can look the ads up themselves, and it reports what the operator's own
Google Ads account pays for the keywords in question -- real CPCs from their
own spend, rather than guesses at somebody else's.

What stood here before made no HTTP request at all. Not one. It nonetheless
reported `data_source` as "Google Ads Transparency Center (AU) & Live SERP
Query" and "Meta Ad Library (Facebook & Instagram Australia Public Database)",
and `model_used` as "live-transparency-crawler+ai-router". Everything in the
report was written into the source file:

  * Two Google ads and two Meta ads per competitor, with headlines, body copy,
    sitelinks, callouts and ad ids generated from `hash(domain) % 1000` -- and
    "started_running": "Active (Running 45+ days)", a factual claim about
    another company's campaign.
  * "estimated_monthly_ad_spend": "$3,200 - $5,500 AUD" and four active
    creatives.
  * Six keywords with CPCs to the cent ($7.20, $8.10) and monthly search
    volumes (2,400/mo), none of which came from any keyword tool.
  * A list of the competitor's "vulnerabilities", describing ads nobody read.

With `use_ai` on -- and it defaulted to on -- the prompt asked the model to
"provide 2 realistic, high-converting Google Search Ads ... they run". An
invented answer to that question is not intelligence about a competitor; it is
a language model writing plausible advertising and the report calling it
observed fact.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

from agents.base import AgentInterface
from config.settings import LOGS_DIR
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("competitor-ad-spy-agent")

HISTORY_FILE = LOGS_DIR / "competitor_ad_spy_history.json"


def load_ad_spy_history() -> List[Dict[str, Any]]:
    """Loads historical competitor ad intelligence reports."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read competitor ad spy history: {e}")
    return []


def save_ad_spy_history(reports: List[Dict[str, Any]]) -> None:
    """Saves competitor ad intelligence reports to disk."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(reports, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save competitor ad spy history: {e}")


def verification_links(domain: str) -> Dict[str, Any]:
    """Where a person can actually see these ads. These links are the honest
    deliverable: they work, and they lead to the real thing."""
    return {
        "meta_ad_library": (
            "https://www.facebook.com/ads/library/?active_status=all&ad_type=all"
            f"&country=AU&q={quote(domain)}&search_type=keyword_unordered&media_type=all"
        ),
        "google_ads_transparency": f"https://adstransparency.google.com/?region=AU&domain={quote(domain)}",
        "note": (
            "Open these to see the competitor's live ads. Neither platform offers an API "
            "that returns them: Google's Transparency Center has none, and Meta's Ad "
            "Library API covers only political and social-issue ads outside the EU. "
            "Nothing on this page claims to have read their ads."
        ),
    }


def measure_competitor_landing_page(url: str, keyword: str) -> Dict[str, Any]:
    """Fetch and measure the page the competitor's ads point at.

    This is the one part of a competitor's advertising that is genuinely
    observable: where the money lands.
    """
    from agents.competitor_agent import fetch_page, measure_page

    fetched = fetch_page(url)
    if not fetched.get("reachable"):
        return {
            "measured": False,
            "url": url,
            "status_code": fetched.get("status_code"),
            "error": fetched.get("error") or "The page could not be fetched.",
        }

    measured = measure_page(fetched["html"], fetched.get("final_url") or url, keyword)
    return {
        "measured": True,
        "url": fetched.get("final_url") or url,
        "status_code": fetched.get("status_code"),
        "response_seconds": fetched.get("response_seconds"),
        "page_bytes": fetched.get("page_bytes"),
        **measured,
    }


def own_keyword_costs(router: ModelRouter, site_id: str) -> Dict[str, Any]:
    """What this account actually pays, from its own Google Ads data.

    The block this replaces listed six keywords with CPCs to the cent and
    monthly search volumes, presented as the competitor's bidding. Those were
    literals. An operator's own account is the one place where a real cost per
    click for these terms exists.
    """
    from agents.google_ads_optimization_agent import GoogleAdsOptimizationAgent
    from integrations.ads.google_ads_client import account_belongs_to_site

    # Credentials fall back to environment variables, so a site with no Google
    # Ads account of its own resolves to whichever account the server holds.
    # Without this check, the second site's panel showed the first site's
    # keyword costs as its own.
    account = account_belongs_to_site(site_id)
    if not account["owns_account"]:
        return {
            "measured": False,
            "error": (
                f"This site has no Google Ads account of its own (it declares "
                f"{account['declared']!r}). The credentials on this server belong to account "
                f"{account['resolved'] or 'none'}, so showing those costs here would report "
                f"another business's spend as this one's."
            ),
            "keywords": [],
        }

    try:
        task = AgentTask(
            task_id="adspy-own-costs",
            agent_id="google-ads-optimization-agent",
            task_type="recommend_optimizations",
            input_data={"action": "recommend_optimizations", "site_id": site_id},
            site_id=site_id,
        )
        out = GoogleAdsOptimizationAgent().run_task(task, router).get("output", {})
    except Exception as e:
        logger.warning(f"Could not read own Google Ads costs: {e}")
        return {"measured": False, "error": str(e), "keywords": []}

    if out.get("data_source") != "LIVE (Google Ads API)":
        return {
            "measured": False,
            "error": out.get("live_error") or "No Google Ads account is connected for this site.",
            "keywords": [],
        }

    keywords = []
    for bucket in ("winning_keywords", "wasteful_keywords"):
        for k in out.get(bucket) or []:
            keywords.append({
                "keyword": k.get("keyword"),
                "match_type": k.get("match_type"),
                "clicks": k.get("clicks"),
                "spend": k.get("spend"),
                "avg_cpc": k.get("avg_cpc"),
                "conversions": k.get("conversions"),
                "converting": bucket == "winning_keywords",
            })

    return {
        "measured": True,
        "source": "your own Google Ads account (last 30 days)",
        "account_id": out.get("account_id"),
        "keywords": keywords[:15],
        "note": (
            "These are the costs your account actually paid. What the competitor pays is "
            "not published by either platform."
        ),
    }


class CompetitorAdSpyAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="competitor-ad-spy-agent",
            name="Competitor Ad Spy & Intelligence Agent",
            description="Measures a competitor's live landing page, links to the official ad libraries, and reports your own real keyword costs.",
            category="Competitor & Ad Intelligence",
            enabled=True,
            paused=False,
            supported_actions=["spy_competitor_ads", "analyze_landing_page", "generate_counter_ads"],
            version="2.0.0",
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "spy_competitor_ads")).lower().strip()
        raw_url = str(input_data.get("competitor_url", "")).strip()
        site_id = input_data.get("site_id") or input_data.get("site") or "ccm"
        keyword = str(input_data.get("target_keyword", "chauffeur melbourne")).strip()
        # This defaulted to True, so every run spent tokens writing fiction.
        use_ai = bool(input_data.get("use_ai", False))

        if not raw_url:
            return {
                "output": {
                    "action": action,
                    "error": "No competitor URL was given, so nothing was measured.",
                    "measured_landing_page": {"measured": False},
                },
                "model_used": "none", "tokens_used": 0, "cost_usd": 0.0,
            }

        parsed = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}")
        clean_domain = (parsed.netloc or parsed.path).replace("www.", "")
        page_url = parsed.geturl()

        from config.websites import WebsiteManager

        profile = WebsiteManager().get(site_id)
        target_brand = profile.name if profile else site_id
        target_domain = profile.domain if profile else ""
        target_loc = profile.location if profile else "Melbourne, VIC"

        logger.info(
            f"Executing CompetitorAdSpyAgent: action={action}, competitor='{clean_domain}', "
            f"site='{site_id}', use_ai={use_ai}"
        )

        landing = measure_competitor_landing_page(page_url, keyword)
        costs = own_keyword_costs(router, site_id)

        report: Dict[str, Any] = {
            "action": action,
            "competitor_domain": clean_domain,
            "competitor_url": page_url,
            "target_brand": target_brand,
            "target_domain": target_domain,
            "location": target_loc,
            "analyzed_at": datetime.now().isoformat(),
            # Named for what it is. There is no crawler behind either ad platform.
            "data_source": "competitor landing page (fetched) + your own Google Ads account",
            "competitor_ads_readable": False,
            "competitor_ads_note": (
                "Their ad creatives, keywords and spend are not readable through any API. "
                "Nothing here is an estimate of what they run or what they pay."
            ),
            "verification_links": verification_links(clean_domain),
            "measured_landing_page": landing,
            "your_keyword_costs": costs,
        }

        tokens_used, cost_usd = 0, 0.0
        model_used = "landing-page-measurement"

        if use_ai and landing.get("measured"):
            try:
                winners = [k["keyword"] for k in costs.get("keywords", []) if k.get("converting")]
                response = router.route_and_execute(LLMRequest(
                    user_prompt=(
                        f"Write draft Google Search ad copy for {target_brand} ({target_domain}).\n"
                        f"These keywords converted on their own account: "
                        f"{', '.join(winners) or 'none recorded'}.\n"
                        f"A competitor's landing page at {clean_domain} has this title: "
                        f"{landing.get('page_title', '')!r}, H1: {landing.get('h1_text', '')!r}, "
                        f"{landing.get('word_count', 0)} words.\n\n"
                        f"Rules: do NOT invent prices, guarantees, response times, fleet models, "
                        f"awards or accreditations. Do NOT describe what the competitor advertises "
                        f"-- their ads have not been read. Write only claims a chauffeur business "
                        f"could make about itself without evidence. "
                        f"Return JSON with 'headlines' (max 30 chars each) and 'descriptions' "
                        f"(max 90 chars each)."
                    ),
                    task_type=TaskComplexity.STANDARD,
                    json_output=True,
                ))
                model_used = response.model_used
                tokens_used = response.tokens_in + response.tokens_out
                cost_usd = response.cost_usd
                if response.parsed_json:
                    # Labelled as a draft for the operator's own ads, which is
                    # what it is. The old counter-strategy asserted the
                    # competitor's weaknesses and proposed copy promising
                    # "Fixed Rates From $95" and a "100% On-Time Guarantee" --
                    # commitments this business may not offer, in a market where
                    # advertising them without basis is a consumer-law problem.
                    report["draft_ad_copy"] = response.parsed_json
                    report["draft_ad_copy_note"] = (
                        f"Draft copy for your own ads, written by {model_used}. It is not based on "
                        f"the competitor's ads, which were not read. Check every claim before "
                        f"publishing it."
                    )
            except Exception as e:
                logger.warning(f"Draft ad copy generation failed: {e}")
                report["draft_ad_copy_error"] = str(e)

        history = load_ad_spy_history()
        history.insert(0, {
            "report_id": f"adspy-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "competitor_domain": clean_domain,
            "analyzed_at": report["analyzed_at"],
            "landing_page_measured": bool(landing.get("measured")),
            "data": report,
        })
        save_ad_spy_history(history[:50])

        return {
            "output": report,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        }
