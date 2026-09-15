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
# The list endpoint returns only each submission's "main" field -- the email
# address -- so reading it alone made every enquiry look like an address and
# nothing else. The name, the message and the rest are on the per-submission
# endpoint, and they were there the whole time.
DETAIL_PATH = "/wp-json/elementor/v1/form-submissions/{submission_id}"
DETAIL_LIMIT = 60
FETCH_TIMEOUT_SECONDS = 25
PAGE_SIZE = 10
# A ceiling on pages, so a misbehaving endpoint cannot spin here forever.
MAX_PAGES = 50


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

    # Fetched a page at a time rather than in one large request. The page size
    # is deliberately small; the loop is what makes sure every submission is
    # still read, so a smaller page never means fewer leads shown.
    rows: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {}
    page = 1

    while page <= MAX_PAGES:
        try:
            res = requests.get(
                base + SUBMISSIONS_PATH,
                params={
                    "per_page": PAGE_SIZE,
                    "page": page,
                    "order": "desc",
                    "orderby": "created_at",
                },
                auth=(user, password),
                timeout=FETCH_TIMEOUT_SECONDS,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Marketing-Dashboard)"},
            )
        except Exception as e:
            if rows:
                break  # keep what was already read rather than losing the lot
            return [], None, f"Could not reach WordPress: {e}"

        if res.status_code == 401:
            return [], None, "WordPress rejected the credentials (401). Check the application password."
        if res.status_code == 404:
            return [], None, (
                "This WordPress site has no Elementor Pro form-submissions endpoint. "
                "Submissions can only be read if Elementor Pro is active and storing them."
            )
        if res.status_code != 200:
            if rows:
                break
            return [], None, f"WordPress returned HTTP {res.status_code} for form submissions."

        try:
            payload = res.json()
        except Exception as e:
            if rows:
                break
            return [], None, f"WordPress returned a response that could not be read: {e}"

        batch = payload.get("data") or []
        rows.extend(batch)
        # The first page's meta carries the totals for the whole set.
        if page == 1:
            meta = payload.get("meta") or {}

        last_page = ((payload.get("meta") or {}).get("pagination") or {}).get("last_page")
        if len(batch) < PAGE_SIZE or (last_page and page >= last_page):
            break
        page += 1

    _enrich_with_details(base, (user, password), rows)
    return rows, meta, None


def _enrich_with_details(base: str, auth: Tuple[str, str], rows: List[Dict[str, Any]]) -> None:
    """Replace each row's single-field `values` with everything it captured.

    Done in place, and best-effort: a submission whose detail cannot be read
    keeps the one field the list gave, rather than the whole report failing.
    """
    import requests

    for row in rows[:DETAIL_LIMIT]:
        submission_id = row.get("id")
        if not submission_id:
            continue
        try:
            res = requests.get(
                base + DETAIL_PATH.format(submission_id=submission_id),
                auth=auth,
                timeout=FETCH_TIMEOUT_SECONDS,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Marketing-Dashboard)"},
            )
            if res.status_code != 200:
                continue
            payload = res.json()
            detail = payload.get("data") if isinstance(payload, dict) else None
            detail = detail if isinstance(detail, dict) else payload
            values = (detail or {}).get("values")
            if values:
                row["values"] = values
        except Exception as e:
            logger.warning(f"Could not read submission {submission_id}: {e}")


def normalise_submission(row: Dict[str, Any]) -> Dict[str, Any]:
    """One submission, carrying only the fields the form actually captured."""
    fields = {
        str(v.get("key")): v.get("value")
        for v in (row.get("values") or [])
        if v.get("key")
    }
    form = row.get("form") or {}

    def first(*names: str) -> Optional[str]:
        for name in names:
            value = fields.get(name)
            if value and str(value).strip():
                return str(value).strip()
        return None

    # Elementor names a field the operator never labelled "field_<hash>". Those
    # carry real answers -- a surname, a confirmed email -- so they are kept,
    # but they are not guessed at.
    named = {k: v for k, v in fields.items() if not k.startswith("field_")}
    unlabelled = {k: v for k, v in fields.items() if k.startswith("field_") and str(v or "").strip()}

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
        "named_fields": named,
        "unlabelled_fields": unlabelled,
        "email": first("email", "Email", "your-email"),
        "name": first("name", "Name", "your-name", "full_name", "first_name"),
        "phone": first("phone", "Phone", "tel", "telephone", "mobile", "your-phone"),
        "message": first("message", "Message", "your-message", "comments", "enquiry", "details"),
    }


# Phrases lifted from the submissions themselves. Every one of the flagged
# enquiries on this site asks to join a mailing list; none of them mentions a
# journey.
NEWSLETTER_PHRASES = (
    "mailing list", "email updates", "subscribe", "subscription", "newsletter",
    "product news", "news about new content", "stay informed", "keep me posted",
    "please confirm my", "receive emails", "hear more about email",
)

# What somebody booking a car actually writes about.
SERVICE_TERMS = (
    "airport", "transfer", "chauffeur", "pickup", "pick up", "drop off", "wedding",
    "corporate", "hire", "booking", "book", "quote", "passenger", "flight", "tour",
    "melbourne", "cbd", "tullamarine", "car", "van", "sprinter", "hourly", "trip",
)

LOCATION_FIELDS = ("pickuplocations", "pickup", "pickup_location",
                   "dropofflocation", "dropoff", "drop_off_location")


def classify_submission(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Judge whether an enquiry looks genuine, with the reasons shown.

    A heuristic, and labelled as one. It never deletes or hides anything: a
    wrongly flagged enquiry is a lost customer, so the operator sees every
    submission and the reasoning behind each verdict.
    """
    reasons_spam: List[str] = []
    reasons_genuine: List[str] = []
    score = 0

    message = (lead.get("message") or "").strip()
    lower = message.lower()
    fields = lead.get("fields") or {}
    filled = {k: v for k, v in fields.items() if str(v or "").strip() and str(v).strip().lower() != "none"}

    matched_newsletter = [p for p in NEWSLETTER_PHRASES if p in lower]
    if matched_newsletter:
        score += 3
        reasons_spam.append(f"asks to join a mailing list ({matched_newsletter[0]!r})")

    if message and not any(term in lower for term in SERVICE_TERMS):
        score += 2
        reasons_spam.append("the message mentions no journey, vehicle or booking")

    locations = [v for k, v in filled.items() if k.lower() in LOCATION_FIELDS]
    if locations:
        score -= 4
        reasons_genuine.append(f"gave a pickup or drop-off location ({locations[0][:40]})")

    if len(filled) <= 5:
        score += 1
        reasons_spam.append(f"only {len(filled)} fields were filled in")
    elif len(filled) >= 9:
        score -= 2
        reasons_genuine.append(f"filled in {len(filled)} fields")

    name = (lead.get("name") or "").strip().lower()
    email = (lead.get("email") or "").strip().lower()
    if name and email and "@" in email and len(name) > 2 and name not in email.split("@")[0]:
        score += 1
        reasons_spam.append("the name does not appear anywhere in the email address")

    if score >= 4:
        verdict = "likely_spam"
    elif score <= -2:
        verdict = "likely_genuine"
    else:
        verdict = "unclear"

    return {
        "verdict": verdict,
        "score": score,
        "reasons_spam": reasons_spam,
        "reasons_genuine": reasons_genuine,
        "method": "heuristic on the message text and which fields were filled — not a spam service",
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

    verdicts: Dict[str, int] = {}
    for lead in leads:
        verdict = (lead.get("assessment") or {}).get("verdict", "unclear")
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
    worth_reading = [
        lead for lead in leads
        if (lead.get("assessment") or {}).get("verdict") != "likely_spam"
        and not lead.get("is_read")
    ]

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
        "by_verdict": verdicts,
        "unread_worth_reading": len(worth_reading),
        "verdict_note": (
            "Spam is flagged by a heuristic on the message text and which fields were filled, "
            "not by a spam service. Nothing is hidden or deleted; check anything marked unclear."
        ),
    }


def build_recommendations(leads: List[Dict[str, Any]], summary: Dict[str, Any]) -> List[str]:
    """Advice drawn from these submissions, not written in advance."""
    out: List[str] = []
    if not leads:
        return ["No form submissions have been received yet."]

    spam_count = summary.get("by_verdict", {}).get("likely_spam", 0)
    if summary.get("unread_worth_reading"):
        out.append(
            f"{summary['unread_worth_reading']} unread enquiries do not look like spam. "
            f"Those are the ones to read; {spam_count} of the {summary['total_on_site']} "
            f"submissions are mailing-list spam."
        )
    elif summary["unread"]:
        out.append(
            f"All {summary['unread']} unread submissions look like mailing-list spam. "
            f"Nothing here needs a reply."
        )

    if spam_count >= 5:
        out.append(
            f"{spam_count} spam submissions arrived through the website form. Turn on "
            f"reCAPTCHA in Elementor (Elementor > Settings > Integrations) and add the "
            f"reCAPTCHA field to each form -- the honeypot plugin on this site is not "
            f"stopping them."
        )

    captured = summary["fields_captured"]
    missing = [f for f in ("phone", "date") if f not in captured]
    if missing:
        out.append(
            f"The forms capture {', '.join(captured) or 'nothing'} but not "
            f"{', '.join(missing)}. Adding a phone field in Elementor would let you call "
            f"back rather than waiting on email."
        )

    with_message = [lead for lead in leads if lead.get("message")]
    if with_message:
        out.append(
            f"{len(with_message)} of {len(leads)} enquiries wrote a message explaining what "
            f"they wanted. Read those first -- they say more than the email address does."
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
        for lead in leads:
            lead["assessment"] = classify_submission(lead)
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
