"""
Facebook Page publisher — Meta Graph API.
Posts a photo (with caption) to the Page if an image URL is available,
otherwise a plain text post to the feed.

Requires: META_ACCESS_TOKEN (Page access token), META_PAGE_ID.
Token scopes: pages_manage_posts, pages_read_engagement.
"""

import logging

import requests

from config import META_ACCESS_TOKEN, META_PAGE_ID
from models import Post
from publishers.base import PublishError, full_text, image_public_url, require

log = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v21.0"


def publish(post: Post) -> str:
    require("facebook", META_ACCESS_TOKEN=META_ACCESS_TOKEN, META_PAGE_ID=META_PAGE_ID)

    image_url = image_public_url(post)
    if image_url:
        r = requests.post(
            f"{GRAPH}/{META_PAGE_ID}/photos",
            data={"url": image_url, "message": full_text(post),
                  "access_token": META_ACCESS_TOKEN},
            timeout=60,
        )
    else:
        r = requests.post(
            f"{GRAPH}/{META_PAGE_ID}/feed",
            data={"message": full_text(post), "access_token": META_ACCESS_TOKEN},
            timeout=60,
        )
    if r.status_code != 200:
        raise PublishError(f"facebook publish failed: {r.status_code} {r.text[:300]}")
    body = r.json()
    return body.get("post_id") or body.get("id", "")
