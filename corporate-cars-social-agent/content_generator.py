"""
Corporate Cars Melbourne — Social Media Agent
Content engine: generates platform-specific posts with the Claude API
and saves them as status=draft, with an image picked from the library.

use_ai=False produces a deterministic template post — useful for testing
the pipeline end-to-end without an ANTHROPIC_API_KEY.
"""

import json
import logging
from datetime import datetime

import anthropic
from sqlalchemy.orm import Session

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, BUSINESS_NAME, WEBSITE_URL
from image_selector import select_image
from models import Keyword, Platform, Post, PostStatus
from prompts import HARD_LIMITS, PLATFORM_RULES, SYSTEM_PROMPT

log = logging.getLogger(__name__)


class GenerationError(Exception):
    pass


def get_or_create_keyword(session: Session, text: str, category: str | None = None) -> Keyword:
    text = text.strip().lower()
    kw = session.query(Keyword).filter(Keyword.keyword == text).one_or_none()
    if kw is None:
        kw = Keyword(keyword=text, category=category)
        session.add(kw)
        session.commit()
    elif category and not kw.category:
        kw.category = category
        session.commit()
    return kw


def _build_user_prompt(keyword: Keyword, platform: str) -> str:
    rules = PLATFORM_RULES[platform]
    return (
        f"Platform: {platform}\n"
        f"SEO keyword to target: \"{keyword.keyword}\""
        + (f" (category: {keyword.category})" if keyword.category else "")
        + "\n\nPLATFORM RULES & STRICT WORD LIMITS\n"
        f"- Target Word Count: {rules.get('target_words', '40-70 words')} (Strictly do not exceed {rules.get('max_words', 70)} words)\n"
        f"- Hard character limit (caption + hashtags combined): {rules['max_chars']}\n"
        f"- Target character length: {rules['target_chars']}\n"
        f"- Hashtags: {rules['hashtag_count']}\n"
        f"- CTA style: {rules['cta_style']}\n"
        f"- Algorithm guidance: {rules['algorithm_notes']}\n\n"
        "Write the post now. Keep it crisp, compact, and punchy (max 2-3 short paragraphs). Respond with the JSON object only."
    )


def _parse_response(text: str) -> dict:
    """Extract the JSON object from the model response (tolerates stray fences)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise GenerationError(f"No JSON object in model response: {text[:200]!r}")
    data = json.loads(text[start:end + 1])
    if "caption" not in data or not str(data["caption"]).strip():
        raise GenerationError("Model response missing 'caption'")
    return {
        "caption": str(data["caption"]).strip(),
        "hashtags": str(data.get("hashtags", "")).strip(),
        "cta": str(data.get("cta", "")).strip()[:255],
    }


def _generate_with_claude(keyword: Keyword, platform: str) -> dict:
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.startswith("your_"):
        raise GenerationError(
            "ANTHROPIC_API_KEY is not set in .env. Add your key, or use --no-ai for a template post."
        )
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)  # SDK retries 429/5xx itself
    user_prompt = _build_user_prompt(keyword, platform)

    last_error: Exception | None = None
    for attempt in range(2):  # one retry for malformed JSON
        try:
            response = _call_claude(client, user_prompt)
        except anthropic.AuthenticationError as e:
            raise GenerationError(f"Anthropic auth failed — check ANTHROPIC_API_KEY in .env ({e.message})")
        except anthropic.APIConnectionError:
            raise GenerationError("Could not reach the Anthropic API — check your internet connection.")
        except anthropic.APIStatusError as e:
            raise GenerationError(f"Anthropic API error {e.status_code}: {e.message}")
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return _parse_response(text)
        except (GenerationError, json.JSONDecodeError) as e:
            last_error = e
            log.warning("Attempt %d: bad JSON from model (%s), retrying", attempt + 1, e)
    raise GenerationError(f"Could not parse model output after retries: {last_error}")


def _call_claude(client: anthropic.Anthropic, user_prompt: str):
    return client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # system prompt is stable across calls
            }],
            messages=[{"role": "user", "content": user_prompt}],
        )


def _generate_template(keyword: Keyword, platform: str) -> dict:
    """Deterministic offline fallback for testing without an API key."""
    kw = keyword.keyword.title()
    templates = {
        "x": f"{kw} in Melbourne, handled. Flight tracked, chauffeur waiting, fixed price. Book: {WEBSITE_URL}",
        "pinterest": f"{kw} | {BUSINESS_NAME}\nPremium chauffeur service for {keyword.keyword} across Melbourne. "
                     f"Late-model European vehicles, accredited chauffeurs, fixed pricing. Plan your journey at {WEBSITE_URL}",
    }
    caption = templates.get(platform, (
        f"When it comes to {keyword.keyword}, the details matter. {BUSINESS_NAME} delivers "
        f"punctual, discreet chauffeur service across Melbourne — immaculate European vehicles, "
        f"accredited chauffeurs, fixed pricing. Arrange your next journey at {WEBSITE_URL}."
    ))
    hashtags = {"instagram": "#MelbourneChauffeur #CorporateTravel #ExecutiveTransfers",
                "linkedin": "#CorporateTravel #Melbourne #ExecutiveTransport",
                "x": "#Melbourne"}.get(platform, "")
    return {"caption": caption, "hashtags": hashtags, "cta": f"Book at {WEBSITE_URL}"}


def _enforce_limit(content: dict, platform: str) -> dict:
    limit = HARD_LIMITS[platform]
    combined = content["caption"] + ("\n\n" + content["hashtags"] if content["hashtags"] else "")
    if len(combined) <= limit:
        return content
    log.warning("%s post over %d chars (%d) — trimming", platform, limit, len(combined))
    overflow = len(combined) - limit
    if content["hashtags"] and len(content["hashtags"]) + 2 >= overflow:
        content["hashtags"] = ""  # drop hashtags first
    else:
        room = limit - (len(content["hashtags"]) + 2 if content["hashtags"] else 0) - 1
        content["caption"] = content["caption"][:room].rsplit(" ", 1)[0] + "…"
    return content


def generate_post(session: Session, keyword: Keyword, platform: Platform,
                  use_ai: bool = True) -> Post:
    """Generate one draft post for one platform and persist it."""
    pname = platform.value
    content = _generate_with_claude(keyword, pname) if use_ai else _generate_template(keyword, pname)
    content = _enforce_limit(content, pname)

    image = select_image(session, topic=keyword.keyword, keyword=keyword)
    if image is None:
        log.warning("No images in library — post %s/%s created without an image", pname, keyword.keyword)

    post = Post(
        platform=platform,
        keyword_id=keyword.id,
        image_id=image.id if image else None,
        caption=content["caption"],
        hashtags=content["hashtags"],
        cta=content["cta"],
        status=PostStatus.draft,
    )
    keyword.last_used_at = datetime.utcnow()
    session.add(post)
    session.commit()
    log.info("Draft post %d created: %s / '%s'%s", post.id, pname, keyword.keyword,
             f" (image: {image.filename})" if image else "")
    return post
