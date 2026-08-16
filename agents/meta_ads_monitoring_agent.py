"""
Agent #11: Meta Ads Monitoring Agent (`meta-ads-monitoring-agent`).

Monitors Facebook & Instagram ad campaigns, spend, impressions, reach, CPM, CPC, CTR,
conversions, CPA, ROAS, and ad frequency in STRICT READ-ONLY / SIMULATED mode.
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

logger = get_agent_logger("meta-ads-monitoring-agent")


class MetaAdsMonitoringAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="meta-ads-monitoring-agent",
            name="Meta Ads Monitoring Agent",
            description="Monitors Facebook & Instagram ad performance, spend, CPM, CPC, CPA, ROAS, and ad frequency in Read-Only mode.",
            category="Paid Advertising",
            enabled=True,
            paused=False,
            supported_actions=["monitor_performance", "placement_breakdown", "frequency_check", "cost_summary"],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "monitor_performance")).lower().strip()
        ad_account_id = str(input_data.get("ad_account_id", "act_987654321")).strip()
        date_range = str(input_data.get("date_range", "last_30_days")).strip()
        use_ai = bool(input_data.get("use_ai", False))

        logger.info(f"Executing MetaAdsMonitoringAgent task: action={action}, ad_account='{ad_account_id}', live_enabled={ADS_LIVE_EXECUTION_ENABLED}")

        # Safety Check Guard
        if action in ["create_meta_campaign", "update_meta_bid", "change_meta_budget", "mutate"]:
            logger.warning(f"Blocked live Meta mutation request '{action}' (ADS_LIVE_EXECUTION_ENABLED=false)")
            return {
                "output": {
                    "status": "BLOCKED_BY_SAFETY_GUARD",
                    "reason": "ADS_LIVE_EXECUTION_ENABLED is false. Live Meta Ads mutations are disabled.",
                    "mode": "Simulation Only"
                },
                "model_used": "safety-guard",
                "tokens_used": 0,
                "cost_usd": 0.0
            }

        # Deterministic Meta Ads Monitoring Engine (Simulated Read-Only Data)
        placements = [
            {
                "platform": "Instagram Feed & Stories",
                "campaign_name": "IG - Executive Chauffeur Branding",
                "spend_usd": 640.00,
                "impressions": 38500,
                "reach": 24200,
                "frequency": 1.59,
                "cpm_usd": 16.62,
                "clicks": 540,
                "ctr_percent": 1.40,
                "cpc_usd": 1.19,
                "conversions": 28,
                "cpa_usd": 22.86,
                "roas_ratio": 3.65
            },
            {
                "platform": "Facebook News Feed",
                "campaign_name": "FB - Corporate Event Transport",
                "spend_usd": 480.00,
                "impressions": 32000,
                "reach": 19800,
                "frequency": 1.62,
                "cpm_usd": 15.00,
                "clicks": 410,
                "ctr_percent": 1.28,
                "cpc_usd": 1.17,
                "conversions": 22,
                "cpa_usd": 21.81,
                "roas_ratio": 3.90
            }
        ]

        total_spend = sum(p["spend_usd"] for p in placements)
        total_impressions = sum(p["impressions"] for p in placements)
        total_reach = sum(p["reach"] for p in placements)
        total_clicks = sum(p["clicks"] for p in placements)
        total_conversions = sum(p["conversions"] for p in placements)

        result_payload = {
            "action": action,
            "ad_account_id": ad_account_id,
            "date_range": date_range,
            "safety_guard_status": f"PROTECTED (ADS_LIVE_EXECUTION_ENABLED={ADS_LIVE_EXECUTION_ENABLED})",
            "account_summary": {
                "total_spend_usd": total_spend,
                "total_impressions": total_impressions,
                "total_reach": total_reach,
                "avg_frequency": round(total_impressions / total_reach, 2),
                "total_clicks": total_clicks,
                "avg_ctr_percent": round((total_clicks / total_impressions) * 100, 2),
                "avg_cpc_usd": round(total_spend / total_clicks, 2),
                "total_conversions": total_conversions,
                "avg_cpa_usd": round(total_spend / total_conversions, 2)
            },
            "placement_performance": placements,
            "ad_fatigue_warning": "None. Frequency is healthy at < 2.0.",
            "actionable_recommendations": [
                "1. Instagram Stories placements show high engagement; consider allocating 60% of creative budget to 9:16 vertical video.",
                "2. Maintain active audience exclusions to prevent ad fatigue."
            ]
        }

        # Optional AI Enrichment
        tokens_used = 0
        cost_usd = 0.0
        model_used = "rule-based-meta-ads-monitor"

        if use_ai:
            prompt = (
                f"Analyze Meta Ads performance for account '{ad_account_id}' spend ${total_spend}. "
                f"Identify top creative angle recommendations and audience targeting tweaks."
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
                logger.warning(f"AI Meta Ads monitoring analysis failed (fallback to rule engine): {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd
        }
