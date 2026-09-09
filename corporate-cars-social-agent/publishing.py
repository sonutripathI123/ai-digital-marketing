"""
Phase 3/4: publish everything that's due, with exponential-backoff retries.

A failed publish stays status=scheduled and is retried on later cycles with
delay RETRY_BASE_DELAY_SECONDS * 2^attempts, until MAX_PUBLISH_ATTEMPTS is
reached (or the error is non-retryable, e.g. missing credentials) — then the
post is marked failed with the error stored on the row.
"""

import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from config import MAX_PUBLISH_ATTEMPTS, RETRY_BASE_DELAY_SECONDS
from models import Post, PostStatus, Schedule
from publishers import PublishError, publish_post
from publishers.base import full_text, image_public_url, validate_post_integrity
from site_config import (
    PRIMARY_SITE_ID,
    _data_dir_candidates,
    get_site_social_config,
    normalize_site_id,
    state_dir,
)

log = logging.getLogger(__name__)


DAILY_LOCK_FILE = Path("logs/social_daily_published_lock.json")


def slot_key(site_id: str, platform: str) -> str:
    """Rate-limit bucket. Scoped per website so sites never consume each
    other's quota — 'ccm:facebook' is independent of 'opal:facebook'."""
    return f"{normalize_site_id(site_id)}:{(platform or '').strip().lower()}"


def _lock_path(for_write: bool = False) -> Path:
    # A configured STATE_DIR (mounted disk) wins, so the daily quota tally
    # survives restarts instead of resetting and allowing extra posts.
    persistent = state_dir()
    if persistent:
        return persistent / "social_daily_published_lock.json"

    if DAILY_LOCK_FILE.exists():
        return DAILY_LOCK_FILE
    alt = Path("../logs/social_daily_published_lock.json")
    if alt.exists():
        return alt
    if not for_write:
        return DAILY_LOCK_FILE
    return DAILY_LOCK_FILE if DAILY_LOCK_FILE.parent.exists() else alt


def _get_daily_counts(today_date_str: str) -> dict:
    """Per-site publish tally for today, as {'site:platform': count}."""
    fpath = _lock_path()
    if not fpath.exists():
        return {}
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if data.get("date") != today_date_str:
        return {}

    counts = {k: int(v) for k, v in (data.get("counts") or {}).items()}
    # Backward compatibility with the old site-blind ["facebook", ...] format:
    # attribute those to the primary site rather than discarding them.
    for legacy_plat in data.get("published_platforms", []) or []:
        counts.setdefault(slot_key(PRIMARY_SITE_ID, legacy_plat), 1)
    return counts


def _record_daily_publish(today_date_str: str, site_id: str, platform: str) -> None:
    """Increment the per-site tally so the quota survives process restarts."""
    fpath = _lock_path(for_write=True)
    fpath.parent.mkdir(parents=True, exist_ok=True)

    data = {"date": today_date_str, "counts": {}}
    if fpath.exists():
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = json.load(f)
            if content.get("date") == today_date_str:
                data = {"date": today_date_str, "counts": {k: int(v) for k, v in (content.get("counts") or {}).items()}}
                for legacy_plat in content.get("published_platforms", []) or []:
                    data["counts"].setdefault(slot_key(PRIMARY_SITE_ID, legacy_plat), 1)
        except Exception:
            pass

    key = slot_key(site_id, platform)
    data["counts"][key] = data["counts"].get(key, 0) + 1
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.warning("Could not update daily publish lock file: %s", e)

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


def _post_site_id(post: Post) -> str:
    """Site a SQLite post belongs to; legacy rows without one are the primary site."""
    return normalize_site_id(getattr(post, "site", None) or getattr(post, "site_id", None))


def publish_due(session: Session, dry_run: bool = True, site: str | None = None) -> dict:
    """Publish all scheduled posts whose publish_at has passed.

    Rate limits are enforced per website, not globally: each site gets its own
    daily and weekly quota per platform, so two brands publishing to Facebook
    on the same day never block each other. Pass `site` to restrict a run to a
    single website; omit it to service every site in one pass.
    """
    now_utc = datetime.utcnow()
    now_mel = datetime.now(ZoneInfo("Australia/Melbourne"))
    today_mel_date = now_mel.date()
    today_mel_str = str(today_mel_date)
    site_filter = normalize_site_id(site) if site else None

    # Per-site tally of what already went out today, as {'site:platform': count}.
    published_counts = _get_daily_counts(today_mel_str)

    # 1. Fold in SQLite posts published today
    published_posts = session.query(Post).filter(Post.status == PostStatus.published).all()
    for p in published_posts:
        if _is_same_melbourne_day(p.updated_at, today_mel_date) or (p.schedule_entry and _is_same_melbourne_day(p.schedule_entry.last_attempt_at, today_mel_date)):
            key = slot_key(_post_site_id(p), p.platform.value)
            if key not in published_counts:
                published_counts[key] = 1
                _record_daily_publish(today_mel_str, _post_site_id(p), p.platform.value)

    # 2. Fold in JSON campaigns published today
    campaigns_today = _load_campaigns()
    for c in campaigns_today:
        if c.get("status") == "published" and c.get("published_at"):
            pub_dt = parse_melbourne_time(c.get("published_at"))
            if pub_dt and pub_dt.date() == today_mel_date:
                key = slot_key(c.get("site"), c.get("platform", ""))
                if key not in published_counts:
                    published_counts[key] = 1
                    _record_daily_publish(today_mel_str, c.get("site"), c.get("platform", ""))

    # Weekly tally (Melbourne week, Monday-based) for the per-site weekly cap.
    week_counts = _get_week_counts(campaigns_today, now_mel)

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

    counts = {
        "published": 0, "failed": 0, "skipped_backoff": 0, "skipped_daily_limit": 0,
        "skipped_weekly_limit": 0, "skipped_no_credentials": 0, "skipped_other_site": 0,
        "skipped_stale": 0, "skipped_integrity": 0, "dry_run": 0,
    }

    for entry in due:
        post = entry.post
        plat = post.platform
        post_site = _post_site_id(post)
        key = slot_key(post_site, plat.value)
        site_cfg = get_site_social_config(post_site)

        if site_filter and post_site != site_filter:
            counts["skipped_other_site"] += 1
            continue

        # STRICT CONTENT + IMAGE INTEGRITY GUARD:
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

        # Per-site daily cap for this platform
        if published_counts.get(key, 0) >= site_cfg.posts_per_day_per_platform:
            counts["skipped_daily_limit"] += 1
            log.info(
                "Skipping post %d - [%s] %s daily cap of %d reached for %s",
                post.id, post_site, plat.value, site_cfg.posts_per_day_per_platform, today_mel_date,
            )
            continue

        # Per-site weekly cap for this platform
        if week_counts.get(key, 0) >= site_cfg.posts_per_week_per_platform:
            counts["skipped_weekly_limit"] += 1
            log.info(
                "Skipping post %d - [%s] %s weekly cap of %d already met this week",
                post.id, post_site, plat.value, site_cfg.posts_per_week_per_platform,
            )
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
        published_counts[key] = published_counts.get(key, 0) + 1
        week_counts[key] = week_counts.get(key, 0) + 1
        _record_daily_publish(today_mel_str, post_site, plat.value)
        session.commit()
        log.info("Published post %d to [%s] %s (platform id %s)",
                 post.id, post_site, post.platform.value, platform_post_id)

    # -------------------------------------------------------------
    # Dual Engine: Also publish any due campaigns in social_scheduled_campaigns.json
    # -------------------------------------------------------------
    json_counts = _publish_due_json_campaigns(
        now_mel,
        published_counts=published_counts,
        week_counts=week_counts,
        dry_run=dry_run,
        site_filter=site_filter,
    )
    for key_name, value in json_counts.items():
        counts[key_name] = counts.get(key_name, 0) + value

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


def _campaigns_path() -> Path | None:
    """Campaign queue file. Prefers DATA_DIR (a mounted disk, when configured)
    over the repo copy, so runtime statuses survive a redeploy."""
    for path in _data_dir_candidates("social_scheduled_campaigns.json"):
        if path.exists():
            return path
    for path in (Path("data/social_scheduled_campaigns.json"),
                 Path("../data/social_scheduled_campaigns.json")):
        if path.exists():
            return path
    return None


def _load_campaigns() -> list:
    path = _campaigns_path()
    if not path:
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        log.warning("Could not read %s: %s", path, e)
        return []


def _get_week_counts(campaigns: list, now_mel: datetime) -> dict:
    """Posts already published this Melbourne week, as {'site:platform': count}."""
    week_start = now_mel.date() - timedelta(days=now_mel.weekday())
    counts: dict = {}
    for c in campaigns:
        if c.get("status") != "published" or not c.get("published_at"):
            continue
        pub_dt = parse_melbourne_time(c.get("published_at"))
        if pub_dt and week_start <= pub_dt.date() <= now_mel.date():
            key = slot_key(c.get("site"), c.get("platform", ""))
            counts[key] = counts.get(key, 0) + 1
    return counts


def _resolve_local_image(campaign: dict) -> Path | None:
    """Local file for a campaign's image — LinkedIn uploads binary, not a URL."""
    img_rel = campaign.get("image_path") or ("images/" + campaign.get("image_name", ""))
    img_rel = img_rel.replace("\\", "/").strip()
    if not img_rel:
        return None
    base = Path(__file__).resolve().parent
    stripped = img_rel[len("images/"):] if img_rel.startswith("images/") else img_rel
    for candidate in (base / img_rel, base / "images" / stripped):
        if candidate.exists():
            return candidate
    return None


def _linkedin_publish(cfg, image_path: Path, text: str) -> str:
    """Publish one image post to a site's own LinkedIn organisation page.

    Mirrors publishers/linkedin.py (registerUpload -> binary PUT -> UGC post)
    but takes the token and organisation URN from the site's config, so each
    website posts to its own page.
    """
    import requests

    api = "https://api.linkedin.com/v2"
    headers = {
        "Authorization": f"Bearer {cfg.linkedin_token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    register = requests.post(
        f"{api}/assets?action=registerUpload",
        headers=headers,
        json={
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": cfg.linkedin_org_urn,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }],
            }
        },
        timeout=60,
    )
    if register.status_code != 200:
        raise PublishError(f"linkedin registerUpload failed: {register.status_code} {register.text[:300]}")

    value = register.json()["value"]
    asset = value["asset"]
    upload_url = value["uploadMechanism"][
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]

    with open(image_path, "rb") as f:
        put = requests.put(
            upload_url, data=f,
            headers={"Authorization": f"Bearer {cfg.linkedin_token}"},
            timeout=120,
        )
    if put.status_code not in (200, 201):
        raise PublishError(f"linkedin image upload failed: {put.status_code} {put.text[:300]}")

    body = {
        "author": cfg.linkedin_org_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "IMAGE",
                "media": [{"status": "READY", "media": asset}],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    r = requests.post(f"{api}/ugcPosts", headers=headers, json=body, timeout=60)
    if r.status_code != 201:
        raise PublishError(f"linkedin post failed: {r.status_code} {r.text[:300]}")
    return r.headers.get("x-restli-id") or r.json().get("id", "")


def _publish_due_json_campaigns(
    now_mel: datetime,
    published_counts: dict = None,
    week_counts: dict = None,
    dry_run: bool = True,
    site_filter: str | None = None,
) -> dict:
    """Publish due campaigns from data/social_scheduled_campaigns.json.

    Each campaign carries its own `site`, and every credential and quota is
    resolved for that site — so one brand's post can never go out on another
    brand's account, and one brand can never eat another's daily quota.
    """
    import os
    import time
    import urllib.parse
    import requests

    published_counts = published_counts if published_counts is not None else {}
    week_counts = week_counts if week_counts is not None else {}

    sched_file = _campaigns_path()
    if not sched_file:
        return {}
    campaigns = _load_campaigns()
    if not campaigns:
        return {}

    cloud_base = os.getenv(
        "RENDER_EXTERNAL_URL",
        os.getenv("IMAGE_BASE_URL", "https://ai-digital-marketing-gm68.onrender.com/social-images")
        .rsplit("/social-images", 1)[0],
    ).rstrip("/")
    GRAPH = "https://graph.facebook.com/v21.0"

    counts = {
        "published": 0, "failed": 0, "skipped_daily_limit": 0, "skipped_weekly_limit": 0,
        "skipped_no_credentials": 0, "skipped_other_site": 0, "skipped_stale": 0, "dry_run": 0,
    }
    site_configs: dict = {}
    updated = False
    today_str = str(now_mel.date())

    def mark_published(campaign: dict, site_id: str, platform: str, post_id: str) -> None:
        nonlocal updated
        key = slot_key(site_id, platform)
        campaign["status"] = "published"
        campaign["platform_post_id"] = post_id
        campaign["published_at"] = now_mel.strftime("%a %d %b %Y at %I:%M %p (Melbourne Time)")
        counts["published"] += 1
        published_counts[key] = published_counts.get(key, 0) + 1
        week_counts[key] = week_counts.get(key, 0) + 1
        _record_daily_publish(today_str, site_id, platform)
        updated = True

    for c in campaigns:
        if c.get("status") != "scheduled":
            continue

        raw_time = c.get("scheduled_for") or c.get("scheduled_time")
        scheduled_dt = parse_melbourne_time(raw_time)
        if not scheduled_dt or scheduled_dt > now_mel:
            continue

        site_id = normalize_site_id(c.get("site"))
        plat = (c.get("platform") or "").strip().lower()
        key = slot_key(site_id, plat)

        if site_filter and site_id != site_filter:
            counts["skipped_other_site"] += 1
            continue

        if site_id not in site_configs:
            site_configs[site_id] = get_site_social_config(site_id)
        cfg = site_configs[site_id]

        # Staleness guard. A campaign that missed its slot by more than the
        # site's allowance is retired instead of published, which:
        #   - stops posts firing at a useless hour (e.g. dumped at midnight
        #     after being blocked all day by a quota), and
        #   - stops a redeploy — which restores this file from git and can
        #     reset statuses — from re-publishing weeks-old campaigns.
        lateness_hours = (now_mel - scheduled_dt).total_seconds() / 3600.0
        if lateness_hours > cfg.max_lateness_hours:
            counts["skipped_stale"] += 1
            if not dry_run:
                c["status"] = "expired"
                c["expired_at"] = now_mel.strftime("%a %d %b %Y at %I:%M %p (Melbourne Time)")
                c["expired_reason"] = (
                    f"Missed its slot by {lateness_hours:.1f}h "
                    f"(allowed {cfg.max_lateness_hours}h) - not published."
                )
                updated = True
            log.warning(
                "Retiring campaign %s - [%s] %s was %.1fh late (allowed %dh). Sched: %s",
                c.get("id"), site_id, plat, lateness_hours, cfg.max_lateness_hours, raw_time,
            )
            continue

        # Per-site daily cap
        if published_counts.get(key, 0) >= cfg.posts_per_day_per_platform:
            counts["skipped_daily_limit"] += 1
            log.info(
                "Skipping campaign %s - [%s] %s daily cap of %d reached for %s",
                c.get("id"), site_id, plat, cfg.posts_per_day_per_platform, now_mel.date(),
            )
            continue

        # Per-site weekly cap
        if week_counts.get(key, 0) >= cfg.posts_per_week_per_platform:
            counts["skipped_weekly_limit"] += 1
            log.info(
                "Skipping campaign %s - [%s] %s weekly cap of %d already met this week",
                c.get("id"), site_id, plat, cfg.posts_per_week_per_platform,
            )
            continue

        # Never silently fake a publish: without this site's own credentials
        # for this platform the campaign stays scheduled and is reported.
        if not cfg.can_publish(plat):
            counts["skipped_no_credentials"] += 1
            log.error(
                "Cannot publish campaign %s - [%s] %s is not connected. Missing: %s",
                c.get("id"), site_id, plat, cfg.missing_for(plat) or "platform not supported",
            )
            continue

        cap_full = f"{c.get('caption', '')}\n\n{c.get('hashtags', '')}".strip()
        img_rel = c.get("image_path") or ("images/" + c.get("image_name", "fleet-photo.jpg"))
        img_clean = img_rel.replace("images/", "").replace("\\", "/")
        encoded_img_path = "/".join(urllib.parse.quote(part) for part in img_clean.split("/"))
        full_img_url = f"{cloud_base}/social-images/{encoded_img_path}"

        log.info(
            "Publishing due campaign %s | site=%s platform=%s | Sched: %s",
            c.get("id"), site_id, plat, raw_time,
        )

        if dry_run:
            counts["dry_run"] += 1
            # Consume the quota in memory only, so the preview reflects what a
            # live run would actually do instead of listing every due campaign.
            published_counts[key] = published_counts.get(key, 0) + 1
            week_counts[key] = week_counts.get(key, 0) + 1
            log.info(
                "[DRY RUN] Would publish %s to [%s] %s (target: %s)",
                c.get("id"), site_id, plat,
                cfg.facebook_page_id if plat == "facebook"
                else cfg.instagram_account_id if plat == "instagram"
                else cfg.linkedin_org_urn,
            )
            continue

        try:
            if plat == "instagram":
                r1 = requests.post(
                    f"{GRAPH}/{cfg.instagram_account_id}/media",
                    data={"image_url": full_img_url, "caption": cap_full,
                          "access_token": cfg.meta_access_token},
                    timeout=60,
                )
                if r1.status_code != 200:
                    counts["failed"] += 1
                    log.error("Instagram container failed for %s [%s]: %s", c.get("id"), site_id, r1.text)
                    continue
                time.sleep(4)
                r2 = requests.post(
                    f"{GRAPH}/{cfg.instagram_account_id}/media_publish",
                    data={"creation_id": r1.json()["id"], "access_token": cfg.meta_access_token},
                    timeout=60,
                )
                if r2.status_code != 200:
                    counts["failed"] += 1
                    log.error("Instagram publish failed for %s [%s]: %s", c.get("id"), site_id, r2.text)
                    continue
                pub_id = r2.json()["id"]
                mark_published(c, site_id, plat, pub_id)
                log.info("Published Instagram campaign %s [%s] -> ID: %s", c.get("id"), site_id, pub_id)

            elif plat == "facebook":
                r_fb = requests.post(
                    f"{GRAPH}/{cfg.facebook_page_id}/photos",
                    data={"url": full_img_url, "message": cap_full,
                          "access_token": cfg.meta_access_token},
                    timeout=60,
                )
                if r_fb.status_code != 200:
                    counts["failed"] += 1
                    log.error("Facebook publish failed for %s [%s]: %s", c.get("id"), site_id, r_fb.text)
                    continue
                body = r_fb.json()
                pub_id = body.get("post_id") or body.get("id")
                mark_published(c, site_id, plat, pub_id)
                log.info("Published Facebook campaign %s [%s] -> ID: %s", c.get("id"), site_id, pub_id)

            elif plat == "linkedin":
                image_path = _resolve_local_image(c)
                if not image_path:
                    counts["failed"] += 1
                    log.error(
                        "LinkedIn campaign %s [%s] has no local image (%s) - image is mandatory.",
                        c.get("id"), site_id, img_rel,
                    )
                    continue
                pub_id = _linkedin_publish(cfg, image_path, cap_full)
                mark_published(c, site_id, plat, pub_id)
                log.info("Published LinkedIn campaign %s [%s] -> ID: %s", c.get("id"), site_id, pub_id)

        except PublishError as e:
            counts["failed"] += 1
            log.error("Publish error for campaign %s [%s] %s: %s", c.get("id"), site_id, plat, e)
        except Exception as e:
            counts["failed"] += 1
            log.exception("Error publishing campaign %s [%s]: %s", c.get("id"), site_id, e)

    if updated:
        try:
            with open(sched_file, "w", encoding="utf-8") as f:
                json.dump(campaigns, f, indent=2, ensure_ascii=False)
            log.info("Updated %s with new published statuses.", sched_file)
        except Exception as e:
            log.error("Failed to save %s: %s", sched_file, e)

    return counts
