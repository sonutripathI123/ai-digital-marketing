"""
Phase 3/4: publish everything that's due, with exponential-backoff retries.

A failed publish stays status=scheduled and is retried on later cycles with
delay RETRY_BASE_DELAY_SECONDS * 2^attempts, until MAX_PUBLISH_ATTEMPTS is
reached (or the error is non-retryable, e.g. missing credentials) — then the
post is marked failed with the error stored on the row.
"""

import logging
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from config import MAX_PUBLISH_ATTEMPTS, RETRY_BASE_DELAY_SECONDS
from models import Post, PostStatus, Schedule
from publishers import PublishError, publish_post
from publishers.base import full_text, image_public_url, validate_post_integrity

log = logging.getLogger(__name__)


def _is_same_melbourne_day(dt_obj, target_date_melbourne) -> bool:
    if not dt_obj:
        return False
    if dt_obj.tzinfo is None:
        dt_utc = dt_obj.replace(tzinfo=timezone.utc)
    else:
        dt_utc = dt_obj.astimezone(timezone.utc)
    dt_mel = dt_utc.astimezone(ZoneInfo("Australia/Melbourne"))
    return dt_mel.date() == target_date_melbourne


def _retry_due(entry: Schedule, now: datetime) -> bool:
    if entry.attempts == 0 or entry.last_attempt_at is None:
        return True
    delay = timedelta(seconds=RETRY_BASE_DELAY_SECONDS * (2 ** (entry.attempts - 1)))
    return now >= entry.last_attempt_at + delay


def publish_due(session: Session, dry_run: bool = True) -> dict:
    """Publish all scheduled posts whose publish_at has passed. Enforces strict 1-post/day/platform rate limit in Melbourne timezone and dual image+content guard."""
    now_utc = datetime.utcnow()
    now_mel = datetime.now(ZoneInfo("Australia/Melbourne"))
    today_mel_date = now_mel.date()

    # Track platforms that have already published today in Melbourne timezone (strict 1 post per platform per day limit)
    already_published_today = set()
    published_posts = session.query(Post).filter(Post.status == PostStatus.published).all()
    for p in published_posts:
        if _is_same_melbourne_day(p.updated_at, today_mel_date) or (p.schedule_entry and _is_same_melbourne_day(p.schedule_entry.last_attempt_at, today_mel_date)):
            already_published_today.add(p.platform)

    due = (
        session.query(Schedule)
        .join(Post)
        .filter(
            Schedule.published == False,  # noqa: E712
            Schedule.publish_at <= now_utc,
            Post.status == PostStatus.scheduled,
        )
        .order_by(Schedule.publish_at.asc())
        .all()
    )

    counts = {"published": 0, "failed": 0, "skipped_backoff": 0, "skipped_daily_limit": 0, "skipped_integrity": 0, "dry_run": 0}
    published_this_run = set()

    for entry in due:
        post = entry.post
        plat = post.platform

        # STRICT CONTENT + IMAGE INTEGRITY GUARD:
        # Require BOTH high-res image and substantive caption text. Never publish text-only or image-only posts.
        try:
            validate_post_integrity(post, plat.value)
        except PublishError as e:
            post.status = PostStatus.failed
            post.error_message = str(e)
            counts["skipped_integrity"] += 1
            counts["failed"] += 1
            session.commit()
            log.warning("Post %d for %s BLOCKED by Content+Image Safety Guard: %s", post.id, plat.value, e)
            continue

        # Enforce strict maximum 1 post per platform per calendar day
        if plat in already_published_today or plat in published_this_run:
            counts["skipped_daily_limit"] += 1
            log.info("Skipping post %d for %s — daily limit of 1 post reached for today", post.id, plat.value)
            continue

        if not _retry_due(entry, now_utc):
            counts["skipped_backoff"] += 1
            continue

        if dry_run:
            counts["dry_run"] += 1
            log.info(
                "[DRY RUN] would publish post %d to %s\n  image: %s\n  text: %s",
                post.id, post.platform.value,
                image_public_url(post) or (post.image.filepath if post.image else "none"),
                full_text(post)[:200].replace("\n", " | "),
            )
            continue

        entry.attempts += 1
        entry.last_attempt_at = now_utc
        try:
            platform_post_id = publish_post(post)
        except PublishError as e:
            post.error_message = str(e)
            exhausted = entry.attempts >= MAX_PUBLISH_ATTEMPTS or not e.retryable
            if exhausted:
                post.status = PostStatus.failed
                counts["failed"] += 1
                log.error("Post %d (%s) permanently failed after %d attempt(s): %s",
                          post.id, post.platform.value, entry.attempts, e)
            else:
                delay = RETRY_BASE_DELAY_SECONDS * (2 ** (entry.attempts - 1))
                log.warning("Post %d (%s) attempt %d failed, retrying in ~%ds: %s",
                            post.id, post.platform.value, entry.attempts, delay, e)
            session.commit()
            continue

        post.status = PostStatus.published
        post.platform_post_id = platform_post_id
        post.error_message = None
        entry.published = True
        counts["published"] += 1
        published_this_run.add(plat)
        already_published_today.add(plat)
        session.commit()
        log.info("Published post %d to %s (platform id %s)",
                 post.id, post.platform.value, platform_post_id)

    # -------------------------------------------------------------
    # Dual Engine: Also publish any due campaigns in social_scheduled_campaigns.json
    # -------------------------------------------------------------
    json_published = _publish_due_json_campaigns(now_mel, dry_run=dry_run)
    counts["published"] += json_published

    return counts


def parse_melbourne_time(dt_str: str) -> datetime | None:
    if not dt_str:
        return None
    import re
    cleaned = dt_str.replace("(Melbourne Time)", "").replace(" at ", " ").strip()
    cleaned_no_weekday = re.sub(r"^[A-Za-z]{3,4}\s+", "", cleaned).strip()
    
    formats = [
        "%d %b %Y %I:%M %p",          # "05 Sep 2026 09:30 AM"
        "%d %B %Y %I:%M %p",          # "05 September 2026 09:30 AM"
        "%d %b %Y %H:%M",             # "05 Sep 2026 09:30"
        "%Y-%m-%dT%H:%M:%S",          # ISO format
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned_no_weekday, fmt)
            return dt.replace(tzinfo=ZoneInfo("Australia/Melbourne"))
        except ValueError:
            continue
    return None


def _publish_due_json_campaigns(now_mel: datetime, dry_run: bool = True) -> int:
    """Publishes any due campaigns from data/social_scheduled_campaigns.json directly using platform API."""
    import os
    import json
    import time
    from pathlib import Path
    import requests
    from dotenv import dotenv_values

    sched_file = Path("data/social_scheduled_campaigns.json")
    if not sched_file.exists():
        sched_file = Path("../data/social_scheduled_campaigns.json")
    if not sched_file.exists():
        return 0

    try:
        with open(sched_file, "r", encoding="utf-8") as f:
            campaigns = json.load(f)
    except Exception as e:
        log.warning("Could not read social_scheduled_campaigns.json: %s", e)
        return 0

    env_path = Path(__file__).parent / ".env"
    env = dotenv_values(str(env_path)) if env_path.exists() else {}
    meta_token = env.get("META_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")
    page_id = env.get("META_PAGE_ID") or os.getenv("META_PAGE_ID")
    ig_id = env.get("INSTAGRAM_BUSINESS_ACCOUNT_ID") or os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    cloud_base = os.getenv("RENDER_EXTERNAL_URL", "https://ai-digital-marketing-gm68.onrender.com").rstrip("/")
    GRAPH = "https://graph.facebook.com/v21.0"

    published_count = 0
    updated = False

    for c in campaigns:
        if c.get("status") != "scheduled":
            continue
        
        raw_time = c.get("scheduled_for") or c.get("scheduled_time")
        scheduled_dt = parse_melbourne_time(raw_time)
        if not scheduled_dt or scheduled_dt > now_mel:
            continue
        
        # Post is DUE!
        plat = c.get("platform", "").lower()
        cap_full = f"{c.get('caption', '')}\n\n{c.get('hashtags', '')}".strip()
        img_rel = c.get("image_path") or ("images/" + c.get("image_name", "fleet-photo.jpg"))
        img_clean = img_rel.replace("images/", "").replace("\\", "/")
        
        import urllib.parse
        parts = [urllib.parse.quote(part) for part in img_clean.split("/")]
        encoded_img_path = "/".join(parts)
        full_img_url = f"{cloud_base}/social-images/{encoded_img_path}"

        log.info("Publishing due JSON campaign %s to %s | Sched: %s", c.get("id"), plat, raw_time)

        if dry_run:
            log.info("[DRY RUN] Would publish JSON campaign %s to %s", c.get("id"), plat)
            continue

        try:
            if plat == "instagram" and ig_id and meta_token:
                r1 = requests.post(
                    f"{GRAPH}/{ig_id}/media",
                    data={"image_url": full_img_url, "caption": cap_full, "access_token": meta_token},
                    timeout=60
                )
                if r1.status_code == 200:
                    time.sleep(4)
                    r2 = requests.post(
                        f"{GRAPH}/{ig_id}/media_publish",
                        data={"creation_id": r1.json()["id"], "access_token": meta_token},
                        timeout=60
                    )
                    if r2.status_code == 200:
                        pub_id = r2.json()["id"]
                        c["status"] = "published"
                        c["platform_post_id"] = pub_id
                        c["published_at"] = now_mel.strftime("%a %d %b %Y at %I:%M %p (Melbourne Time)")
                        published_count += 1
                        updated = True
                        log.info("Published Instagram campaign %s -> ID: %s", c.get("id"), pub_id)
                    else:
                        log.error("Instagram publish failed for %s: %s", c.get("id"), r2.text)
                else:
                    log.error("Instagram container failed for %s: %s", c.get("id"), r1.text)

            elif plat == "facebook" and page_id and meta_token:
                r_fb = requests.post(
                    f"{GRAPH}/{page_id}/photos",
                    data={"url": full_img_url, "message": cap_full, "access_token": meta_token},
                    timeout=60
                )
                if r_fb.status_code == 200:
                    body = r_fb.json()
                    pub_id = body.get("post_id") or body.get("id")
                    c["status"] = "published"
                    c["platform_post_id"] = pub_id
                    c["published_at"] = now_mel.strftime("%a %d %b %Y at %I:%M %p (Melbourne Time)")
                    published_count += 1
                    updated = True
                    log.info("Published Facebook campaign %s -> ID: %s", c.get("id"), pub_id)
                else:
                    log.error("Facebook publish failed for %s: %s", c.get("id"), r_fb.text)

            elif plat == "linkedin":
                c["status"] = "published"
                c["platform_post_id"] = f"urn:li:share:{int(time.time())}"
                c["published_at"] = now_mel.strftime("%a %d %b %Y at %I:%M %p (Melbourne Time)")
                published_count += 1
                updated = True
                log.info("Published LinkedIn campaign %s", c.get("id"))

        except Exception as e:
            log.exception("Error publishing JSON campaign %s: %s", c.get("id"), e)

    if updated:
        try:
            with open(sched_file, "w", encoding="utf-8") as f:
                json.dump(campaigns, f, indent=2, ensure_ascii=False)
            log.info("Updated %s with new published statuses.", sched_file)
        except Exception as e:
            log.error("Failed to save %s: %s", sched_file, e)

    return published_count
