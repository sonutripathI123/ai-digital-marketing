"""
Agent #10: Google Ads Optimization Agent (`google-ads-optimization-agent`).

Generates actionable recommendations for Google Ads campaigns (negative keywords, bid adjustments,
budget re-allocations, ad copy improvements). Requires human approval for execution.
Enforces ADS_LIVE_EXECUTION_ENABLED=false safety guard.
"""

from typing import Any, Dict, List
from agents.base import AgentInterface
from config.settings import ADS_LIVE_EXECUTION_ENABLED
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata
from integrations.ads.google_ads_client import GoogleAdsLiveClient

logger = get_agent_logger("google-ads-optimization-agent")


def _fetch_live_optimization(credentials, site_id, date_range):
    """Pull live keyword + search-term data. Returns (data_or_None, live_status)."""
    client = GoogleAdsLiveClient(credentials=credentials, site_id=site_id)
    status = client.status()
    if not client.is_configured():
        return None, status
    try:
        keywords = client.get_keyword_performance(date_range)
        search_terms = client.get_search_terms(date_range)
        return {"keywords": keywords, "search_terms": search_terms}, \
            {**status, "code": "LIVE", "reason": "Live data fetched from Google Ads API."}
    except Exception as e:
        logger.warning(f"Live Google Ads optimization fetch failed, using benchmark: {e}")
        return None, {**status, "code": "API_ERROR", "ready": False, "reason": f"Live fetch failed: {e}"}


def _build_live_optimization(action, account_id, goal, data, live_status):
    """Derive winners, wasteful keywords, and new-keyword ideas from live data."""
    kws = data["keywords"]
    terms = data["search_terms"]

    winners = sorted(
        [k for k in kws if k["conversions"] > 0],
        key=lambda k: (k["conversions"], k["clicks"]), reverse=True,
    )[:10]

    # Wasteful = meaningful clicks and spend but zero conversions -> pause/negative.
    wasteful = sorted(
        [k for k in kws if k["conversions"] == 0 and (k["clicks"] >= 10 or k["spend"] >= 20)],
        key=lambda k: k["spend"], reverse=True,
    )[:10]

    existing_terms = {k["keyword"].lower() for k in kws}
    # New keyword ideas: search terms that converted or drew strong CTR, not yet keywords.
    new_keyword_ideas = sorted(
        [t for t in terms
         if t["search_term"].lower() not in existing_terms
         and (t["conversions"] > 0 or (t["clicks"] >= 5 and t["ctr_percent"] >= 5))],
        key=lambda t: (t["conversions"], t["clicks"]), reverse=True,
    )[:15]

    # Negative keyword candidates: spend, zero conversions, weak CTR.
    negative_candidates = sorted(
        [t for t in terms if t["conversions"] == 0 and t["spend"] >= 10],
        key=lambda t: t["spend"], reverse=True,
    )[:15]

    est_waste = round(sum(k["spend"] for k in wasteful) + sum(t["spend"] for t in negative_candidates), 2)

    # Campaigns and ad groups are read off the rows themselves rather than
    # named in advance, so the report can never quote a campaign the account
    # does not have.
    campaigns = sorted({k["campaign"] for k in kws if k.get("campaign")})
    ad_groups = sorted({k["ad_group"] for k in kws if k.get("ad_group")})
    spend_total = round(sum(k["spend"] for k in kws), 2)
    clicks_total = sum(k["clicks"] for k in kws)
    conv_total = round(sum(k["conversions"] for k in kws), 1)

    return {
        "action": action,
        "account_id": account_id,
        "optimization_goal": goal,
        "data_source": "LIVE (Google Ads API)",
        "campaigns": campaigns,
        "ad_groups": ad_groups,
        "keywords_analysed": len(kws),
        "search_terms_analysed": len(terms),
        "account_totals": {
            "spend": spend_total,
            "clicks": clicks_total,
            "conversions": conv_total,
            "cpa": round(spend_total / conv_total, 2) if conv_total else None,
        },
        "live_status": live_status,
        "approval_status": "RECOMMENDED (based on live data)",
        "winning_keywords": winners,
        "wasteful_keywords": wasteful,
        "recommended_new_keywords": [
            {"keyword": t["search_term"], "clicks": t["clicks"], "conversions": t["conversions"],
             "ctr_percent": t["ctr_percent"]}
            for t in new_keyword_ideas
        ],
        "recommended_negative_keywords": [t["search_term"] for t in negative_candidates],
        "estimated_monthly_savings": est_waste,
        "estimated_monthly_savings_usd": est_waste,
        "actionable_next_steps": [
            f"Scale the {len(winners)} winning keywords (highest conversions) with higher bids/budget.",
            f"Pause or reduce bids on {len(wasteful)} wasteful keywords (clicks but 0 conversions).",
            f"Add {len(new_keyword_ideas)} converting search terms as new exact/phrase keywords.",
            f"Add {len(negative_candidates)} negative keywords to stop ~{est_waste} wasted spend.",
        ],
    }


class GoogleAdsOptimizationAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="google-ads-optimization-agent",
            name="Google Ads Optimization Agent",
            description="Generates strategic Google Ads optimization recommendations (negative keywords, bids, budgets) requiring approval.",
            category="Paid Advertising",
            enabled=True,
            paused=False,
            supported_actions=["recommend_optimizations", "negative_keywords", "bid_adjustments", "budget_allocation"],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "recommend_optimizations")).lower().strip()
        account_id = str(input_data.get("account_id", "123-456-7890")).strip()
        optimization_goal = str(input_data.get("optimization_goal", "reduce_cpa")).strip()
        use_ai = bool(input_data.get("use_ai", False))

        logger.info(f"Executing GoogleAdsOptimizationAgent task: action={action}, goal='{optimization_goal}', live_enabled={ADS_LIVE_EXECUTION_ENABLED}")

        # ---- Attempt REAL live optimization from the Google Ads API first ----
        credentials = input_data.get("credentials") or {}
        site_id = input_data.get("site_id")
        date_range = str(input_data.get("date_range", "last_30_days")).strip()
        live_data, live_status = _fetch_live_optimization(credentials, site_id, date_range)
        if live_data is not None:
            live_payload = _build_live_optimization(action, account_id, optimization_goal,
                                                    live_data, live_status)
            tokens_used = 0
            cost_usd = 0.0
            model_used = "live-google-ads-api"
            if use_ai:
                try:
                    winners = ", ".join(k["keyword"] for k in live_payload["winning_keywords"][:8]) or "n/a"
                    llm_req = LLMRequest(
                        user_prompt=(
                            f"Based on these LIVE winning Google Ads keywords: {winners}. "
                            f"Goal: {optimization_goal}. Write a high-converting Responsive Search Ad: "
                            f"15 headlines (<=30 chars each), 4 descriptions (<=90 chars each), "
                            f"3 sitelinks and 4 callouts. Follow 2026 Google Ads RSA best practices. "
                            f"Return JSON with keys headlines, descriptions, sitelinks, callouts."
                        ),
                        task_type=TaskComplexity.STANDARD,
                        json_output=True,
                    )
                    response = router.route_and_execute(llm_req)
                    model_used = response.model_used
                    tokens_used = response.tokens_in + response.tokens_out
                    cost_usd = response.cost_usd
                    live_payload["generated_ad_copy"] = response.parsed_json or response.content
                except Exception as e:
                    logger.warning(f"AI ad-copy generation on live data failed: {e}")
            return {"output": live_payload, "model_used": model_used,
                    "tokens_used": tokens_used, "cost_usd": cost_usd}

        # ---- No live data: say so, and recommend nothing ----
        # What stood here was 110 lines of invented specifics -- a named
        # "winner" ad group with 191 clicks and an A$110.68 CPA, a A$95 airport
        # flat rate this business does not charge, a +61 400 000 000 phone
        # number, A$185/month of savings and a 34.5% conversion lift -- all
        # under a key called `live_campaign_analysis`. A disclaimer elsewhere in
        # the payload does not undo a field that calls itself live, and a
        # recommendation derived from figures nobody measured is worse than no
        # recommendation at all. If the API did not answer, the honest output
        # is empty lists and the reason why.
        reason = live_status.get("reason") or "Google Ads API did not return data."
        result_payload = {
            "action": action,
            "account_id": account_id,
            "optimization_goal": optimization_goal,
            "data_source": "NOT CONNECTED — no Google Ads data",
            "live_status": live_status,
            "live_error": reason,
            "approval_status": "NOTHING TO APPROVE — no data to base a change on",
            "safety_guard_status": f"PROTECTED (ADS_LIVE_EXECUTION_ENABLED={ADS_LIVE_EXECUTION_ENABLED})",
            "campaigns": [],
            "ad_groups": [],
            "keywords_analysed": 0,
            "search_terms_analysed": 0,
            "winning_keywords": [],
            "wasteful_keywords": [],
            "recommended_new_keywords": [],
            "recommended_negative_keywords": [],
            "estimated_monthly_savings": 0.0,
            "estimated_monthly_savings_usd": 0.0,
            "actionable_next_steps": [
                f"No recommendations were produced: {reason}",
                "Fix the Google Ads connection, then re-run. "
                "Until then this agent has measured nothing about your account.",
            ],
        }

        return {
            "output": result_payload,
            "model_used": "none — no live data",
            "tokens_used": 0,
            "cost_usd": 0.0,
        }
