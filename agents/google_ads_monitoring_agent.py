"""
Agent #9: Google Ads Monitoring Agent (`google-ads-monitoring-agent`).

Monitors Google Ads campaigns, clicks, impressions, CTR, CPC, spend, conversions,
CPA, ROAS, and budget utilization in STRICT READ-ONLY / SIMULATED mode.
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

logger = get_agent_logger("google-ads-monitoring-agent")


class GoogleAdsMonitoringAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="google-ads-monitoring-agent",
            name="Google Ads Monitoring Agent",
            description="Monitors Google Ads performance, campaign spend, CTR, CPC, CPA, ROAS, and anomalies in safe Read-Only mode.",
            category="Paid Advertising",
            enabled=True,
            paused=False,
            supported_actions=["monitor_performance", "campaign_breakdown", "anomaly_detection", "cost_summary"],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "monitor_performance")).lower().strip()
        account_id = str(input_data.get("account_id", "123-456-7890")).strip()
        date_range = str(input_data.get("date_range", "last_30_days")).strip()
        use_ai = bool(input_data.get("use_ai", False))

        logger.info(f"Executing GoogleAdsMonitoringAgent task: action={action}, account='{account_id}', live_enabled={ADS_LIVE_EXECUTION_ENABLED}")

        # Safety Check Guard
        if action in ["create_campaign", "update_bid", "change_budget", "mutate"]:
            logger.warning(f"Blocked live mutation request '{action}' (ADS_LIVE_EXECUTION_ENABLED=false)")
            return {
                "output": {
                    "status": "BLOCKED_BY_SAFETY_GUARD",
                    "reason": "ADS_LIVE_EXECUTION_ENABLED is false. Live Google Ads mutations are disabled.",
                    "mode": "Simulation Only"
                },
                "model_used": "safety-guard",
                "tokens_used": 0,
                "cost_usd": 0.0
            }

        # Deterministic Google Ads Monitoring Engine (Simulated Read-Only Data)
        campaigns = [
            {
                "campaign_name": "Search - Corporate Chauffeur Melbourne",
                "status": "ACTIVE",
                "daily_budget_usd": 50.0,
                "spend_usd": 1240.50,
                "impressions": 14200,
                "clicks": 680,
                "ctr_percent": 4.79,
                "avg_cpc_usd": 1.82,
                "conversions": 52,
                "cpa_usd": 23.85,
                "roas_ratio": 4.15
            },
            {
                "campaign_name": "Search - Airport Transfers Tullamarine",
                "status": "ACTIVE",
                "daily_budget_usd": 40.0,
                "spend_usd": 980.00,
                "impressions": 11500,
                "clicks": 590,
                "ctr_percent": 5.13,
                "avg_cpc_usd": 1.66,
                "conversions": 48,
                "cpa_usd": 20.41,
                "roas_ratio": 4.80
            }
        ]

        total_spend = sum(c["spend_usd"] for c in campaigns)
        total_clicks = sum(c["clicks"] for c in campaigns)
        total_impressions = sum(c["impressions"] for c in campaigns)
        total_conversions = sum(c["conversions"] for c in campaigns)

        anomalies = [
            {
                "campaign": "Search - Corporate Chauffeur Melbourne",
                "metric": "CPC",
                "finding": "CPC increased by +12% on weekends due to competitive bidding.",
                "severity": "LOW"
            }
        ]

        result_payload = {
            "action": action,
            "account_id": account_id,
            "date_range": date_range,
            "safety_guard_status": f"PROTECTED (ADS_LIVE_EXECUTION_ENABLED={ADS_LIVE_EXECUTION_ENABLED})",
            "account_summary": {
                "total_spend_usd": total_spend,
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "avg_ctr_percent": round((total_clicks / total_impressions) * 100, 2),
                "avg_cpc_usd": round(total_spend / total_clicks, 2),
                "total_conversions": total_conversions,
                "avg_cpa_usd": round(total_spend / total_conversions, 2)
            },
            "campaign_performance": campaigns,
            "detected_anomalies": anomalies,
            "actionable_recommendations": [
                "1. Maintain current Airport Transfers budget (High ROAS 4.8x).",
                "2. Review Optimization Agent suggestions for negative keyword additions."
            ]
        }

        # Optional AI Enrichment
        tokens_used = 0
        cost_usd = 0.0
        model_used = "rule-based-google-ads-monitor"

        if use_ai:
            prompt = (
                f"Analyze Google Ads campaign metrics for account '{account_id}' spend ${total_spend}. "
                f"Identify top CPA reduction opportunities and budget re-allocation tips."
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
                logger.warning(f"AI Google Ads monitoring analysis failed (fallback to rule engine): {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd
        }
