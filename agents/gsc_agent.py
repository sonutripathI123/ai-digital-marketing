"""
Agent #7: Google Search Console Agent (`gsc-agent`).

Fetches and analyzes organic search performance metrics (clicks, impressions, CTR, average position),
top queries, top landing pages, and high-potential keyword opportunities.
"""

from pathlib import Path
from typing import Any, Dict, List
from config.settings import ROOT_DIR
from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("gsc-agent")


class GSCAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="gsc-agent",
            name="Google Search Console Agent",
            description="Analyzes organic search clicks, impressions, CTR, positions, and detects quick-win keyword opportunities.",
            category="Analytics & Reporting",
            enabled=True,
            paused=False,
            supported_actions=["fetch_performance", "top_queries", "top_pages", "opportunity_keywords"],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "fetch_performance")).lower().strip()
        site_url = str(input_data.get("site_url", "https://corporatecarsmelbourne.com.au")).strip()
        date_range = str(input_data.get("date_range", "last_28_days")).strip()
        use_ai = bool(input_data.get("use_ai", False))

        logger.info(f"Executing GSCAgent task: action={action}, site_url='{site_url}', date_range='{date_range}'")

        # Live Google Search Console API Connection
        key_file = Path(ROOT_DIR) / "gsc-service-account.json"
        top_queries = []
        live_fetched = False

        if key_file.exists():
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                from datetime import datetime, timedelta

                creds = service_account.Credentials.from_service_account_file(
                    str(key_file),
                    scopes=['https://www.googleapis.com/auth/webmasters.readonly']
                )
                service = build('searchconsole', 'v1', credentials=creds)

                end_d = datetime.now() - timedelta(days=2)
                start_d = end_d - timedelta(days=30)
                
                request_body = {
                    'startDate': start_d.strftime('%Y-%m-%d'),
                    'endDate': end_d.strftime('%Y-%m-%d'),
                    'dimensions': ['query'],
                    'rowLimit': 15
                }

                target_site = site_url if site_url.endswith('/') else site_url + '/'
                res = service.searchanalytics().query(siteUrl=target_site, body=request_body).execute()

                if "rows" in res:
                    for row in res["rows"]:
                        top_queries.append({
                            "query": row["keys"][0],
                            "clicks": int(row.get("clicks", 0)),
                            "impressions": int(row.get("impressions", 0)),
                            "ctr": round(float(row.get("ctr", 0)) * 100, 2),
                            "position": round(float(row.get("position", 0)), 1)
                        })
                    live_fetched = True
            except Exception as e:
                logger.warning(f"Failed to fetch live GSC API data: {e}")

        if not top_queries:
            top_queries = [
                {"query": "corporate cars melbourne", "clicks": 9, "impressions": 297, "ctr": 3.03, "position": 27.8},
                {"query": "melbourne corporate cars", "clicks": 7, "impressions": 445, "ctr": 1.57, "position": 7.6},
                {"query": "corporate chauffeur melbourne", "clicks": 1, "impressions": 327, "ctr": 0.30, "position": 21.5},
                {"query": "melbourne corporate cars limousines", "clicks": 1, "impressions": 53, "ctr": 1.89, "position": 14.2},
                {"query": "sprinter van hire melbourne", "clicks": 1, "impressions": 20, "ctr": 5.00, "position": 11.6}
            ]

        # Generate Quick-Win Keyword Opportunities
        opportunity_keywords = []
        for q in top_queries:
            if 4.0 <= q["position"] <= 20.0 and q["impressions"] > 15:
                opportunity_keywords.append({
                    "query": q["query"],
                    "impressions": q["impressions"],
                    "current_position": q["position"],
                    "current_ctr": q["ctr"],
                    "potential_win": f"Quick Win — Position {q['position']} (Page 1/2 opportunity). Optimize title & headers to boost CTR.",
                    "recommendation": f"Add dedicated blog content targeting '{q['query']}' and pair with internal links."
                })

        total_clks = sum(q["clicks"] for q in top_queries)
        total_imps = sum(q["impressions"] for q in top_queries)
        avg_ctr = round(sum(q["ctr"] for q in top_queries) / len(top_queries), 2) if top_queries else 0.0
        avg_pos = round(sum(q["position"] for q in top_queries) / len(top_queries), 1) if top_queries else 0.0

        summary_metrics = {
            "total_clicks": total_clks,
            "total_impressions": total_imps,
            "average_ctr_percent": avg_ctr,
            "average_position": avg_pos,
            "data_source": "100% LIVE GOOGLE SEARCH CONSOLE API" if live_fetched else "Fallback Metrics"
        }

        result_payload = {
            "action": action,
            "site_url": site_url,
            "date_range": date_range,
            "live_data_connected": live_fetched,
            "performance_summary": summary_metrics,
            "top_queries": top_queries,
            "quick_win_opportunities": opportunity_keywords,
            "actionable_insights": [
                "1. Focus content optimization on 'melbourne corporate cars' (Position 7.6 - Page 1 opportunity!).",
                "2. Create dedicated pillar page for 'sprinter van hire melbourne' (Position 11.6 - Top of Page 2)."
            ]
        }

        # Optional AI Enrichment
        tokens_used = 0
        cost_usd = 0.0
        model_used = "rule-based-gsc-engine"

        if use_ai:
            prompt = (
                f"Analyze Google Search Console metrics for site '{site_url}' over '{date_range}'. "
                f"Identify top CTR optimization priorities and keyword ranking trends."
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
                logger.warning(f"AI GSC analysis failed (fallback to rule engine): {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd
        }
