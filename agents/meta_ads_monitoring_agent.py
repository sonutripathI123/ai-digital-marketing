"""
Agent #11: Meta Ads Monitoring Agent (`meta-ads-monitoring-agent`).

Reads Facebook and Instagram ad performance from the Meta Marketing API, and
reports nothing when it cannot.

The version this replaces made no API call at all. It carried two campaigns
written into its own source -- "IG - Executive Chauffeur Branding" at $640 and
"FB - Corporate Event Transport" at $480, with impressions, reach, frequency,
CPM, CTR, CPC, 50 conversions between them and a ROAS of 3.65 and 3.90 -- and
summed them into an account total of $1,120 spend across 70,500 impressions. It
then stated "Ad fatigue warning: None. Frequency is healthy at < 2.0", a verdict
on figures nobody had measured, and advised moving 60% of the creative budget to
vertical video on the strength of them.

Its docstring called this "SIMULATED" mode. The payload did not: `account_summary`
presented those totals as the account's own, under a real ad account id field.

Reading real data needs two things this system does not have by default: the
`ads_read` permission on the Meta token, and an ad account id. Both are
reported as missing rather than stood in for.
"""

from typing import Any, Dict, List, Optional, Tuple

from agents.base import AgentInterface
from config.settings import ADS_LIVE_EXECUTION_ENABLED
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("meta-ads-monitoring-agent")

GRAPH = "https://graph.facebook.com/v19.0"
FETCH_TIMEOUT_SECONDS = 20

DATE_PRESETS = {
    "today": "today",
    "yesterday": "yesterday",
    "last_7_days": "last_7d",
    "last_14_days": "last_14d",
    "last_28_days": "last_28d",
    "last_30_days": "last_30d",
    "last_90_days": "last_90d",
    "this_month": "this_month",
    "last_month": "last_month",
}

MUTATING_ACTIONS = ("create_meta_campaign", "update_meta_bid", "change_meta_budget", "mutate")


def resolve_meta_ads_credentials(site_id: str) -> Dict[str, str]:
    """The ad account and token for a site, from saved credentials or env."""
    import os

    from dotenv import load_dotenv

    from config.settings import ROOT_DIR

    load_dotenv(ROOT_DIR / "corporate-cars-social-agent" / ".env", override=False)

    creds: Dict[str, str] = {}
    try:
        from config.websites import WebsiteManager

        saved = WebsiteManager().get_agent_credentials(site_id, "meta-ads-monitoring-agent") or {}
        for key in ("ad_account_id", "access_token"):
            if saved.get(key):
                creds[key] = str(saved[key]).strip()
    except Exception as e:
        logger.warning(f"Could not read saved Meta Ads credentials for {site_id}: {e}")

    prefix = "OPAL_" if site_id == "opal" else ""
    if not creds.get("ad_account_id"):
        for name in (f"{prefix}META_AD_ACCOUNT_ID", "META_AD_ACCOUNT_ID", "META_ADS_ACCOUNT_ID"):
            if os.getenv(name):
                creds["ad_account_id"] = os.getenv(name, "").strip()
                break
    if not creds.get("access_token"):
        for name in (f"{prefix}META_ACCESS_TOKEN", f"{prefix}META_USER_TOKEN", "META_USER_TOKEN"):
            if os.getenv(name):
                creds["access_token"] = os.getenv(name, "").strip()
                break
    return creds


def token_has_ads_read(token: str) -> Tuple[bool, List[str]]:
    """Whether this token may read ad data, and what it does carry."""
    import requests

    try:
        res = requests.get(f"{GRAPH}/me/permissions",
                           params={"access_token": token}, timeout=FETCH_TIMEOUT_SECONDS)
        if res.status_code != 200:
            return False, []
        granted = sorted(p["permission"] for p in res.json().get("data", [])
                         if p.get("status") == "granted")
        return "ads_read" in granted, granted
    except Exception as e:
        logger.warning(f"Could not read Meta token permissions: {e}")
        return False, []


def fetch_ad_insights(account_id: str, token: str, date_preset: str
                      ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Campaign-level insights straight from the Marketing API."""
    import requests

    account = account_id if account_id.startswith("act_") else f"act_{account_id}"
    try:
        res = requests.get(
            f"{GRAPH}/{account}/insights",
            params={
                "level": "campaign",
                "date_preset": date_preset,
                "fields": ("campaign_name,spend,impressions,reach,frequency,clicks,ctr,cpc,cpm,"
                           "actions,cost_per_action_type"),
                "limit": 100,
                "access_token": token,
            },
            timeout=FETCH_TIMEOUT_SECONDS,
        )
    except Exception as e:
        return [], f"Could not reach the Meta Marketing API: {e}"

    if res.status_code != 200:
        try:
            message = res.json().get("error", {}).get("message", "")
        except Exception:
            message = res.text[:200]
        return [], f"Meta returned HTTP {res.status_code}: {message}"

    rows: List[Dict[str, Any]] = []
    for row in res.json().get("data") or []:
        # Meta reports conversions inside an `actions` list keyed by type; a
        # campaign with none simply has no entry, which is not zero conversions
        # of a type it never tracked.
        actions = {a.get("action_type"): a.get("value") for a in (row.get("actions") or [])}
        leads = actions.get("lead") or actions.get("offsite_conversion.fb_pixel_lead")
        rows.append({
            "campaign_name": row.get("campaign_name"),
            "spend": float(row.get("spend") or 0),
            "impressions": int(row.get("impressions") or 0),
            "reach": int(row.get("reach") or 0),
            "frequency": round(float(row.get("frequency") or 0), 2),
            "clicks": int(row.get("clicks") or 0),
            "ctr_percent": round(float(row.get("ctr") or 0), 2),
            "cpc": round(float(row.get("cpc") or 0), 2),
            "cpm": round(float(row.get("cpm") or 0), 2),
            "leads": int(leads) if leads is not None else None,
            "all_actions": actions,
        })
    return rows, None


def not_connected(action: str, date_range: str, reason: str,
                  detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The honest empty report. No placements, no totals, no verdict."""
    return {
        "action": action,
        "date_range": date_range,
        "live_data_connected": False,
        "data_source": "NOT CONNECTED — Meta Ads was not read",
        "live_error": reason,
        "safety_guard_status": f"PROTECTED (ADS_LIVE_EXECUTION_ENABLED={ADS_LIVE_EXECUTION_ENABLED})",
        "account_summary": {},
        "campaign_performance": [],
        # The old payload asserted "Ad fatigue warning: None. Frequency is
        # healthy at < 2.0" without a frequency to judge.
        "ad_fatigue": None,
        "actionable_recommendations": [f"Connect Meta Ads to report on it: {reason}"],
        **(detail or {}),
    }


class MetaAdsMonitoringAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="meta-ads-monitoring-agent",
            name="Meta Ads Monitoring Agent",
            description="Reads Facebook and Instagram ad spend, reach, frequency, CPC and CPM from the Meta Marketing API.",
            category="Paid Advertising",
            enabled=True,
            paused=False,
            supported_actions=["monitor_performance", "placement_breakdown", "frequency_check", "cost_summary"],
            version="2.0.0",
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "monitor_performance")).lower().strip()
        date_range = str(input_data.get("date_range", "last_30_days")).strip()
        site_id = input_data.get("site_id") or getattr(task, "site_id", None) or "ccm"
        use_ai = bool(input_data.get("use_ai", False))

        if action in MUTATING_ACTIONS:
            logger.warning(f"Blocked live Meta mutation request '{action}'")
            return {
                "output": {
                    "status": "BLOCKED_BY_SAFETY_GUARD",
                    "reason": "This agent is read-only. It cannot create or change Meta campaigns.",
                },
                "model_used": "safety-guard", "tokens_used": 0, "cost_usd": 0.0,
            }

        creds = resolve_meta_ads_credentials(site_id)
        account_id = creds.get("ad_account_id")
        token = creds.get("access_token")

        logger.info(
            f"Executing MetaAdsMonitoringAgent: action={action}, site={site_id}, "
            f"account={'set' if account_id else 'missing'}, token={'set' if token else 'missing'}"
        )

        if not token:
            return {"output": not_connected(action, date_range,
                    "No Meta access token is configured for this site."),
                    "model_used": "none", "tokens_used": 0, "cost_usd": 0.0}

        has_ads_read, granted = token_has_ads_read(token)
        if not has_ads_read:
            return {"output": not_connected(
                action, date_range,
                "The Meta access token does not carry the ads_read permission, so no ad data "
                "can be read. Add ads_read to the token in Graph API Explorer and save it again.",
                {"token_permissions": granted},
            ), "model_used": "none", "tokens_used": 0, "cost_usd": 0.0}

        if not account_id:
            return {"output": not_connected(
                action, date_range,
                "No Meta ad account id is configured. Add it under this agent's Connect form "
                "(it looks like act_1234567890, shown in Meta Ads Manager).",
                {"token_permissions": granted},
            ), "model_used": "none", "tokens_used": 0, "cost_usd": 0.0}

        campaigns, error = fetch_ad_insights(
            account_id, token, DATE_PRESETS.get(date_range, "last_30d"))
        if error:
            return {"output": not_connected(action, date_range, error,
                    {"ad_account_id": account_id, "token_permissions": granted}),
                    "model_used": "none", "tokens_used": 0, "cost_usd": 0.0}

        spend = round(sum(c["spend"] for c in campaigns), 2)
        impressions = sum(c["impressions"] for c in campaigns)
        reach = sum(c["reach"] for c in campaigns)
        clicks = sum(c["clicks"] for c in campaigns)
        lead_values = [c["leads"] for c in campaigns if c["leads"] is not None]

        summary = {
            "total_spend": spend,
            "total_impressions": impressions,
            "total_reach": reach,
            # Frequency is impressions over reach, and is undefined without reach
            # rather than being 0.
            "avg_frequency": round(impressions / reach, 2) if reach else None,
            "total_clicks": clicks,
            "avg_ctr_percent": round(clicks / impressions * 100, 2) if impressions else None,
            "avg_cpc": round(spend / clicks, 2) if clicks else None,
            "total_leads": sum(lead_values) if lead_values else None,
            "cost_per_lead": round(spend / sum(lead_values), 2) if lead_values and sum(lead_values) else None,
        }

        frequency = summary["avg_frequency"]
        result_payload: Dict[str, Any] = {
            "action": action,
            "date_range": date_range,
            "live_data_connected": True,
            "data_source": "LIVE — Meta Marketing API",
            "live_error": None,
            "ad_account_id": account_id,
            "safety_guard_status": f"PROTECTED (ADS_LIVE_EXECUTION_ENABLED={ADS_LIVE_EXECUTION_ENABLED})",
            "account_summary": summary,
            "campaign_performance": campaigns,
            "campaigns_returned": len(campaigns),
            "ad_fatigue": (
                None if frequency is None else
                {"frequency": frequency,
                 "note": (f"Each person saw an ad {frequency} times on average. Above about 3 the "
                          f"same people are being shown the same ad repeatedly.")}
            ),
            "leads_note": (
                "Meta reports conversions per action type; campaigns with no lead action "
                "report none rather than zero."
            ),
            "actionable_recommendations": self._recommend(campaigns, summary),
        }

        tokens_used, cost_usd = 0, 0.0
        model_used = "meta-marketing-api"

        if use_ai and campaigns:
            try:
                response = router.route_and_execute(LLMRequest(
                    user_prompt=(
                        f"These are the only measured figures for a Meta Ads account over "
                        f"{date_range}: {summary}. Campaigns: "
                        f"{[{k: c[k] for k in ('campaign_name', 'spend', 'clicks', 'leads')} for c in campaigns]}. "
                        f"Return JSON with 'observations' and 'next_steps'. Do not invent "
                        f"creative performance, audience data or ROAS -- none of that is here."
                    ),
                    task_type=TaskComplexity.STANDARD, json_output=True,
                ))
                model_used = response.model_used
                tokens_used = response.tokens_in + response.tokens_out
                cost_usd = response.cost_usd
                if response.parsed_json:
                    result_payload["ai_analysis"] = response.parsed_json
            except Exception as e:
                logger.warning(f"AI Meta Ads analysis failed: {e}")

        return {"output": result_payload, "model_used": model_used,
                "tokens_used": tokens_used, "cost_usd": cost_usd}

    @staticmethod
    def _recommend(campaigns: List[Dict[str, Any]], summary: Dict[str, Any]) -> List[str]:
        """Advice from these campaigns, not written in advance."""
        out: List[str] = []
        if not campaigns:
            return ["The account returned no campaigns for this period."]

        frequency = summary.get("avg_frequency")
        if frequency and frequency > 3:
            out.append(
                f"Average frequency is {frequency}. The same people are seeing these ads "
                f"repeatedly; widen the audience or refresh the creative."
            )

        spending_no_leads = [
            c for c in campaigns
            if c["spend"] > 0 and (c["leads"] is None or c["leads"] == 0)
        ]
        if spending_no_leads:
            wasted = round(sum(c["spend"] for c in spending_no_leads), 2)
            out.append(
                f"{len(spending_no_leads)} campaign(s) spent {wasted} without a recorded lead. "
                f"Check that lead tracking is set up before concluding they failed."
            )

        if summary.get("cost_per_lead"):
            out.append(f"Cost per lead across the account is {summary['cost_per_lead']}.")

        return out or [f"{len(campaigns)} campaigns returned; nothing stands out as an outlier."]
