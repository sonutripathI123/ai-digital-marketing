"""
Phase 3/4: publish everything that's due, with exponential-backoff retries.

A failed publish stays status=scheduled and is retried on later cycles with
delay RETRY_BASE_DELAY_SECONDS * 2^attempts, until MAX_PUBLISH_ATTEMPTS is
reached (or the error is non-retryable, e.g. missing credentials) — then the
post is marked failed with the error stored on the row.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from config import MAX_PUBLISH_ATTEMPTS, RETRY_BASE_DELAY_SECONDS
from models import Post, PostStatus, Schedule
from publishers import PublishError, publish_post
from publishers.base import full_text, image_public_url, validate_post_integrity

log = logging.getLogger(__name__)


def _retry_due(entry: Schedule, now: datetime) -> bool:
    if entry.attempts == 0 or entry.last_attempt_at is None:
        return True
    delay = timedelta(seconds=RETRY_BASE_DELAY_SECONDS * (2 ** (entry.attempts - 1)))
    return now >= entry.last_attempt_at + delay


def publish_due(session: Session, dry_run: bool = True) -> dict:
    """Publish all scheduled posts whose publish_at has passed. Enforces strict 1-post/day/platform rate limit and dual image+content guard."""
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)

    # Track platforms that have already published today (strict 1 post per platform per day limit)
    already_published_today = set()
    today_published_rows = (
        session.query(Post.platform)
        .join(Schedule)
        .filter(
            Schedule.published == True,
            Schedule.last_attempt_at >= today_start
        )
        .all()
    )
    for row in today_published_rows:
        already_published_today.add(row[0])

    due = (
        session.query(Schedule)
        .join(Post)
        .filter(
            Schedule.published == False,  # noqa: E712
            Schedule.publish_at <= now,
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

        if not _retry_due(entry, now):
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
        entry.last_attempt_at = now
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

    return counts
