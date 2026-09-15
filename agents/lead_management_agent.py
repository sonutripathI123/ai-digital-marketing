"""
Agent #14: Lead Management Agent (`lead-management-agent`).

Reads the form submissions the website actually received, through the Elementor
Pro submissions API, and reports what each one contains.

The version this replaces invented its entire pipeline. Two people who do not
exist -- "James Thornton (BHP Group)" and "Emma Watson" -- with made-up email
addresses, made-up Australian mobile numbers, routes, an $1,850 pipeline, lead
scores of 95 and 88 out of 100 and a "VIP CORPORATE ACCOUNT" tier. BHP Group is
a real company; the report named it as a client of this business. Those figures
were also read by the monthly executive report, which turned them into
"$12,800 AUD of closed revenue" in a document with a PDF export button.

What this agent will not do:

  * It will not score a lead. A score out of 100 implies a model fitted to
    outcomes; there is no outcome data here, and the old 95/100 was a literal.
  * It will not estimate a lead's value. Nothing in a form submission says what
    a booking is worth, and inventing that number is what produced the revenue
    claim above.
  * It will not send anything. Follow-up text is a draft to copy.
"""

from typing import Any, Dict, List, Optional, Tuple

from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("lead-management-agent")

SUBMISSIONS_PATH = "/wp-json/elementor/v1/form-submissions"
FETCH_TIMEOUT_SECONDS = 25
MAX_SUBMISSIONS = 100


def resolve_wordpress_credentials(site_id: str) -> Dict[str, str]:
    """WordPress credentials for this site.

    Falls back to the blog agent's credentials for the same site, since that is
    where operators have already entered them and they address the same site.
    """
    creds: Dict[str, str] = {}
    try:
        from config.websites import WebsiteManager

        manager = WebsiteManager()
        for agent_id in ("lead-management-agent", "blog-agent"):
            saved = manager.get_agent_credentials(site_id, agent_id) or {}
            for key in ("wp_url", "wp_username", "wp_app_password"):
                if saved.get(key) and not creds.get(key):
                    creds[key] = str(saved[key]).strip()
        if not creds.get("wp_url"):
            profile = manager.get(site_id)
            if profile and profile.domain:
                creds["wp_url"] = profile.domain
    except Exception as e:
        logger.warning(f"Could not read WordPress credentials for {site_id}: {e}")
    return creds


def fetch_form_submissions(site_id: str) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    """Read submissions from Elementor. Returns (rows, pagination_meta, error)."""
    import requests

    creds = resolve_wordpress_credentials(site_id)
    base = (creds.get("wp_url") or "").rstrip("/")
    user = creds.get("wp_username")
    # WordPress shows application passwords in spaced groups; the spaces are
    # display only and must not be sent.
    password = (creds.get("wp_app_password") or "").replace(" ", "")

    if not base:
        return [], None, "No WordPress URL is configured for this site."
    if not (user and password):
        return [], None, (
            "No WordPress username or application password is saved for this site, "
            "so the form submissions cannot be read."
        )

    try:
        res = requests.get(
            base + SUBMISSIONS_PATH,
            params={"per_page": MAX_SUBMISSIONS, "order": "desc", "orderby": "created_at"},
            auth=(user, password),
            timeout=FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Marketing-Dashboard)"},
        )
    except Exception as e:
        return [], None, f"Could not reach WordPress: {e}"

    if res.status_code == 401:
        return [], None, "WordPress rejected the credentials (401). Check the application password."
    if res.status_code == 404:
        return [], None, (
            "This WordPress site has no Elementor Pro form-submissions endpoint. "
            "Submissions can only be read if Elementor Pro is active and storing them."
        )
    if res.status_code != 200:
        return [], None, f"WordPress returned HTTP {res.status_code} for form submissions."

    try:
        payload = res.json()
    except Exception as e:
        return [], None, f"WordPress returned a response that could not be read: {e}"

    return payload.get("data") or [], payload.get("meta") or {}, None


def normalise_submission(row: Dict[str, Any]) -> Dict[str, Any]:
    """One submission, carrying only the fields the form actually captured."""
    fields = {
        str(v.get("key")): v.get("value")
        for v in (row.get("values") or [])
        if v.get("key")
    }
    form = row.get("form") or {}
    return {
        "id": row.get("id"),
        "submitted_at": row.get("created_at"),
        "submitted_at_gmt": row.get("created_at_gmt"),
        "form_name": form.get("name"),
        "page_title": row.get("referer_title"),
        "page_url": row.get("referer"),
        "status": row.get("status"),
        "is_read": bool(row.get("is_read")),
        # Whatever the form collected, under its own field names. The old
        # payload had client_name, phone, service_type, route, estimated_value
        # and tier for every lead; this form captures an email address and
        # nothing else, so those keys would have had to be filled in.
        "fields": fields,
        "email": fields.get("email") or fields.get("Email"),
    }


def summarise(leads: List[Dict[str, Any]], meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Counts and coverage, all of it derived from the rows just read."""
    by_form: Dict[str, int] = {}
    by_page: Dict[str, int] = {}
    captured_fields: Dict[str, int] = {}
    for lead in leads:
        by_form[lead["form_name"] or "unnamed form"] = by_form.get(lead["form_name"] or "unnamed form", 0) + 1
        by_page[lead["page_title"] or "unknown page"] = by_page.get(lead["page_title"] or "unknown page", 0) + 1
        for key in lead["fields"]:
            captured_fields[key] = captured_fields.get(key, 0) + 1

    pagination = (meta or {}).get("pagination") or {}
    counts = (meta or {}).get("count") or {}
    unread = counts.get("unread")
    if unread is None:
        unread = len([lead for lead in leads if not lead["is_read"]])

    dates = sorted(lead["submitted_at"] for lead in leads if lead.get("submitted_at"))

    return {
        "total_on_site": pagination.get("total", len(leads)),
        "returned_here": len(leads),
        "unread": unread,
        "read": counts.get("read", len(leads) - unread if leads else 0),
        "first_submission": dates[0] if dates else None,
        "latest_submission": dates[-1] if dates else None,
        "by_form": by_form,
        "by_page": by_page,
        "fields_captured": sorted(captured_fields),
    }


def build_recommendations(leads: List[Dict[str, Any]], summary: Dict[str, Any]) -> List[str]:
    """Advice drawn from these submissions, not written in advance."""
    out: List[str] = []
    if not leads:
        return ["No form submissions have been received yet."]

    if summary["unread"]:
        out.append(
            f"{summary['unread']} of {summary['total_on_site']} submissions are still marked unread "
            f"in WordPress. The oldest unread one dates from {summary['first_submission']}."
        )

    captured = summary["fields_captured"]
    missing = [f for f in ("name", "phone", "message", "date") if f not in captured]
    if missing:
        out.append(
            f"Every submission captured only: {', '.join(captured) or 'nothing'}. "
            f"The forms do not collect {', '.join(missing)}, so there is no way to call "
            f"these people back or know what they wanted. Adding those fields is worth "
            f"more than anything this agent can do with the data as it stands."
        )

    if len(summary["by_form"]) > 1:
        busiest = max(summary["by_form"].items(), key=lambda kv: kv[1])
        out.append(
            f"{busiest[1]} of {len(leads)} came through '{busiest[0]}'. "
            f"Check that each form sends you an email notification."
        )

    generic = [name for name in summary["by_form"] if name and name.strip().lower() in ("new form", "form")]
    if generic:
        out.append(
            f"A form is still named {generic[0]!r}. Naming it after the page it sits on makes "
            f"these submissions traceable to the page that produced them."
        )
    return out


class LeadManagementAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="lead-management-agent",
            name="Lead Management Agent",
            description="Reads the website's real form submissions from WordPress and reports what each one contains.",
            category="Sales & CRM",
            enabled=True,
            paused=False,
            supported_actions=["process_lead", "score_lead", "draft_followup", "lead_report"],
            version="2.0.0",
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "lead_report")).lower().strip()
        site_id = input_data.get("site_id") or getattr(task, "site_id", None) or "ccm"
        use_ai = bool(input_data.get("use_ai", False))

        logger.info(f"Executing LeadManagementAgent: action={action}, site={site_id}")

        # ---- Drafting a reply to one submission ----
        if action == "draft_followup":
            email = str(input_data.get("email", "")).strip()
            context = str(input_data.get("context", "")).strip()
            if not email:
                return {
                    "output": {
                        "action": action,
                        "error": "No email address was given, so nothing was drafted.",
                        "draft_email": None,
                    },
                    "model_used": "none", "tokens_used": 0, "cost_usd": 0.0,
                }

            draft, method, model_used = None, None, "template"
            tokens_used, cost_usd = 0, 0.0
            if use_ai:
                try:
                    response = router.route_and_execute(LLMRequest(
                        user_prompt=(
                            f"Write a short first reply to a website enquiry from {email}. "
                            f"{'Context: ' + context if context else 'The form captured only their email address, so nothing about what they want is known.'} "
                            f"Ask what they need rather than assuming. No prices, no invented "
                            f"details, no claims about the service. Plain text."
                        ),
                        task_type=TaskComplexity.STANDARD,
                        json_output=False,
                    ))
                    draft = (response.content or "").strip()
                    model_used = response.model_used
                    tokens_used = response.tokens_in + response.tokens_out
                    cost_usd = response.cost_usd
                    method = f"written by {model_used}"
                except Exception as e:
                    logger.warning(f"AI follow-up drafting failed: {e}")

            if not draft:
                # The template this replaces quoted a price -- "Estimated
                # Investment: $250.00 AUD" -- and named vehicles, for an enquiry
                # whose contents nobody knew.
                draft = (
                    "Hello,\n\n"
                    "Thank you for getting in touch through our website. So that we can quote "
                    "accurately, could you let us know the date, the pickup and drop-off "
                    "locations, and how many passengers?\n\n"
                    "Kind regards,\nCorporate Cars Melbourne"
                )
                method = "generic template — no model ran"

            return {
                "output": {
                    "action": action,
                    "to": email,
                    "draft_email": draft,
                    "draft_method": method,
                    "can_send_from_here": False,
                    "send_note": "This is a draft to copy. No email is sent from this dashboard.",
                },
                "model_used": model_used, "tokens_used": tokens_used, "cost_usd": cost_usd,
            }

        # ---- Reading the submissions ----
        rows, meta, error = fetch_form_submissions(site_id)
        if error:
            return {
                "output": {
                    "action": action,
                    "live_data_connected": False,
                    "data_source": "NOT CONNECTED — form submissions could not be read",
                    "live_error": error,
                    "pipeline_summary": {
                        "total_on_site": 0, "returned_here": 0, "unread": 0,
                        "fields_captured": [],
                    },
                    "recent_leads": [],
                    "actionable_recommendations": [f"Fix the connection: {error}"],
                },
                "model_used": "none — not connected", "tokens_used": 0, "cost_usd": 0.0,
            }

        leads = [normalise_submission(row) for row in rows]
        summary = summarise(leads, meta)

        result_payload: Dict[str, Any] = {
            "action": action,
            "site_id": site_id,
            "live_data_connected": True,
            "data_source": "LIVE — Elementor Pro form submissions (WordPress)",
            "live_error": None,
            "pipeline_summary": summary,
            # Deliberately absent: lead_score, tier, estimated_value_usd and
            # total_pipeline_value_usd. Nothing in a submission supports any of
            # them, and the monthly report read them as revenue.
            "scoring_note": (
                "No lead score or deal value is shown. A form submission carries no "
                "information that would support either, and the figures that used to "
                "appear here were written into the source."
            ),
            "recent_leads": leads[:40],
            "actionable_recommendations": build_recommendations(leads, summary),
        }

        tokens_used, cost_usd = 0, 0.0
        model_used = "wordpress-form-submissions"

        if use_ai and leads:
            try:
                response = router.route_and_execute(LLMRequest(
                    user_prompt=(
                        f"A chauffeur business received {summary['total_on_site']} website form "
                        f"submissions. Each one captured only these fields: "
                        f"{', '.join(summary['fields_captured']) or 'none'}. They came through "
                        f"these forms: {summary['by_form']}. {summary['unread']} are unread. "
                        f"Return JSON with 'risks' and 'next_steps' for handling these enquiries. "
                        f"Do not invent lead values, names or scores."
                    ),
                    task_type=TaskComplexity.STANDARD,
                    json_output=True,
                ))
                model_used = response.model_used
                tokens_used = response.tokens_in + response.tokens_out
                cost_usd = response.cost_usd
                if response.parsed_json:
                    result_payload["ai_analysis"] = response.parsed_json
            except Exception as e:
                logger.warning(f"AI lead analysis failed: {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        }
