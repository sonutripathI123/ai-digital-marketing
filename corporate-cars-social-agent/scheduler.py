"""
Corporate Cars Melbourne — Social Media Agent
Phase 2: assign publish slots to draft posts — 2 posts/week/platform.

Slots are defined in Melbourne local time and stored in the DB as UTC.
Slot times are staggered across platforms so nothing posts simultaneously.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from config import POSTS_PER_WEEK_PER_PLATFORM, TIMEZONE
from models import Platform, Post, PostStatus, Schedule

log = logging.getLogger(__name__)

# (weekday, hour, minute) in Melbourne time; weekday: 0=Mon.
# Two slots per platform, spread across high-engagement windows.
POSTING_SLOTS = {
    Platform.linkedin:  [(1, 10, 30), (3, 11, 0)],   # Tue 10:30am, Thu 11:00am
    Platform.instagram: [(2, 14, 0), (4, 15, 30)],   # Tue 11:00am, Fri 10:15am
    Platform.facebook:  [(1, 16, 0), (3, 13, 30)],    # Wed 10:00am, Sat 10:30am
    Platform.x:         [(0, 8, 0), (3, 17, 15)],    # Mon 8:00am, Thu 5:15pm
    Platform.threads:   [(2, 19, 30), (6, 11, 0)],   # Wed 7:30pm, Sun 11:00am
    Platform.pinterest: [(1, 20, 30), (5, 14, 0)],   # Tue 8:30pm, Sat 2:00pm
}


def _next_slot_occurrence(weekday: int, hour: int, minute: int, after: datetime) -> datetime:
    """First Melbourne-local occurrence of the slot strictly after `after` (UTC aware)."""
    local_after = after.astimezone(TIMEZONE)
    candidate = local_after.replace(hour=hour, minute=minute, second=0, microsecond=0)
    days_ahead = (weekday - candidate.weekday()) % 7
    candidate += timedelta(days=days_ahead)
    if candidate <= local_after:
        candidate += timedelta(days=7)
    return candidate.astimezone(timezone.utc)


def _last_scheduled_utc(session: Session, platform: Platform) -> datetime | None:
    row = (
        session.query(Schedule.publish_at)
        .join(Post)
        .filter(Post.platform == platform, Schedule.published == False)  # noqa: E712
        .order_by(Schedule.publish_at.desc())
        .first()
    )
    return row[0].replace(tzinfo=timezone.utc) if row else None


def schedule_posts(session: Session, weeks: int = 1) -> list[Schedule]:
    """
    For each platform, queue POSTS_PER_WEEK_PER_PLATFORM drafts per week for
    `weeks` weeks. Oldest drafts go out first. Scheduling continues after the
    latest already-queued slot, so re-running extends the queue, not overlaps it.
    """
    created: list[Schedule] = []
    now_utc = datetime.now(timezone.utc)

    ACTIVE_PLATFORMS = [Platform.instagram, Platform.facebook, Platform.linkedin]
    for platform in ACTIVE_PLATFORMS:
        slots = POSTING_SLOTS[platform][:POSTS_PER_WEEK_PER_PLATFORM]
        drafts = (
            session.query(Post)
            .filter(Post.platform == platform, Post.status == PostStatus.draft)
            .order_by(Post.created_at.asc())
            .all()
        )
        if not drafts:
            log.info("No drafts to schedule for %s", platform.value)
            continue

        start_after = _last_scheduled_utc(session, platform) or now_utc
        draft_iter = iter(drafts)
        done = False
        for week in range(weeks):
            # chronological within the week, so the oldest draft gets the earliest slot
            occurrences = sorted(
                _next_slot_occurrence(weekday, hour, minute, start_after + timedelta(weeks=week))
                for (weekday, hour, minute) in slots
            )
            for publish_at in occurrences:
                post = next(draft_iter, None)
                if post is None:
                    done = True
                    break
                entry = Schedule(post_id=post.id, publish_at=publish_at.replace(tzinfo=None))
                post.status = PostStatus.scheduled
                session.add(entry)
                created.append(entry)
                local = publish_at.astimezone(TIMEZONE)
                log.info("Scheduled post %d (%s) for %s", post.id, platform.value,
                         local.strftime("%a %d %b %Y %H:%M %Z"))
            if done:
                break

    session.commit()
    return created
