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


def _build_insights(top_queries: List[Dict[str, Any]], summary: Dict[str, Any],
                    opportunities: List[Dict[str, Any]]) -> List[str]:
    """Insights drawn from the rows just returned, not written in advance."""
    if not top_queries:
        return ["Search Console returned no queries for this window."]

    insights: List[str] = []

    if opportunities:
        best = max(opportunities, key=lambda o: o["impressions"])
        insights.append(
            f"'{best['query']}' sits at position {best['current_position']} on "
            f"{best['impressions']:,} impressions — the closest page-one gain available."
        )

    zero_click = [q for q in top_queries if q["clicks"] == 0 and q["impressions"] >= 50]
    if zero_click:
        worst = max(zero_click, key=lambda q: q["impressions"])
        insights.append(
            f"'{worst['query']}' drew {worst['impressions']:,} impressions and no clicks at "
            f"position {worst['position']} — the snippet is not earning the click."
        )

    ctr = summary.get("average_ctr_percent") or 0
    if ctr and ctr < 1.0:
        insights.append(
            f"Site CTR is {ctr}% across {summary.get('total_impressions', 0):,} impressions. "
            f"Titles and meta descriptions are the constraint before rankings."
        )

    ranked_well = [q for q in top_queries if q["position"] <= 3]
    if ranked_well:
        insights.append(
            f"{len(ranked_well)} of the queries shown already rank in the top 3 — "
            f"protect those pages before chasing new terms."
        )

    return insights or [
        f"{len(top_queries)} queries returned; nothing in this window stands out as an outlier."
    ]


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
        top_queries = []
        live_fetched = False
        live_error = None
        site_totals = None

        from integrations.google_credentials import load_service_account_credentials

        creds, cred_error = load_service_account_credentials(
            ['https://www.googleapis.com/auth/webmasters.readonly']
        )
        if cred_error:
            live_error = cred_error
            logger.warning(f"GSC live fetch unavailable: {cred_error}")

        if creds:
            try:
                from googleapiclient.discovery import build
                from datetime import datetime, timedelta

                service = build('searchconsole', 'v1', credentials=creds)

                # date_range was accepted and then ignored: the window was always
                # the last 30 days whatever the caller asked for.
                window_days = {
                    "last_7_days": 7, "last_28_days": 28, "last_30_days": 30,
                    "last_90_days": 90, "last_180_days": 180,
                }.get(date_range, 30)

                end_d = datetime.now() - timedelta(days=2)
                start_d = end_d - timedelta(days=window_days)

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

                    # The summary used to be the sum of these 15 rows and call
                    # itself "total" — 761 impressions against a site doing
                    # 21,000. A query with no dimensions returns the real totals.
                    try:
                        totals_res = service.searchanalytics().query(
                            siteUrl=target_site,
                            body={
                                'startDate': start_d.strftime('%Y-%m-%d'),
                                'endDate': end_d.strftime('%Y-%m-%d'),
                                'dimensions': [],
                            },
                        ).execute()
                        rows = totals_res.get("rows") or []
                        if rows:
                            r0 = rows[0]
                            site_totals = {
                                "clicks": int(r0.get("clicks", 0)),
                                "impressions": int(r0.get("impressions", 0)),
                                "ctr_percent": round(float(r0.get("ctr", 0)) * 100, 2),
                                "position": round(float(r0.get("position", 0)), 1),
                            }
                    except Exception as e:
                        logger.warning(f"Could not fetch Search Console site totals: {e}")
                else:
                    live_error = "Search Console returned no rows for this date range."
            except Exception as e:
                live_error = f"Search Console API call failed: {e}"
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

        # CTR is clicks over impressions. Averaging the per-query percentages
        # gave every query equal weight regardless of size, which reported
        # 14.18% for a site whose actual CTR over the same rows was 1.97%.
        # Position is weighted by impressions for the same reason.
        shown_clicks = sum(q["clicks"] for q in top_queries)
        shown_imps = sum(q["impressions"] for q in top_queries)
        shown_ctr = round(shown_clicks / shown_imps * 100, 2) if shown_imps else 0.0
        shown_pos = (
            round(sum(q["position"] * q["impressions"] for q in top_queries) / shown_imps, 1)
            if shown_imps else 0.0
        )

        summary_metrics = {
            # Site-wide when the API gave them; otherwise the rows shown, and
            # the scope says which.
            "total_clicks": site_totals["clicks"] if site_totals else shown_clicks,
            "total_impressions": site_totals["impressions"] if site_totals else shown_imps,
            "average_ctr_percent": site_totals["ctr_percent"] if site_totals else shown_ctr,
            "average_position": site_totals["position"] if site_totals else shown_pos,
            "scope": "whole site" if site_totals else f"top {len(top_queries)} queries shown",
            "top_queries_clicks": shown_clicks,
            "top_queries_impressions": shown_imps,
            "top_queries_ctr_percent": shown_ctr,
            "data_source": (
                "100% LIVE GOOGLE SEARCH CONSOLE API" if live_fetched
                else "SAMPLE DATA - NOT LIVE. Do not use for decisions."
            )
        }

        result_payload = {
            "action": action,
            "site_url": site_url,
            "date_range": date_range,
            "live_data_connected": live_fetched,
            "live_error": live_error,
            "performance_summary": summary_metrics,
            "top_queries": top_queries,
            "quick_win_opportunities": opportunity_keywords,
            # These two lines used to be fixed text quoting positions 7.6 and
            # 11.6 for two named keywords — figures from the sample data, shown
            # unchanged over live results that said something else entirely.
            "actionable_insights": _build_insights(top_queries, summary_metrics, opportunity_keywords)
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
