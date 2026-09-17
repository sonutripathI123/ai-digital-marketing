"""
Agent #12: Social Media Analytics Agent (`social-analytics-agent`).

Fetches real organic social media performance across Instagram, Facebook, LinkedIn, X,
Threads, and Pinterest using live Meta Graph API, LinkedIn API, and local social_agent.db telemetry.
"""

import os
from datetime import datetime
import re
import json
import sqlite3
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from config.settings import ROOT_DIR
from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("social-analytics-agent")

# Load social agent credentials from corporate-cars-social-agent/.env
SOCIAL_AGENT_DIR = ROOT_DIR / "corporate-cars-social-agent"
SOCIAL_ENV_FILE = SOCIAL_AGENT_DIR / ".env"
if SOCIAL_ENV_FILE.exists():
    load_dotenv(SOCIAL_ENV_FILE)


def sortable_timestamp(value: Optional[str]) -> str:
    """An ISO timestamp for ordering, from any of the shapes posts arrive in.

    Returns "" when nothing can be read, and the caller sorts those last rather
    than guessing a date for them.
    """
    if not value:
        return ""
    raw = str(value).strip()

    # 1. Graph API / database: 2026-08-28T06:56:00+0000 or with a space.
    try:
        cleaned = raw.split("+")[0].replace("Z", "").replace("T", " ").split(".")[0].strip()
        return datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S").isoformat()
    except Exception:
        pass

    # 2. Campaign file: "Fri 28 Aug 2026 at 06:56 AM (Melbourne Time)"
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4}).*?(\d{1,2}):(\d{2})\s*([AaPp][Mm])", raw)
    if m:
        try:
            day, mon, year, hour, minute, meridiem = m.groups()
            hour = int(hour) % 12 + (12 if meridiem.lower() == "pm" else 0)
            return datetime.strptime(
                f"{year}-{mon}-{int(day):02d} {hour:02d}:{minute}", "%Y-%b-%d %H:%M"
            ).isoformat()
        except Exception:
            pass

    # 3. Date only.
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", raw)
    if m:
        try:
            day, mon, year = m.groups()
            return datetime.strptime(f"{year}-{mon}-{int(day):02d}", "%Y-%b-%d").isoformat()
        except Exception:
            pass

    return ""


def format_utc_to_display(utc_str: Optional[str]) -> str:
    if not utc_str:
        return "Recent"
    try:
        from datetime import datetime, timedelta
        raw = str(utc_str).strip()
        if "+" in raw:
            raw = raw.split("+")[0]
        if "Z" in raw:
            raw = raw.replace("Z", "")
        raw = raw.replace("T", " ").split(".")[0].strip()
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        dt_ist = dt + timedelta(hours=5, minutes=30)
        dt_aest = dt + timedelta(hours=10)
        return f"{dt_ist.strftime('%d %b %Y, %I:%M %p IST')} ({dt_aest.strftime('%I:%M %p AEST')})"
    except Exception:
        return str(utc_str)[:16]


# Ids the publisher never returned — placeholders that must not be treated as
# proof that a platform accepted the post.
_PLACEHOLDER_POST_IDS = {"", "live verified", "none", "null"}


def _is_real_post_id(post_id: Any) -> bool:
    return str(post_id or "").strip().lower() not in _PLACEHOLDER_POST_IDS


def _dedupe_published_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One row per post.

    The history is stitched together from the campaign queue, a local cache, the
    Meta and LinkedIn APIs and the SQLite table, and the same post routinely
    arrives from more than one of them — which is why the dashboard showed
    identical posts two and three times over. Collapse on the platform's own id
    where there is one, and otherwise on the post's identity (platform, time and
    opening line), keeping the first and richest copy seen.

    `is_live_api` is also corrected here. It was written as a hardcoded True on
    every path, so it claimed platform confirmation for posts that never
    returned an id.
    """
    seen_ids: set = set()
    seen_fallback: set = set()
    deduped: List[Dict[str, Any]] = []

    for item in history:
        post_id = item.get("platform_post_id")
        if _is_real_post_id(post_id):
            key = str(post_id).strip()
            if key in seen_ids:
                continue
            seen_ids.add(key)
        else:
            key = (
                str(item.get("platform", "")).lower(),
                str(item.get("published_at", "")),
                str(item.get("caption", ""))[:60],
            )
            if key in seen_fallback:
                continue
            seen_fallback.add(key)

        item["is_live_api"] = _is_real_post_id(post_id)
        deduped.append(item)

    return deduped


def _derive_page_token(user_token: str, page_id: str) -> Optional[str]:
    """The Page access token that /me/accounts already carries.

    Facebook rejects a user token for a Page's own posts, which is why the
    engagement read failed with "Invalid OAuth 2.0 Access Token". The Page
    token is not a separate thing to go and fetch by hand -- it is returned
    alongside every page the user administers, and on a long-lived user token
    it does not expire.
    """
    try:
        res = requests.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={"fields": "id,access_token", "access_token": user_token},
            timeout=10,
        )
        if res.status_code != 200:
            return None
        for page in res.json().get("data") or []:
            if str(page.get("id")) == str(page_id):
                return page.get("access_token")
    except Exception as e:
        logger.warning(f"Could not derive a Facebook Page token: {e}")
    return None


def _build_social_recommendations(live_accounts, engagement, published_history,
                                  scheduled_queue, unavailable) -> List[str]:
    """Advice from what the accounts actually did, not written in advance."""
    out: List[str] = []

    ig_likes = engagement["instagram"]["likes"]
    ig_posts = engagement["instagram"]["posts_measured"]
    if ig_posts:
        if not ig_likes:
            out.append(
                f"{ig_posts} Instagram posts have drawn no likes at all. Posting more will "
                f"not change that on its own -- the account needs an audience first."
            )
        else:
            out.append(
                f"{ig_posts} Instagram posts have {ig_likes} likes between them "
                f"({round(ig_likes / ig_posts, 1)} per post)."
            )

    followers = {k: v.get("followers") for k, v in live_accounts.items()}
    tiny = [k for k, v in followers.items() if isinstance(v, int) and v < 50]
    if tiny:
        counts = ", ".join(f"{k} {followers[k]}" for k in tiny)
        out.append(
            f"Follower counts are very low ({counts}). Until that changes, organic posts "
            f"reach almost nobody, whatever the posting schedule."
        )

    if not scheduled_queue:
        out.append("Nothing is queued to publish. The schedule is empty.")

    if unavailable:
        out.append(
            f"{len(unavailable)} metrics could not be read from the platforms; see "
            f"metrics_unavailable for the reason on each."
        )
    return out or ["No social activity was found to report on."]


def _posts_site_filter(cur, site_id: str, alias: str = "p"):
    """SQL fragment and parameters restricting posts to one website.

    The posts table gained site_id late; every row written before that belongs
    to Corporate Cars Melbourne, because this was a single-brand database. So
    a NULL counts as ccm and as nothing else -- without this, a new client saw
    CCM's captions listed as its own published posts.
    """
    try:
        columns = [r[1] for r in cur.execute("PRAGMA table_info(posts)")]
    except Exception:
        columns = []
    if "site_id" not in columns:
        # Pre-migration database: all of it is the primary site's.
        return ("1=1" if site_id == "ccm" else "1=0"), []
    if site_id == "ccm":
        return f"({alias}.site_id = ? OR {alias}.site_id IS NULL)", [site_id]
    return f"{alias}.site_id = ?", [site_id]


def linkedin_api_versions(count: int = 6) -> List[str]:
    """Recent LinkedIn-Version values, newest first.

    LinkedIn versions are months (YYYYMM) and only a rolling window is valid,
    so a hardcoded one expires. The current month is not always released yet,
    so this starts at last month and walks back.

    LINKEDIN_API_VERSION overrides it when a specific month is needed.
    """
    pinned = os.getenv("LINKEDIN_API_VERSION", "").strip()
    if pinned:
        return [pinned]

    now = datetime.now()
    year, month = now.year, now.month
    out: List[str] = []
    for _ in range(count):
        month -= 1
        if month == 0:
            month, year = 12, year - 1
        out.append(f"{year}{month:02d}")
    return out


def linkedin_get(url: str, headers: Dict[str, str], params: Dict[str, Any],
                 timeout: int = 10):
    """GET a versioned LinkedIn endpoint, trying recent versions in turn.

    Returns the first response that is not a version rejection, so a genuine
    error (a bad token, a missing permission) is still reported rather than
    retried six times.
    """
    import requests

    last = None
    for version in linkedin_api_versions():
        last = requests.get(url, params=params, timeout=timeout,
                            headers={**headers, "LinkedIn-Version": version})
        if last.status_code != 426:
            return last, version
        logger.info("LinkedIn rejected version %s; trying an older one.", version)
    return last, None


def fetch_real_social_analytics(
    site_id: str = "",
    site_domain: str = "",
    site_name: str = "",
) -> Dict[str, Any]:
    """
    Connects to real corporate-cars-social-agent/social_agent.db and queries live Meta & LinkedIn APIs
    to return 100% accurate real analytics with live post interactions (likes, comments, permalinks).
    Supports multi-tenant sites (Corporate Cars Melbourne, Opal Chauffeurs, etc.).
    """
    db_path = SOCIAL_AGENT_DIR / "social_agent.db"
    
    if site_id == "opal":
        meta_token = os.getenv("OPAL_META_ACCESS_TOKEN", "").strip() or os.getenv("META_USER_TOKEN", "").strip()
        meta_page_id = os.getenv("OPAL_META_PAGE_ID", "102034409405004").strip()
        ig_id = os.getenv("OPAL_INSTAGRAM_BUSINESS_ACCOUNT_ID", "17841456911741892").strip()
        linkedin_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
        linkedin_org = os.getenv("OPAL_LINKEDIN_ORGANIZATION_URN", "urn:li:organization:87379144").strip()
        brand_title = "Opal Chauffeurs"
        brand_vanity = "opalchauffeurs"
        fb_followers = None
        ig_followers = None
        ig_media_count = None
        li_followers = None
    elif site_id == "ccm":
        meta_token = os.getenv("META_USER_TOKEN", "").strip()
        meta_page_id = os.getenv("META_PAGE_ID", "791630667378039").strip()
        ig_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "17841477866530528").strip()
        linkedin_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
        linkedin_org = os.getenv("LINKEDIN_ORGANIZATION_URN", "urn:li:organization:109059206").strip()
        brand_title = "Corporate Cars Melbourne"
        brand_vanity = "corporate-cars-melbourne"
        fb_followers = None
        ig_followers = None
        ig_media_count = None
        li_followers = None
    else:
        # This branch used to be the "else", holding Corporate Cars Melbourne's
        # page ids and brand -- so every site that was not Opal, including any
        # newly added one, was reported as CCM with CCM's Facebook page and
        # Instagram account. A site with no social accounts of its own now gets
        # nothing rather than somebody else's.
        prefix = re.sub(r"[^A-Z0-9]+", "_", (site_id or "").upper()).strip("_")
        meta_token = os.getenv(f"{prefix}_META_ACCESS_TOKEN", "").strip() if prefix else ""
        meta_page_id = os.getenv(f"{prefix}_META_PAGE_ID", "").strip() if prefix else ""
        ig_id = os.getenv(f"{prefix}_INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip() if prefix else ""
        linkedin_token = os.getenv(f"{prefix}_LINKEDIN_ACCESS_TOKEN", "").strip() if prefix else ""
        linkedin_org = os.getenv(f"{prefix}_LINKEDIN_ORGANIZATION_URN", "").strip() if prefix else ""
        brand_title = site_name or site_id or "this website"
        brand_vanity = ""
        fb_followers = None
        ig_followers = None
        ig_media_count = None
        li_followers = None

    live_accounts = {
        "facebook": {"connected": False, "name": brand_title, "page_id": meta_page_id,
                     "followers": fb_followers, "status": "not checked"},
        "instagram": {"connected": False, "username": brand_vanity, "account_id": ig_id,
                      "followers": ig_followers, "media_count": ig_media_count, "status": "not checked"},
        "linkedin": {"connected": False, "name": brand_title, "org_id": linkedin_org,
                     "vanity_name": brand_vanity, "followers": li_followers, "status": "not checked"},
    }
    # Engagement the platforms actually reported, filled in below. Nothing here
    # is estimated: a metric the API would not give stays None.
    engagement = {
        "instagram": {"likes": None, "comments": None, "posts_measured": 0,
                      "impressions": None, "reach": None},
        "facebook": {"likes": None, "comments": None, "posts_measured": 0,
                     "impressions": None, "reach": None},
        "linkedin": {"likes": None, "comments": None, "posts_measured": 0,
                     "impressions": None, "reach": None},
    }
    unavailable: Dict[str, str] = {}

    published_history = []
    scheduled_queue = []
    # Posts the publisher gave up on. Reported rather than dropped: a post that
    # never went out is a thing the operator needs to see, not a silent gap.
    retired_posts: List[Dict[str, Any]] = []
    campaign_queue: List[Dict[str, Any]] = []
    platform_db_counts = {}
    cached_map = {}

    # 0. Load published posts from data/social_scheduled_campaigns.json for this site
    sched_file = ROOT_DIR / "data" / "social_scheduled_campaigns.json"
    if sched_file.exists():
        try:
            with open(sched_file, "r", encoding="utf-8") as sfp:
                camp_posts = json.load(sfp)
                for cp in camp_posts:
                    if cp.get("site") == site_id and cp.get("status") == "scheduled":
                        # Campaigns created from the dashboard live here, not in
                        # the publisher's database, so reading only that
                        # database showed an empty queue while thirty posts
                        # were waiting.
                        campaign_queue.append({
                            "id": cp.get("id"),
                            "platform": (cp.get("platform") or "").capitalize(),
                            "title": (cp.get("caption") or "").split("\n")[0][:80],
                            "scheduled_for": (cp.get("scheduled_for") or "").replace(
                                " (Melbourne Time)", ""),
                            "scheduled_for_iso": sortable_timestamp(cp.get("scheduled_for")),
                            "source": "campaign",
                        })
                    if cp.get("site") == site_id and cp.get("status") == "expired":
                        retired_posts.append({
                            "id": cp.get("id"),
                            "platform": (cp.get("platform") or "").capitalize(),
                            "scheduled_for": (cp.get("scheduled_for") or "").replace(
                                " (Melbourne Time)", ""),
                            "retired_at": (cp.get("expired_at") or "").replace(
                                " (Melbourne Time)", ""),
                            "reason": cp.get("expired_reason") or "Missed its slot.",
                            "title": (cp.get("caption") or "").split("\n")[0][:80],
                        })
                    if cp.get("site") == site_id and cp.get("status") == "published":
                        # The publisher records the id as "platform_post_id";
                        # only campaigns from the retired engine use "post_id".
                        # Reading the old key alone left every current record
                        # with a blank id, which then failed the SQLite
                        # de-duplication below and listed each post twice.
                        pid = cp.get("platform_post_id") or cp.get("post_id", "")
                        plat = cp.get("platform", "LinkedIn").capitalize()
                        cap = cp.get("caption", "")
                        title = cap.split("\n")[0] if cap else f"{plat} Post"
                        if len(title) > 75:
                            title = title[:72] + "..."
                        
                        # Build permalink URL
                        if plat.lower() == "linkedin":
                            post_url = f"https://www.linkedin.com/company/{brand_vanity}/"
                        elif plat.lower() == "facebook":
                            post_url = f"https://www.facebook.com/{meta_page_id}"
                        else:
                            post_url = f"https://www.instagram.com/{brand_vanity}/"

                        published_history.append({
                            "id": cp.get("id", f"pub_{site_id}"),
                            "platform": plat,
                            "title": title,
                            "caption": cap,
                            "hashtags": cp.get("hashtags", ""),
                            "platform_post_id": pid,
                            "published_at": cp.get("published_at", "Today"),
                            "published_at_iso": sortable_timestamp(
                                cp.get("published_at_utc") or cp.get("published_at")),
                            "likes": 1,
                            "comments": 0,
                            "url": post_url,
                            "image_name": cp.get("image_name", "fleet-photo.jpg"),
                            "is_live_api": True
                        })
        except Exception as e:
            logger.warning(f"Failed to read social_scheduled_campaigns.json: {e}")

    # 0b. Load verified live social cache if exists (for CCM)
    if site_id == "ccm":
        cache_path = SOCIAL_AGENT_DIR / "live_social_cache.json"
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as cfp:
                    cached_items = json.load(cfp)
                    for ci in cached_items:
                        pid = ci.get("platform_post_id")
                        if pid:
                            cached_map[pid] = ci
                            published_history.append({
                                "id": ci.get("id"),
                                "platform": ci.get("platform"),
                                "title": ci.get("title"),
                                "caption": ci.get("caption", ""),
                                "hashtags": "",
                                "platform_post_id": pid,
                                "published_at": format_utc_to_display(ci.get("timestamp")),
                                "likes": ci.get("likes", 0),
                                "comments": ci.get("comments", 0),
                                "url": ci.get("url"),
                                "is_live_api": True
                            })
            except Exception as e:
                logger.warning(f"Failed to read live_social_cache.json: {e}")

    # 1. Fetch live Instagram Posts directly from Meta Graph API if token available
    if meta_token and ig_id:
        try:
            url_ig = f"https://graph.facebook.com/v19.0/{ig_id}/media?fields=id,caption,media_type,permalink,timestamp,like_count,comments_count&limit=25&access_token={meta_token}"
            r_ig = requests.get(url_ig, timeout=3)
            if r_ig.status_code == 200:
                live_items = r_ig.json().get("data", [])
                if live_items:
                    for idx, m in enumerate(live_items):
                        caption = m.get("caption", "").strip()
                        first_line = caption.split("\n")[0] if caption else "Instagram Post"
                        if len(first_line) > 75:
                            first_line = first_line[:72] + "..."
                        item_obj = {
                            "id": f"ig_{m.get('id')[-4:]}",
                            "platform": "Instagram",
                            "title": first_line,
                            "caption": caption,
                            "hashtags": "",
                            "platform_post_id": m.get("id"),
                            "published_at": format_utc_to_display(m.get("timestamp")),
                            "published_at_iso": sortable_timestamp(m.get("timestamp")),
                            "likes": m.get("like_count", 0),
                            "comments": m.get("comments_count", 0),
                            "url": m.get("permalink", f"https://www.instagram.com/p/{m.get('id')}/"),
                            "is_live_api": True
                        }
                        cached_map[m.get("id")] = item_obj
                        published_history.append(item_obj)
        except Exception as e:
            logger.warning(f"Failed to query live IG media: {e}")

    # 2. Fetch live Facebook Feed from Meta Graph API
    if meta_token and meta_page_id:
        try:
            url_fb = f"https://graph.facebook.com/v19.0/{meta_page_id}/feed?fields=id,message,created_time,permalink_url,likes.summary(true),comments.summary(true)&limit=15&access_token={meta_token}"
            r_fb = requests.get(url_fb, timeout=3)
            if r_fb.status_code == 200:
                fb_items = r_fb.json().get("data", [])
                if fb_items:
                    for f in fb_items:
                        msg = f.get("message", "").strip()
                        first_line = msg.split("\n")[0] if msg else "Facebook Post"
                        if len(first_line) > 75:
                            first_line = first_line[:72] + "..."
                        likes_cnt = f.get("likes", {}).get("summary", {}).get("total_count", 0)
                        comments_cnt = f.get("comments", {}).get("summary", {}).get("total_count", 0)
                        item_obj = {
                            "id": f"fb_{f.get('id')[-4:]}",
                            "platform": "Facebook",
                            "title": first_line,
                            "caption": msg,
                            "hashtags": "",
                            "platform_post_id": f.get("id"),
                            "published_at": format_utc_to_display(f.get("created_time")),
                            "published_at_iso": sortable_timestamp(f.get("created_time")),
                            "likes": likes_cnt,
                            "comments": comments_cnt,
                            "url": f.get("permalink_url", f"https://facebook.com/{f.get('id')}"),
                            "is_live_api": True
                        }
                        cached_map[f.get("id")] = item_obj
                        published_history.append(item_obj)
        except Exception as e:
            logger.warning(f"Failed to query live FB feed: {e}")

    # 3. Query local DB for scheduled queue & LinkedIn published posts
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            # Breakdown counts
            # The aggregate query names the table; the two below alias it "p".
            _where_t, _params = _posts_site_filter(cur, site_id, "posts")
            _where, _ = _posts_site_filter(cur, site_id, "p")
            cur.execute(
                f"SELECT platform, status, count(*) FROM posts WHERE {_where_t} "
                "GROUP BY platform, status", _params)
            for plat, stat, count in cur.fetchall():
                plat = plat.lower()
                if plat not in platform_db_counts:
                    platform_db_counts[plat] = {"published": 0, "scheduled": 0, "draft": 0}
                if stat in platform_db_counts[plat]:
                    platform_db_counts[plat][stat] = count

            # Fetch all published posts from DB across LinkedIn, Facebook, and Instagram
            cur.execute("""
                SELECT p.id, p.platform, p.caption, p.hashtags, p.platform_post_id, s.publish_at, p.created_at
                FROM posts p
                LEFT JOIN schedule s ON s.post_id = p.id
                WHERE p.status = 'published' AND """ + _where + """
                ORDER BY COALESCE(s.publish_at, p.created_at) DESC
            """, _params)
            existing_ids = {str(p.get("platform_post_id")) for p in published_history if p.get("platform_post_id")}
            existing_titles = {str(p.get("title", ""))[:35].lower() for p in published_history if p.get("title")}
            for r in cur.fetchall():
                pid = str(r[4] or "")
                caption_clean = r[2].strip() if r[2] else ""
                first_line = caption_clean.split("\n")[0] if caption_clean else f"Post #{r[0]}"
                if len(first_line) > 75:
                    first_line = first_line[:72] + "..."
                
                # Deduplicate by platform_post_id or matching opening title
                if pid and pid in existing_ids:
                    continue
                if first_line[:35].lower() in existing_titles and r[1].lower() == "instagram":
                    continue
                plat = r[1].lower()
                
                # Check if we have cached metrics
                post_likes = 0
                post_comments = 0
                if pid in cached_map:
                    post_likes = cached_map[pid].get("likes", 0)
                    post_comments = cached_map[pid].get("comments", 0)

                # Construct platform-specific live permalink URL
                if plat == "instagram":
                    post_url = f"https://www.instagram.com/p/{pid}/" if (pid.startswith("18") or pid.startswith("Dc")) else ""
                elif plat == "facebook":
                    if "_" in pid:
                        page_id, post_fbid = pid.split("_", 1)
                        post_url = f"https://www.facebook.com/permalink.php?story_fbid={post_fbid}&id={page_id}"
                    else:
                        post_url = f"https://www.facebook.com/profile.php?id={meta_page_id}"
                elif plat == "linkedin":
                    if pid.startswith("urn:li:"):
                        post_url = f"https://www.linkedin.com/feed/update/{pid}/"
                    else:
                        post_url = "https://www.linkedin.com/company/corporate-cars-melbourne/"
                else:
                    post_url = site_domain

                published_history.append({
                    "id": f"s{r[0]:04d}",
                    "platform": r[1].capitalize(),
                    "title": first_line,
                    "caption": caption_clean,
                    "hashtags": r[3] or "",
                    "platform_post_id": pid or "Live Verified",
                    "published_at": format_utc_to_display(r[5] or r[6]),
                    "published_at_iso": sortable_timestamp(r[5] or r[6]),
                    "likes": post_likes,
                    "comments": post_comments,
                    "url": post_url,
                    "is_live_api": True
                })

            # Upcoming scheduled queue
            cur.execute("""
                SELECT p.id, p.platform, p.caption, s.publish_at
                FROM posts p
                LEFT JOIN schedule s ON s.post_id = p.id
                WHERE (p.status = 'scheduled' OR (s.published = 0 AND s.publish_at IS NOT NULL))
                  AND """ + _where + """
                ORDER BY s.publish_at ASC
            """, _params)
            for r in cur.fetchall():
                caption_clean = r[2].strip() if r[2] else ""
                first_line = caption_clean.split("\n")[0] if caption_clean else f"Post #{r[0]}"
                if len(first_line) > 70:
                    first_line = first_line[:67] + "..."
                scheduled_queue.append({
                    "id": f"s{r[0]:04d}",
                    "platform": r[1].capitalize(),
                    "title": first_line,
                    "time": format_utc_to_display(r[3])
                })

            conn.close()
        except Exception as e:
            logger.warning(f"Failed to query social_agent.db: {e}")

    # Live Meta FB Page telemetry
    if meta_token and meta_page_id:
        try:
            r_fb = requests.get(f"https://graph.facebook.com/v19.0/{meta_page_id}?fields=name,followers_count,fan_count&access_token={meta_token}", timeout=8)
            if r_fb.status_code == 200:
                data_fb = r_fb.json()
                live_accounts["facebook"]["connected"] = True
                live_accounts["facebook"]["status"] = "reachable"
                live_accounts["facebook"]["name"] = data_fb.get("name") or brand_title
                # `or 1` used to stand in when the field was absent, reporting a
                # follower the page may not have.
                live_accounts["facebook"]["followers"] = data_fb.get(
                    "followers_count", data_fb.get("fan_count"))
            else:
                unavailable["facebook_account"] = f"HTTP {r_fb.status_code} from the Meta Graph API"
        except Exception as e:
            logger.warning(f"Meta FB live fetch failed: {e}")
            unavailable["facebook_account"] = str(e)

        # A Page token is required for the Page's own posts. It is already
        # inside the user token's /me/accounts response, so it is taken from
        # there rather than asked of the operator.
        page_token = _derive_page_token(meta_token, meta_page_id)
        if not page_token:
            unavailable["facebook_engagement"] = (
                "No Facebook Page access token could be derived from the configured user "
                "token. The account may no longer administer this Page."
            )
        else:
            try:
                r_posts = requests.get(
                    f"https://graph.facebook.com/v19.0/{meta_page_id}/posts",
                    params={"fields": "id,created_time,reactions.summary(true),comments.summary(true)",
                            "limit": 50, "access_token": page_token},
                    timeout=12,
                )
                if r_posts.status_code == 200:
                    posts = r_posts.json().get("data") or []
                    engagement["facebook"]["posts_measured"] = len(posts)
                    engagement["facebook"]["likes"] = sum(
                        ((pp.get("reactions") or {}).get("summary") or {}).get("total_count", 0)
                        for pp in posts
                    )
                    engagement["facebook"]["comments"] = sum(
                        ((pp.get("comments") or {}).get("summary") or {}).get("total_count", 0)
                        for pp in posts
                    )
                else:
                    detail = ""
                    try:
                        detail = r_posts.json().get("error", {}).get("message", "")
                    except Exception:
                        detail = r_posts.text[:120]
                    # Reactions and comments need pages_read_user_content on top
                    # of the Page token.
                    unavailable["facebook_engagement"] = detail or f"HTTP {r_posts.status_code}"
            except Exception as e:
                logger.warning(f"Facebook post engagement fetch failed: {e}")
                unavailable["facebook_engagement"] = str(e)

    # Meta IG Business
    if meta_token and ig_id:
        try:
            r_ig = requests.get(f"https://graph.facebook.com/v19.0/{ig_id}?fields=username,followers_count,media_count&access_token={meta_token}", timeout=8)
            if r_ig.status_code == 200:
                data_ig = r_ig.json()
                live_accounts["instagram"]["connected"] = True
                live_accounts["instagram"]["username"] = data_ig.get("username", "")
                live_accounts["instagram"]["status"] = "reachable"
                live_accounts["instagram"]["followers"] = data_ig.get("followers_count")
                live_accounts["instagram"]["media_count"] = data_ig.get("media_count")
            else:
                unavailable["instagram_account"] = f"HTTP {r_ig.status_code} from the Instagram Graph API"
        except Exception as e:
            logger.warning(f"Meta IG live fetch failed: {e}")
            unavailable["instagram_account"] = str(e)

        # Real per-post engagement. This replaces "impressions: 24500, clicks:
        # 1210, likes: 890, engagement_rate: 6.2%", which were literals.
        try:
            r_media = requests.get(
                f"https://graph.facebook.com/v19.0/{ig_id}/media",
                params={"fields": "id,timestamp,permalink,like_count,comments_count",
                        "limit": 50, "access_token": meta_token},
                timeout=12,
            )
            if r_media.status_code == 200:
                media = r_media.json().get("data") or []
                engagement["instagram"]["posts_measured"] = len(media)
                engagement["instagram"]["likes"] = sum(m.get("like_count", 0) for m in media)
                engagement["instagram"]["comments"] = sum(m.get("comments_count", 0) for m in media)
            else:
                unavailable["instagram_engagement"] = f"HTTP {r_media.status_code} reading Instagram media"
        except Exception as e:
            logger.warning(f"Instagram media fetch failed: {e}")
            unavailable["instagram_engagement"] = str(e)

        # Reach and impressions need instagram_manage_insights, which this
        # token does not carry -- the API answers "Application does not have
        # permission for this action".
        unavailable["instagram_reach"] = (
            "Instagram reach and impressions need the instagram_manage_insights "
            "permission, which this access token does not have."
        )

    # LinkedIn Org
    if linkedin_token and linkedin_org:
        try:
            org_id = linkedin_org.replace("urn:li:organization:", "")
            headers = {"Authorization": f"Bearer {linkedin_token}", "X-Restli-Protocol-Version": "2.0.0"}
            r_li = requests.get(f"https://api.linkedin.com/v2/organizations/{org_id}", headers=headers, timeout=8)
            if r_li.status_code == 200:
                data_li = r_li.json()
                live_accounts["linkedin"]["connected"] = True
                live_accounts["linkedin"]["status"] = "reachable"
                live_accounts["linkedin"]["name"] = data_li.get("localizedName") or brand_title
                live_accounts["linkedin"]["vanity_name"] = data_li.get("vanityName") or brand_vanity
            else:
                unavailable["linkedin_account"] = f"HTTP {r_li.status_code} from the LinkedIn API"

            # The follower count lives behind networkSizes, and the URN has to
            # be percent-encoded in the path or LinkedIn answers "Syntax
            # exception in path variables".
            from urllib.parse import quote

            r_net, used_version = linkedin_get(
                "https://api.linkedin.com/rest/networkSizes/" + quote(linkedin_org, safe=""),
                headers,
                # LinkedIn renamed this enum to SCREAMING_SNAKE_CASE; the old
                # spelling now answers 400 "is not an enum symbol".
                {"edgeType": "COMPANY_FOLLOWED_BY_MEMBER"},
            )
            if r_net is not None and r_net.status_code == 200:
                live_accounts["linkedin"]["followers"] = r_net.json().get("firstDegreeSize")
                live_accounts["linkedin"]["api_version"] = used_version
            elif r_net is not None and r_net.status_code == 426:
                unavailable["linkedin_followers"] = (
                    "LinkedIn rejected every recent API version it was offered "
                    f"({', '.join(linkedin_api_versions())}). Set "
                    "LINKEDIN_API_VERSION to a month LinkedIn currently accepts."
                )
            else:
                code = r_net.status_code if r_net is not None else "no response"
                unavailable["linkedin_followers"] = f"HTTP {code} reading the follower count"
        except Exception as e:
            logger.warning(f"LinkedIn live fetch failed: {e}")
            unavailable["linkedin_account"] = str(e)

    # These fell back to 6 published and 7 scheduled per platform whenever the
    # publisher's database had nothing for that platform.
    empty_counts = {"published": 0, "scheduled": 0}
    fb_counts = platform_db_counts.get("facebook", empty_counts)
    ig_counts = platform_db_counts.get("instagram", empty_counts)
    li_counts = platform_db_counts.get("linkedin", empty_counts)

    # The publisher's database and the campaign file each hold part of the
    # queue; the panel needs both, in one order.
    scheduled_queue = scheduled_queue + campaign_queue
    scheduled_queue.sort(key=lambda q: q.get("scheduled_for_iso") or q.get("publish_at") or "")

    next_fb = next((s for s in scheduled_queue if s["platform"].lower() == "facebook"), None)
    next_ig = next((s for s in scheduled_queue if s["platform"].lower() == "instagram"), None)
    next_li = next((s for s in scheduled_queue if s["platform"].lower() == "linkedin"), None)

    published_history = _dedupe_published_history(published_history)
    # Newest first. Rows whose date could not be read sort last rather than
    # landing at the top on an empty string.
    published_history.sort(key=lambda p: p.get("published_at_iso") or "", reverse=True)

    return {
        "live_connected_accounts": live_accounts,
        "platforms": {
            "facebook": {
                "published": fb_counts.get("published", 0),
                "scheduled": fb_counts.get("scheduled", 0),
                # A fixed date in the past used to stand here whenever nothing
                # was queued, so the panel always named a "next post".
                "next_scheduled_at": next_fb["time"] if next_fb else None,
                "followers": live_accounts["facebook"]["followers"],
                "account_name": live_accounts["facebook"]["name"],
                "likes": engagement["facebook"]["likes"],
                "comments": engagement["facebook"]["comments"],
                "posts_measured": engagement["facebook"]["posts_measured"],
                "impressions": None,
                "reach": None,
                "connected": live_accounts["facebook"]["connected"],
                "status": live_accounts["facebook"]["status"],
            },
            "instagram": {
                "published": ig_counts.get("published", 0),
                "scheduled": ig_counts.get("scheduled", 0),
                "next_scheduled_at": next_ig["time"] if next_ig else None,
                "followers": live_accounts["instagram"]["followers"],
                "media_count": live_accounts["instagram"]["media_count"],
                "account_handle": f"@{live_accounts['instagram']['username']}",
                # Counted off the posts themselves, not estimated.
                "likes": engagement["instagram"]["likes"],
                "comments": engagement["instagram"]["comments"],
                "posts_measured": engagement["instagram"]["posts_measured"],
                "impressions": None,
                "reach": None,
                "connected": live_accounts["instagram"]["connected"],
                "status": live_accounts["instagram"]["status"],
            },
            "linkedin": {
                "published": li_counts.get("published", 0),
                "scheduled": li_counts.get("scheduled", 0),
                "next_scheduled_at": next_li["time"] if next_li else None,
                "account_name": live_accounts["linkedin"]["name"],
                "followers": live_accounts["linkedin"]["followers"],
                "page_url": f"https://www.linkedin.com/company/{live_accounts['linkedin'].get('vanity_name') or brand_vanity}",
                "likes": engagement["linkedin"]["likes"],
                "comments": engagement["linkedin"]["comments"],
                "posts_measured": engagement["linkedin"]["posts_measured"],
                "impressions": None,
                "reach": None,
                "connected": live_accounts["linkedin"]["connected"],
                "status": live_accounts["linkedin"]["status"],
            }
        },
        "total_published_posts": len(published_history),
        "total_scheduled_queue": len(scheduled_queue),
        "published_posts_history": published_history,
        "next_scheduled_posts": scheduled_queue[:15],
        "retired_posts": retired_posts,
        "retired_posts_note": (
            "These were scheduled but never published: each missed its slot by "
            "more than this website's allowance, so the publisher retired it "
            "rather than posting it at the wrong hour. Re-schedule anything "
            "here that still matters."
        ),
        "engagement_measured": engagement,
        "metrics_unavailable": unavailable,
        "measurement_note": (
            "Likes and comments are counted off the posts themselves. Reach, impressions "
            "and engagement rate are not shown: no connected platform will report them to "
            "this access token, and the figures that used to appear here were written into "
            "the source."
        ),
        "weekly_recommendations": _build_social_recommendations(
            live_accounts, engagement, published_history, scheduled_queue, unavailable
        ),
    }


class SocialAnalyticsAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="social-analytics-agent",
            name="Social Media Analytics Agent",
            description="Analyzes real organic reach, engagement, published posts history, and connected account metrics across Instagram, Facebook, and LinkedIn.",
            category="Social Media",
            enabled=True,
            paused=False,
            supported_actions=["fetch_analytics", "top_posts", "platform_breakdown", "follower_growth"],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "fetch_analytics")).lower().strip()
        platform = str(input_data.get("platform", "all")).lower().strip()
        date_range = str(input_data.get("date_range", "last_30_days")).strip()
        use_ai = bool(input_data.get("use_ai", False))

        logger.info(f"Executing SocialAnalyticsAgent task: action={action}, platform='{platform}', date_range='{date_range}'")

        from config.site_context import site_identity

        site_id = str(
            input_data.get("site_id") or getattr(task, "site_id", None) or ""
        ).strip().lower()
        identity = site_identity(site_id)

        # This was called with no arguments, so every run reported the default
        # site's accounts whatever site the task named.
        real_data = fetch_real_social_analytics(
            site_id=site_id,
            site_domain=identity["domain"],
            site_name=identity["name"],
        )

        # Adding the follower counts used to assume both were numbers. They are
        # None when a platform did not answer, and None is not zero.
        follower_values = [
            p.get("followers") for p in real_data["platforms"].values()
            if isinstance(p.get("followers"), int)
        ]
        total_followers = sum(follower_values) if follower_values else None

        measured = real_data.get("engagement_measured") or {}
        likes = [m.get("likes") for m in measured.values() if isinstance(m.get("likes"), int)]
        comments = [m.get("comments") for m in measured.values() if isinstance(m.get("comments"), int)]

        result_payload = {
            "action": action,
            "selected_platform": platform,
            "date_range": date_range,
            "overall_summary": {
                "total_followers": total_followers,
                "followers_counted_on": len(follower_values),
                "total_published_posts": real_data["total_published_posts"],
                "total_scheduled_queue": real_data["total_scheduled_queue"],
                # 55,000 impressions, 3,700 engagements and a 5.43% engagement
                # rate stood here as literals. No connected platform reports
                # reach or impressions to this token, so they are not reported.
                "total_likes": sum(likes) if likes else None,
                "total_comments": sum(comments) if comments else None,
                "total_impressions": None,
                "total_reach": None,
                "avg_engagement_rate_percent": None,
            },
            "metrics_unavailable": real_data.get("metrics_unavailable", {}),
            "measurement_note": real_data.get("measurement_note"),
            "live_connected_accounts": real_data["live_connected_accounts"],
            "platform_breakdown": real_data["platforms"],
            "published_posts_history": real_data["published_posts_history"][:10],
            "next_scheduled_posts": real_data["next_scheduled_posts"],
            # run_task rebuilds the output field by field, so anything the
            # fetch adds has to be listed here or the panel never sees it.
            "retired_posts": real_data.get("retired_posts", []),
            "retired_posts_note": real_data.get("retired_posts_note", ""),
            "total_scheduled_queue": real_data.get("total_scheduled_queue"),
            "actionable_recommendations": real_data["weekly_recommendations"]
        }

        # Optional AI Enrichment
        tokens_used = 0
        cost_usd = 0.0
        model_used = "live-social-db-and-api-telemetry-engine"

        if use_ai:
            prompt = (
                f"Analyze social media performance metrics across channels: {real_data['platforms']}. "
                f"Identify top content pillars to double down on and optimal posting times."
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
                logger.warning(f"AI social analytics failed (fallback to telemetry engine): {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd
        }
