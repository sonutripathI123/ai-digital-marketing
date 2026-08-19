"""
Agent #8: GA4 Reporting Agent (`ga4-reporting-agent`).

Fetches and aggregates Google Analytics 4 traffic metrics, user engagement,
acquisition channels, landing page performance, and conversion trends.
"""

from typing import Any, Dict, List
from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

from pathlib import Path
from config.settings import ROOT_DIR

logger = get_agent_logger("ga4-reporting-agent")

GA4_PROPERTY_ID = "550393874"
GA4_MEASUREMENT_ID = "G-2CM2BW6QKN"
GA4_ACCOUNT_ID = "402540807"


class GA4ReportingAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="ga4-reporting-agent",
            name="GA4 Reporting Agent",
            description="Analyzes GA4 active users, sessions, channel acquisition, top landing pages, and conversion events.",
            category="Analytics & Reporting",
            enabled=True,
            paused=False,
            supported_actions=["fetch_overview", "acquisition_channels", "top_landing_pages", "conversion_summary"],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "fetch_overview")).lower().strip()
        property_name = str(input_data.get("property_name", f"Corporate Cars Melbourne GA4 ({GA4_MEASUREMENT_ID})")).strip()
        date_range = str(input_data.get("date_range", "last_28_days")).strip()
        use_ai = bool(input_data.get("use_ai", False))

        logger.info(f"Executing GA4ReportingAgent task: action={action}, property='{property_name}', date_range='{date_range}'")

        # Live GA4 Analytics Connection via Google Analytics Data API / Service Account
        key_file = Path(ROOT_DIR) / "gsc-service-account.json"
        live_fetched = False
        channel_breakdown = []
        top_landing_pages = []

        if key_file.exists():
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build

                creds = service_account.Credentials.from_service_account_file(
                    str(key_file),
                    scopes=['https://www.googleapis.com/auth/analytics.readonly']
                )
                data_service = build('analyticsdata', 'v1beta', credentials=creds)
                
                # Query 1: Acquisition Channels Breakdown
                channel_req = {
                    "dateRanges": [{"startDate": "28daysAgo", "endDate": "today"}],
                    "dimensions": [{"name": "sessionDefaultChannelGroup"}],
                    "metrics": [
                        {"name": "activeUsers"},
                        {"name": "sessions"},
                        {"name": "engagementRate"},
                        {"name": "conversions"}
                    ]
                }
                c_res = data_service.properties().runReport(property=f'properties/{GA4_PROPERTY_ID}', body=channel_req).execute()
                for row in c_res.get('rows', []):
                    c_name = row['dimensionValues'][0]['value']
                    c_users = int(row['metricValues'][0]['value'])
                    c_sessions = int(row['metricValues'][1]['value'])
                    c_eng = round(float(row['metricValues'][2]['value']) * 100, 1)
                    c_conv = int(float(row['metricValues'][3]['value']))
                    channel_breakdown.append({
                        "channel": c_name,
                        "users": c_users,
                        "sessions": c_sessions,
                        "engagement_rate": c_eng,
                        "conversions": c_conv
                    })

                # Query 2: Top Landing Pages
                page_req = {
                    "dateRanges": [{"startDate": "28daysAgo", "endDate": "today"}],
                    "dimensions": [{"name": "pagePath"}],
                    "metrics": [
                        {"name": "sessions"},
                        {"name": "userEngagementDuration"},
                        {"name": "conversions"}
                    ],
                    "limit": 10
                }
                p_res = data_service.properties().runReport(property=f'properties/{GA4_PROPERTY_ID}', body=page_req).execute()
                for row in p_res.get('rows', []):
                    p_path = row['dimensionValues'][0]['value']
                    p_sessions = int(row['metricValues'][0]['value'])
                    p_dur = int(float(row['metricValues'][1]['value']))
                    p_dur_avg = round(p_dur / max(p_sessions, 1))
                    p_conv = int(float(row['metricValues'][2]['value']))
                    top_landing_pages.append({
                        "page": p_path,
                        "sessions": p_sessions,
                        "engagement_time_sec": p_dur_avg,
                        "conversions": p_conv
                    })

                live_fetched = True
                logger.info(f"Successfully authenticated and connected to live GA4 Data API for property {GA4_PROPERTY_ID}")
            except Exception as e:
                logger.warning(f"GA4 Data API fetch notice: {e}")

        if live_fetched:
            # 100% Genuine Live Google API Data
            total_users = sum(c["users"] for c in channel_breakdown) if channel_breakdown else 0
            total_sessions = sum(c["sessions"] for c in channel_breakdown) if channel_breakdown else 0
            total_conversions = sum(c["conversions"] for c in channel_breakdown) if channel_breakdown else 0
            avg_engagement = round(sum(c["engagement_rate"] for c in channel_breakdown) / max(len(channel_breakdown), 1), 1) if channel_breakdown else 0.0
            conv_rate = f"{round((total_conversions / max(total_sessions, 1)) * 100, 2)}%" if total_sessions > 0 else "0.0%"

            result_payload = {
                "action": action,
                "property_name": property_name,
                "property_id": GA4_PROPERTY_ID,
                "measurement_id": GA4_MEASUREMENT_ID,
                "account_id": GA4_ACCOUNT_ID,
                "live_data_connected": True,
                "data_source": "100% LIVE GOOGLE ANALYTICS 4 API",
                "site_tag_status": "GOOGLE API CONNECTED & LISTENING",
                "date_range": date_range,
                "overview_metrics": {
                    "total_users": total_users,
                    "total_sessions": total_sessions,
                    "total_conversions": total_conversions,
                    "average_engagement_rate": f"{avg_engagement}%",
                    "conversion_rate": conv_rate
                },
                "acquisition_channel_breakdown": channel_breakdown,
                "top_landing_pages": top_landing_pages,
                "actionable_insights": [
                    f"1. 🟢 Live Google Analytics 4 API successfully connected to Property ID '{GA4_PROPERTY_ID}' (Measurement ID: {GA4_MEASUREMENT_ID}).",
                    "2. Stream is active and listening for live visitors on corporatecarsmelbourne.com.au.",
                    "3. Ensure the Measurement Tag 'G-2CM2BW6QKN' is placed on your WordPress website so visitor hits are recorded."
                ]
            }
        else:
            # Unconnected State
            result_payload = {
                "action": action,
                "property_name": property_name,
                "property_id": GA4_PROPERTY_ID,
                "measurement_id": GA4_MEASUREMENT_ID,
                "account_id": GA4_ACCOUNT_ID,
                "live_data_connected": False,
                "data_source": "Pending Connection",
                "site_tag_status": "PENDING AUTHENTICATION",
                "date_range": date_range,
                "overview_metrics": {
                    "total_users": 0,
                    "total_sessions": 0,
                    "total_conversions": 0,
                    "average_engagement_rate": "0%",
                    "conversion_rate": "0%"
                },
                "acquisition_channel_breakdown": [],
                "top_landing_pages": [],
                "actionable_insights": [
                    "1. GA4 connection pending verification."
                ]
            }

        # Optional AI Enrichment
        tokens_used = 0
        cost_usd = 0.0
        model_used = "rule-based-ga4-engine"

        if use_ai:
            prompt = (
                f"Analyze GA4 traffic performance for '{property_name}' over '{date_range}'. "
                f"Identify key growth channels, bounce/engagement risks, and conversion optimization strategies."
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
                logger.warning(f"AI GA4 analysis failed (fallback to rule engine): {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd
        }
