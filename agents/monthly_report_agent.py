"""
Agent #15: Monthly Marketing Report Agent (`monthly-report-agent`).

Consolidates what the other agents measured into one executive report. Every
figure carries the agent it came from, and anything nobody measured is reported
as not measured rather than filled in.

This matters more here than anywhere else in the system. The report has a
"Download Executive PDF Report" button, so its numbers leave the dashboard and
land in front of stakeholders. The version this replaces put these in that
document as fact:

    "Total Marketing Revenue Generated: $12,800.00 AUD from 42 qualified
     inbound leads"          -- no revenue or lead source exists in this system
    "$3,340.50 total spend generated 150 conversions with a 4.23x Blended ROAS"
                             -- while reporting ad spend as $0.00 on an account
                                that had actually spent A$874.66
    "4.8 / 5.0 across 142 reviews, 91.5% positive sentiment"
                             -- the same invented figures the reputation agent
                                carried, for a profile that did not exist
    "Site health 96 / 100 Grade A+", "44,000 reach", "3,700 engagements",
    "$18,400 pipeline", "18 corporate accounts", "3,840 GA4 sessions"
                             -- literals, identical on every run

Live values that were fetched had hardcoded fallbacks behind them (`or 13`,
`or 18`, `or 14`), so a failed fetch was indistinguishable from a real result.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.base import AgentInterface
from config.settings import ROOT_DIR
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("monthly-report-agent")

NOT_MEASURED = "not measured"


def _section(source: str, measured: bool, **values: Any) -> Dict[str, Any]:
    """One channel's block, stamped with where it came from."""
    return {"source": source, "measured": measured, **values}


def _run(agent, task_id: str, agent_id: str, action: str, router: ModelRouter,
         site_id: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run another agent and hand back its output, or an empty dict."""
    payload = {"action": action, "site_id": site_id}
    payload.update(extra or {})
    try:
        task = AgentTask(task_id=task_id, agent_id=agent_id, task_type=action,
                         input_data=payload, site_id=site_id)
        return agent.run_task(task, router).get("output", {}) or {}
    except Exception as e:
        logger.warning(f"Monthly report could not read {agent_id}: {e}")
        return {}


def collect_blog_metrics(site_id: str) -> Dict[str, Any]:
    """Published and queued posts, counted from the blog agent's own queue."""
    topics_file = ROOT_DIR / "blog-agent" / "topics.csv"
    if not topics_file.exists():
        return _section("blog agent queue (topics.csv not found)", False,
                        published=None, queued=None, published_inventory=[])

    published, queued = [], []
    try:
        import csv

        with open(topics_file, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if site_id and r.get("site") and r.get("site") != site_id:
                    continue
                if r.get("status") == "published":
                    published.append({
                        "id": r.get("id"),
                        "keyword": r.get("keyword"),
                        "title": r.get("title_hint"),
                        "suburb": r.get("suburb"),
                        "published_at": r.get("go_live_at"),
                        "url": r.get("notes") or None,
                    })
                elif r.get("status") in ("approved", "queued"):
                    queued.append({"id": r.get("id"), "keyword": r.get("keyword")})
    except Exception as e:
        logger.warning(f"Could not read the blog queue: {e}")
        return _section(f"blog agent queue — unreadable: {e}", False,
                        published=None, queued=None, published_inventory=[])

    return _section("blog agent queue (topics.csv)", True,
                    published=len(published), queued=len(queued),
                    published_inventory=published)


def collect_search_metrics(router: ModelRouter, site_id: str) -> Dict[str, Any]:
    """Search Console, read through the GSC agent rather than re-queried here.

    The old code ran its own Search Console query, summed the top 25 query rows
    and called the result the site total -- the same mistake the GSC agent was
    fixed for. Asking that agent means one definition of these numbers.
    """
    from agents.gsc_agent import GSCAgent

    out = _run(GSCAgent(), "monthly-gsc", "gsc-agent", "fetch_performance", router, site_id)
    if not out.get("live_data_connected"):
        return _section("Search Console — not connected", False,
                        clicks=None, impressions=None, ctr_percent=None,
                        average_position=None, top_queries=[],
                        error=out.get("live_error"))

    summary = out.get("performance_summary") or {}
    return _section("Google Search Console API", True,
                    clicks=summary.get("total_clicks"),
                    impressions=summary.get("total_impressions"),
                    ctr_percent=summary.get("average_ctr_percent"),
                    average_position=summary.get("average_position"),
                    scope=summary.get("scope"),
                    top_queries=(out.get("top_queries") or [])[:8])


def collect_analytics_metrics(router: ModelRouter, site_id: str) -> Dict[str, Any]:
    """GA4 sessions and users. Previously the literals 3,840 and 2,180."""
    from agents.ga4_reporting_agent import GA4ReportingAgent

    out = _run(GA4ReportingAgent(), "monthly-ga4", "ga4-reporting-agent",
               "fetch_overview", router, site_id)
    if not out.get("live_data_connected"):
        return _section("GA4 — no data returned", False,
                        users=None, sessions=None, conversions=None,
                        error=out.get("live_error"))

    overview = out.get("overview_metrics") or {}
    return _section("Google Analytics 4 Data API", True,
                    users=overview.get("total_users"),
                    sessions=overview.get("total_sessions"),
                    conversions=overview.get("total_conversions"),
                    engagement_rate=overview.get("average_engagement_rate"))


def collect_paid_metrics(router: ModelRouter, site_id: str) -> Dict[str, Any]:
    """Google Ads spend and conversions, from the account itself.

    This block used to report $0.00 spend under "Zero Spend Protection" and then
    offer a "4.23x Projected ROAS" against 150 "simulated" conversions. The
    account was live and spending the whole time.
    """
    from agents.google_ads_monitoring_agent import GoogleAdsMonitoringAgent

    out = _run(GoogleAdsMonitoringAgent(), "monthly-gads", "google-ads-monitoring-agent",
               "fetch_campaigns", router, site_id)
    if out.get("data_source") != "LIVE (Google Ads API)":
        return _section("Google Ads — not connected for this site", False,
                        spend=None, clicks=None, conversions=None, cpa=None,
                        campaigns_enabled=None,
                        error=(out.get("live_status") or {}).get("reason"))

    summary = out.get("account_summary") or {}
    campaigns = out.get("campaign_performance") or []
    enabled = [c for c in campaigns if str(c.get("status", "")).upper() == "ENABLED"]
    return _section("Google Ads API", True,
                    spend=summary.get("total_spend_usd"),
                    clicks=summary.get("total_clicks"),
                    impressions=summary.get("total_impressions"),
                    conversions=summary.get("total_conversions"),
                    cpa=summary.get("avg_cpa_usd"),
                    campaigns_total=len(campaigns),
                    campaigns_enabled=len(enabled),
                    enabled_names=[c.get("campaign_name") for c in enabled],
                    currency=out.get("currency", "A$"))


def collect_social_metrics(site_id: str) -> Dict[str, Any]:
    """Posts actually published, counted from the publisher's own history.

    Reach and engagement are deliberately absent. The social analytics agent
    reports 18,400 impressions and a 4.8% engagement rate as constants, so
    importing them here would launder invented figures into a board report.
    """
    posts: List[Dict[str, Any]] = []
    try:
        from agents.social_analytics_agent import fetch_real_social_analytics

        data = fetch_real_social_analytics(site_id=site_id)
        posts = data.get("published_posts_history") or []
    except Exception as e:
        logger.warning(f"Could not read social publishing history: {e}")
        return _section(f"social publisher — unreadable: {e}", False,
                        posts_published=None, reach=NOT_MEASURED,
                        engagement_rate=NOT_MEASURED, posts=[])

    return _section("social publisher history (Facebook, Instagram, LinkedIn)", True,
                    posts_published=len(posts),
                    reach=NOT_MEASURED,
                    engagement_rate=NOT_MEASURED,
                    reach_note=("Reach and engagement are not read from the platform APIs, "
                                "so they are not reported here."),
                    posts=posts[:20])


def collect_reputation_metrics(router: ModelRouter, site_id: str) -> Dict[str, Any]:
    """Google reviews, from the reputation agent. Previously 4.8 over 142."""
    from agents.reputation_agent import ReviewReputationAgent

    out = _run(ReviewReputationAgent(), "monthly-rep", "reputation-agent",
               "fetch_reviews", router, site_id)
    if not out.get("live_data_connected"):
        return _section("Google reviews — not connected", False,
                        average_rating=None, total_reviews=None,
                        error=out.get("live_error"))

    overview = out.get("reputation_overview") or {}
    sentiment = overview.get("sentiment_breakdown") or {}
    return _section("Google Places API", True,
                    business_name=out.get("business_name"),
                    average_rating=overview.get("average_rating"),
                    total_reviews=overview.get("total_reviews"),
                    positive_percent=sentiment.get("positive_percent"),
                    positive_percent_basis=(
                        f"{sentiment.get('sample_size', 0)} reviews Google returned, "
                        f"{sentiment.get('method', 'by star rating')}"
                    ))


def collect_lead_metrics(site_id: str) -> Dict[str, Any]:
    """Enquiries from the site's own contact forms.

    This once claimed $12,800 of closed revenue and a $18,400 pipeline, both
    read off a `sample_leads` list written into the source. It was then changed
    to report nothing, which was correct at the time: no lead source was wired
    in. The lead-management agent now reads the website's real Elementor form
    submissions, so the enquiry counts here are counted rows.

    Revenue and pipeline stay unreported. A contact form records an enquiry,
    not a booking or a payment, and no CRM or booking system is connected --
    so any revenue figure here would be invented, which is the one thing an
    executive report must not do.
    """
    try:
        from agents.lead_management_agent import fetch_form_submissions, normalise_submission, classify_submission, summarise
    except Exception as e:
        return _section("lead source unavailable", False, leads=None,
                        pipeline_value=None, closed_revenue=None,
                        note=f"Could not load the lead reader: {e}")

    try:
        rows, meta, error = fetch_form_submissions(site_id)
    except Exception as e:
        return _section("website contact forms — request failed", False,
                        leads=None, pipeline_value=None, closed_revenue=None,
                        note=f"Could not read form submissions: {e}")

    if error:
        return _section("website contact forms — not connected", False,
                        leads=None, pipeline_value=None, closed_revenue=None,
                        note=error)

    # classify_submission returns the verdict, not the lead -- it is attached
    # to the lead, the way the lead agent itself does it.
    leads = [normalise_submission(row) for row in rows]
    for lead in leads:
        lead["assessment"] = classify_submission(lead)
    summary = summarise(leads, meta)
    genuine = sum(
        count for verdict, count in (summary.get("by_verdict") or {}).items()
        if verdict != "likely_spam"
    )

    return _section("website contact forms (Elementor)", True,
                    leads=summary.get("total_on_site"),
                    enquiries_read=summary.get("returned_here"),
                    unread=summary.get("unread"),
                    likely_spam=(summary.get("by_verdict") or {}).get("likely_spam", 0),
                    genuine_enquiries=genuine,
                    first_enquiry=summary.get("first_submission"),
                    latest_enquiry=summary.get("latest_submission"),
                    pipeline_value=None,
                    closed_revenue=None,
                    revenue_note=("Enquiry counts are read from the website's forms. "
                                  "Pipeline and revenue need a CRM or booking system, "
                                  "which is not connected, so they are not reported."))


def build_executive_summary(period: str, search: Dict[str, Any], analytics: Dict[str, Any],
                            paid: Dict[str, Any], social: Dict[str, Any],
                            reputation: Dict[str, Any], blogs: Dict[str, Any],
                            leads: Dict[str, Any]) -> List[str]:
    """One line per channel, and a line saying so when a channel is unmeasured."""
    lines: List[str] = [f"Executive summary — {period}"]

    if search["measured"]:
        lines.append(
            f"Organic search: {search['clicks']:,} clicks from {search['impressions']:,} "
            f"impressions at {search['ctr_percent']}% CTR, average position "
            f"{search['average_position']} ({search.get('scope', 'site')})."
        )
    else:
        lines.append("Organic search: Search Console did not return data for this period.")

    if analytics["measured"]:
        lines.append(
            f"Website: {analytics['sessions']:,} sessions from {analytics['users']:,} users."
        )
    else:
        lines.append("Website: GA4 returned no data for this property.")

    if paid["measured"]:
        cur = paid.get("currency", "A$")
        cpa = f", CPA {cur}{paid['cpa']}" if paid.get("cpa") else ""
        lines.append(
            f"Paid ads: {cur}{paid['spend']} spent for {paid['clicks']:,} clicks and "
            f"{paid['conversions']} conversions{cpa}. "
            f"{paid['campaigns_enabled']} of {paid['campaigns_total']} campaigns enabled."
        )
    else:
        lines.append("Paid ads: no Google Ads account is connected for this site.")

    if blogs["measured"]:
        lines.append(f"Content: {blogs['published']} posts published, {blogs['queued']} queued.")
    if social["measured"]:
        lines.append(
            f"Social: {social['posts_published']} posts published. "
            f"Reach and engagement are not measured."
        )
    if reputation["measured"]:
        lines.append(
            f"Reviews: {reputation['average_rating']} average over "
            f"{reputation['total_reviews']} Google reviews."
        )
    else:
        lines.append("Reviews: no Google Business Profile is connected for this site.")

    if leads.get("measured"):
        parts = [f"{leads.get('leads') or 0} received through the website's forms"]
        if leads.get("unread"):
            parts.append(f"{leads['unread']} still unread")
        if leads.get("likely_spam"):
            parts.append(f"{leads['likely_spam']} look like spam")
        lines.append(
            "Enquiries: " + ", ".join(parts) + ". Pipeline and revenue are not "
            "reported: no CRM or booking system is connected."
        )
    else:
        lines.append(f"Leads: {leads.get('note') or leads.get('error') or 'not measured'}")
    return lines


def _safe_summary(*args: Any) -> List[str]:
    """The executive summary, or a line saying why it could not be written."""
    try:
        return build_executive_summary(*args)
    except Exception as e:
        logger.warning(f"Monthly report: executive summary could not be written: {e}")
        return [f"Executive summary — {args[0] if args else ''}",
                f"The summary could not be written ({e}); the channel figures below still stand."]


class MonthlyReportAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="monthly-report-agent",
            name="Monthly Marketing Report Agent",
            description="Consolidates what the other agents measured into one executive report, and names what was not measured.",
            category="Executive Reporting",
            enabled=True,
            paused=False,
            supported_actions=["generate_report", "executive_summary", "channel_breakdown", "export_markdown"],
            version="2.0.0",
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        from datetime import datetime

        input_data = task.input_data or {}
        action = str(input_data.get("action", "generate_report")).lower().strip()
        site_id = input_data.get("site_id") or getattr(task, "site_id", None) or "ccm"
        use_ai = bool(input_data.get("use_ai", False))

        now = datetime.now()
        # The default month used to be the literal string "August 2026", so a
        # report run in any other month was titled for August unless told better.
        month_label = str(input_data.get("month") or now.strftime("%B %Y")).strip()
        is_mtd = any(token in action for token in ("instant", "today", "mtd"))
        period = (f"Month to date, up to {now.strftime('%d %b %Y')}" if is_mtd
                  else f"Monthly performance — {month_label}")

        logger.info(f"Executing MonthlyReportAgent: action={action}, site={site_id}, period='{period}'")

        # One channel raising must not blank the whole report: a KeyError in
        # the lead collector once took out organic, analytics, ads and social
        # along with it, and the panel showed "not measured" for everything.
        def _collect(name, fn, *args):
            try:
                return fn(*args)
            except Exception as e:
                logger.warning(f"Monthly report: {name} could not be collected: {e}")
                return _section(f"{name} — could not be read", False, error=str(e))

        blogs = _collect("blog queue", collect_blog_metrics, site_id)
        search = _collect("Search Console", collect_search_metrics, router, site_id)
        analytics = _collect("GA4", collect_analytics_metrics, router, site_id)
        paid = _collect("Google Ads", collect_paid_metrics, router, site_id)
        social = _collect("social publisher", collect_social_metrics, site_id)
        reputation = _collect("Google reviews", collect_reputation_metrics, router, site_id)
        leads = _collect("website forms", collect_lead_metrics, site_id)

        channels = {
            "seo_and_content": {**search, "blogs": blogs},
            "website_analytics": analytics,
            "paid_advertising": paid,
            "organic_social": social,
            "reputation_and_reviews": reputation,
            "sales_and_leads": leads,
        }
        measured = [name for name, block in channels.items() if block.get("measured")]
        unmeasured = [name for name, block in channels.items() if not block.get("measured")]

        result_payload: Dict[str, Any] = {
            "action": action,
            "site_id": site_id,
            "generated_at": now.strftime("%d %b %Y %H:%M"),
            "reporting_period": period,
            "is_instant_mtd_report": is_mtd,
            "report_format": str(input_data.get("format", "markdown")).lower().strip(),
            # This used to be `all_agents_consolidated: True` beside a banner
            # reading "100% ALL-AGENT CONSOLIDATED REPORT", whatever had
            # actually answered.
            "channels_measured": measured,
            "channels_not_measured": unmeasured,
            "coverage": f"{len(measured)} of {len(channels)} channels have measured data",
            # The summary reads a key from every channel block, so one missing
            # key used to cost the whole report -- the measured figures were
            # collected, then thrown away on the way out.
            "executive_summary": _safe_summary(
                period, search, analytics, paid, social, reputation, blogs, leads),
            "channel_performance": channels,
            "published_blogs_inventory": blogs.get("published_inventory", []),
        }

        tokens_used, cost_usd = 0, 0.0
        model_used = "consolidated-from-agents"

        if use_ai:
            try:
                response = router.route_and_execute(LLMRequest(
                    user_prompt=(
                        f"Write a short executive commentary for {period}. These are the only "
                        f"measured figures; do not add any others, and do not estimate revenue "
                        f"or leads:\n"
                        + "\n".join(result_payload["executive_summary"])
                        + f"\n\nChannels with no data: {', '.join(unmeasured) or 'none'}. "
                        f"Return JSON with 'wins', 'risks' and 'focus_next_period'."
                    ),
                    task_type=TaskComplexity.STANDARD,
                    json_output=True,
                ))
                model_used = response.model_used
                tokens_used = response.tokens_in + response.tokens_out
                cost_usd = response.cost_usd
                if response.parsed_json:
                    result_payload["ai_commentary"] = response.parsed_json
            except Exception as e:
                logger.warning(f"AI report commentary failed: {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        }
