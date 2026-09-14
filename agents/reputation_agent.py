"""
Agent #13: Review / Reputation Agent (`reputation-agent`).

Reads the business's Google reviews through the Google Places API and
summarises what they say. It reports only what the API returns.

What this agent cannot do, and does not pretend to do:

  * It cannot post a reply. The Places API is read-only; publishing a reply
    needs Google Business Profile API access, which is a separate application
    and OAuth as the business owner. Replies here are drafts to paste.
  * It cannot see every review. Google returns the overall rating, the total
    review count, and at most five recent reviews. A star distribution can
    therefore only be counted across those five, never across all of them, and
    is labelled that way.
  * It reads Google only. TripAdvisor and Trustpilot are not connected.

The version this replaces returned a fixed 4.8 rating over 142 reviews with
three invented reviewers -- "David Miller", "Sarah Jenkins", "Michael Chang" --
their review text, their star ratings and replies supposedly already sent. None
of it came from anywhere. Shown beside a "LIVE BRAND REPUTATION SENTINEL"
badge, it was indistinguishable from a real reputation report.
"""

from typing import Any, Dict, List, Optional, Tuple

from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("reputation-agent")

PLACES_ENDPOINT = "https://places.googleapis.com/v1/places/{place_id}"
PLACES_FIELDS = "id,displayName,rating,userRatingCount,googleMapsUri,reviews"
FETCH_TIMEOUT_SECONDS = 15


def resolve_place_credentials(
    explicit: Optional[Dict[str, Any]] = None,
    site_id: Optional[str] = None,
) -> Dict[str, str]:
    """Place ID and API key, from the task, the site's saved credentials, or env."""
    import os

    creds: Dict[str, str] = {}
    for key in ("place_id", "api_key", "business_name"):
        value = (explicit or {}).get(key)
        if value:
            creds[key] = str(value).strip()

    if site_id and not (creds.get("place_id") and creds.get("api_key")):
        try:
            from config.websites import WebsiteManager

            saved = WebsiteManager().get_agent_credentials(site_id, "reputation-agent") or {}
            for key in ("place_id", "api_key", "business_name"):
                if saved.get(key) and not creds.get(key):
                    creds[key] = str(saved[key]).strip()
        except Exception as e:
            logger.warning(f"Could not read saved reputation credentials for {site_id}: {e}")

    for env_name, key in (
        ("GOOGLE_PLACES_API_KEY", "api_key"),
        ("GOOGLE_MAPS_API_KEY", "api_key"),
        ("GOOGLE_PLACE_ID", "place_id"),
    ):
        if not creds.get(key) and os.getenv(env_name):
            creds[key] = os.getenv(env_name, "").strip()

    return creds


SEARCH_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
SEARCH_FIELDS = "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount"


def search_places(query: str, api_key: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Find candidate places by name, so the Place ID need not be copied by hand.

    Returns (candidates, error). An empty list with no error means Google found
    nothing matching -- which is an answer, not a failure to be papered over.
    """
    import requests

    try:
        res = requests.post(
            SEARCH_ENDPOINT,
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": SEARCH_FIELDS,
                "Content-Type": "application/json",
            },
            json={"textQuery": query},
            timeout=FETCH_TIMEOUT_SECONDS,
        )
    except Exception as e:
        return [], f"Could not reach the Google Places API: {e}"

    if res.status_code != 200:
        detail = ""
        try:
            detail = res.json().get("error", {}).get("message", "")
        except Exception:
            detail = res.text[:200]
        return [], f"Google Places search returned HTTP {res.status_code}. {detail}".strip()

    try:
        places = res.json().get("places") or []
    except Exception as e:
        return [], f"Google Places search returned a response that could not be read: {e}"

    return [
        {
            "place_id": p.get("id"),
            "name": (p.get("displayName") or {}).get("text"),
            "address": p.get("formattedAddress"),
            "rating": p.get("rating"),
            "total_reviews": p.get("userRatingCount"),
        }
        for p in places
        if p.get("id")
    ], None


def fetch_google_reviews(place_id: str, api_key: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Call the Places API. Returns (payload, error) -- never a stand-in for one."""
    import requests

    try:
        res = requests.get(
            PLACES_ENDPOINT.format(place_id=place_id),
            headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": PLACES_FIELDS},
            timeout=FETCH_TIMEOUT_SECONDS,
        )
    except Exception as e:
        return None, f"Could not reach the Google Places API: {e}"

    if res.status_code == 403:
        return None, (
            "Google refused the request (403). The API key is usually either restricted to "
            "other APIs, or the Places API (New) is not enabled on its project."
        )
    if res.status_code == 404:
        return None, f"Google has no place with ID '{place_id}'. Check the Place ID."
    if res.status_code != 200:
        detail = ""
        try:
            detail = res.json().get("error", {}).get("message", "")
        except Exception:
            detail = res.text[:200]
        return None, f"Google Places API returned HTTP {res.status_code}. {detail}".strip()

    try:
        return res.json(), None
    except Exception as e:
        return None, f"Google Places API returned a response that could not be read: {e}"


def normalise_reviews(raw_reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reshape the API's review objects, dropping nothing and inventing nothing."""
    reviews: List[Dict[str, Any]] = []
    for r in raw_reviews or []:
        rating = r.get("rating")
        text = (r.get("originalText") or r.get("text") or {}).get("text", "")
        author = (r.get("authorAttribution") or {}).get("displayName", "")
        reviews.append(
            {
                "id": r.get("name", ""),
                "platform": "Google",
                "author": author or "Google user",
                "rating": int(rating) if isinstance(rating, (int, float)) else None,
                "text": text,
                "published": r.get("publishTime"),
                "published_relative": r.get("relativePublishTimeDescription"),
                "url": (r.get("authorAttribution") or {}).get("uri"),
                # Google does not tell us through this API whether the owner has
                # already replied, so the old "RESPONDED" / "DRAFTED" /
                # "NEEDS_APPROVAL" statuses could only ever have been made up.
                "reply_status": "unknown — the Places API does not report owner replies",
            }
        )
    return reviews


def sentiment_from_ratings(reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Split the returned reviews by star rating.

    This is arithmetic on the star rating, not language analysis. The panel used
    to present percentages under the heading "AI Sentiment Analysis" without any
    model being involved; calling it what it is costs nothing and stops the
    number being read as more than it is.
    """
    rated = [r for r in reviews if isinstance(r.get("rating"), int)]
    total = len(rated)
    if not total:
        return {
            "method": "star rating only — no reviews returned to classify",
            "sample_size": 0,
            "positive_percent": 0.0,
            "neutral_percent": 0.0,
            "negative_percent": 0.0,
        }

    positive = sum(1 for r in rated if r["rating"] >= 4)
    neutral = sum(1 for r in rated if r["rating"] == 3)
    negative = sum(1 for r in rated if r["rating"] <= 2)
    return {
        "method": "derived from star ratings, not language analysis",
        "sample_size": total,
        "positive_percent": round(positive / total * 100, 1),
        "neutral_percent": round(neutral / total * 100, 1),
        "negative_percent": round(negative / total * 100, 1),
    }


def star_breakdown(reviews: List[Dict[str, Any]], total_reviews: int) -> Dict[str, Any]:
    """Counts across the reviews Google returned, which is at most five."""
    rated = [r for r in reviews if isinstance(r.get("rating"), int)]
    return {
        "counted_over": len(rated),
        "account_total_reviews": total_reviews,
        "is_full_history": len(rated) >= total_reviews and total_reviews > 0,
        "note": (
            f"Google returns at most 5 reviews through this API. These counts cover "
            f"{len(rated)} review(s), not all {total_reviews}."
        ) if total_reviews > len(rated) else "These counts cover every review on the profile.",
        "five_star": sum(1 for r in rated if r["rating"] == 5),
        "four_star": sum(1 for r in rated if r["rating"] == 4),
        "three_star_and_below": sum(1 for r in rated if r["rating"] <= 3),
    }


def build_recommendations(rating: Optional[float], total: int,
                          reviews: List[Dict[str, Any]]) -> List[str]:
    """Recommendations drawn from the reviews just read."""
    out: List[str] = []
    low = [r for r in reviews if isinstance(r.get("rating"), int) and r["rating"] <= 3]
    if low:
        worst = min(low, key=lambda r: r["rating"])
        snippet = (worst["text"] or "").strip().replace("\n", " ")[:120]
        out.append(
            f"A {worst['rating']}-star review from {worst['author']} is among the most recent"
            + (f': "{snippet}..."' if snippet else ".")
            + " Reply to it on your Google Business Profile."
        )
    if total == 0:
        out.append("This profile has no reviews yet. Asking recent customers is the only way to start.")
    elif total < 20:
        out.append(f"Only {total} reviews on the profile. Ask after each completed booking to build volume.")
    if rating is not None and rating < 4.5 and total:
        out.append(f"The profile average is {rating}. Replying to negative reviews is what usually moves it.")
    if not out:
        out.append(f"{total} reviews at an average of {rating}. Keep asking after each booking.")
    return out


class ReviewReputationAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="reputation-agent",
            name="Review / Reputation Agent",
            description="Reads Google reviews for the business through the Places API, summarises ratings, and drafts replies to post by hand.",
            category="Customer Experience",
            enabled=True,
            paused=False,
            supported_actions=["fetch_reviews", "sentiment_summary", "draft_reply", "reputation_report"],
            version="2.0.0",
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "fetch_reviews")).lower().strip()
        use_ai = bool(input_data.get("use_ai", False))
        site_id = input_data.get("site_id") or getattr(task, "site_id", None)

        creds = resolve_place_credentials(input_data.get("credentials"), site_id)
        place_id = creds.get("place_id")
        api_key = creds.get("api_key")

        logger.info(
            f"Executing ReviewReputationAgent: action={action}, "
            f"place_id={'set' if place_id else 'missing'}, api_key={'set' if api_key else 'missing'}"
        )

        tokens_used, cost_usd = 0, 0.0
        model_used = "google-places-api"

        # ---- Drafting a reply to a review the operator pasted in ----
        if action == "draft_reply":
            review_text = str(input_data.get("review_text", "")).strip()
            rating = input_data.get("rating")
            if not review_text:
                return {
                    "output": {
                        "action": action,
                        "error": "Paste the review you want a reply to. Nothing was drafted.",
                        "draft_response": None,
                    },
                    "model_used": "none",
                    "tokens_used": 0,
                    "cost_usd": 0.0,
                }

            draft, method = None, None
            if use_ai:
                try:
                    response = router.route_and_execute(LLMRequest(
                        user_prompt=(
                            f"Write a short, warm, specific reply from the business owner to this "
                            f"Google review ({rating} stars): \"{review_text}\". Address what the "
                            f"reviewer actually said. No marketing slogans. Plain text only."
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
                    logger.warning(f"AI reply drafting failed: {e}")

            if not draft:
                # The template this replaces was returned whether or not the AI
                # ran, so a generic sentence was presented as a drafted reply.
                # Say which one the operator is looking at.
                draft = (
                    "Thank you for taking the time to leave a review. We read every one, and "
                    "we would like to hear more — please get in touch so we can follow up."
                )
                method = "generic template — no model ran"
                model_used = "template"

            return {
                "output": {
                    "action": action,
                    "rating": rating,
                    "review_text": review_text,
                    "draft_response": draft,
                    "draft_method": method,
                    "can_publish_from_here": False,
                    "publish_note": (
                        "This is a draft to copy. Posting a reply needs Google Business Profile "
                        "access, which this agent does not have."
                    ),
                },
                "model_used": model_used,
                "tokens_used": tokens_used,
                "cost_usd": cost_usd,
            }

        # ---- Reading the profile ----
        if not place_id or not api_key:
            missing = [n for n, v in (("Place ID", place_id), ("Places API key", api_key)) if not v]
            return {
                "output": {
                    "action": action,
                    "live_data_connected": False,
                    "data_source": "NOT CONNECTED — no Google Places credentials",
                    "live_error": (
                        f"Missing {' and '.join(missing)}. Add them under this agent's "
                        f"Connect form; nothing is shown until Google answers."
                    ),
                    "business_name": creds.get("business_name"),
                    "reputation_overview": {
                        "average_rating": None,
                        "total_reviews": 0,
                        "sentiment_breakdown": sentiment_from_ratings([]),
                    },
                    "star_breakdown": star_breakdown([], 0),
                    "recent_reviews": [],
                    "actionable_recommendations": [
                        "Connect a Google Place ID and a Places API key to read this profile's reviews.",
                    ],
                },
                "model_used": "none — not connected",
                "tokens_used": 0,
                "cost_usd": 0.0,
            }

        payload, error = fetch_google_reviews(place_id, api_key)
        if error or payload is None:
            return {
                "output": {
                    "action": action,
                    "live_data_connected": False,
                    "data_source": "GOOGLE PLACES API — REQUEST FAILED",
                    "live_error": error,
                    "place_id": place_id,
                    "reputation_overview": {
                        "average_rating": None,
                        "total_reviews": 0,
                        "sentiment_breakdown": sentiment_from_ratings([]),
                    },
                    "star_breakdown": star_breakdown([], 0),
                    "recent_reviews": [],
                    "actionable_recommendations": [f"Fix the connection: {error}"],
                },
                "model_used": "none — request failed",
                "tokens_used": 0,
                "cost_usd": 0.0,
            }

        reviews = normalise_reviews(payload.get("reviews") or [])
        rating = payload.get("rating")
        total_reviews = int(payload.get("userRatingCount") or 0)
        business_name = (payload.get("displayName") or {}).get("text") or creds.get("business_name")

        result_payload: Dict[str, Any] = {
            "action": action,
            "live_data_connected": True,
            "data_source": "LIVE — Google Places API",
            "live_error": None,
            "place_id": payload.get("id") or place_id,
            "business_name": business_name,
            "profile_url": payload.get("googleMapsUri"),
            "platforms_read": ["Google"],
            "platforms_not_connected": ["TripAdvisor", "Trustpilot", "Facebook"],
            "reputation_overview": {
                "average_rating": round(float(rating), 2) if rating is not None else None,
                "total_reviews": total_reviews,
                "reviews_returned": len(reviews),
                "sentiment_breakdown": sentiment_from_ratings(reviews),
            },
            "star_breakdown": star_breakdown(reviews, total_reviews),
            "recent_reviews": reviews,
            "can_publish_replies": False,
            "publish_note": (
                "Replies cannot be posted from here. The Places API is read-only; posting needs "
                "Google Business Profile API access and owner OAuth."
            ),
            "actionable_recommendations": build_recommendations(rating, total_reviews, reviews),
        }

        if use_ai and reviews:
            try:
                joined = "\n".join(
                    f"- {r['rating']} stars: {(r['text'] or '')[:300]}" for r in reviews
                )
                response = router.route_and_execute(LLMRequest(
                    user_prompt=(
                        f"These are the most recent Google reviews for {business_name}:\n{joined}\n\n"
                        f"Return JSON with keys 'themes' (what customers repeatedly mention) and "
                        f"'reply_drafts' (one short specific reply per review, in the same order). "
                        f"Base everything on the text above; do not invent details."
                    ),
                    task_type=TaskComplexity.STANDARD,
                    json_output=True,
                ))
                model_used = response.model_used
                tokens_used = response.tokens_in + response.tokens_out
                cost_usd = response.cost_usd
                if response.parsed_json:
                    result_payload["ai_analysis"] = response.parsed_json
                    result_payload["ai_analysis_note"] = f"Written by {model_used} from the reviews above."
            except Exception as e:
                logger.warning(f"AI review analysis failed: {e}")
                result_payload["ai_analysis_error"] = str(e)

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        }
