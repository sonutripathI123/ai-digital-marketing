"""
Facebook Page publisher — Meta Graph API.
Posts a photo (with caption) to the Page if an image URL is available,
otherwise a plain text post to the feed.

Requires: META_ACCESS_TOKEN (Page access token), META_PAGE_ID.
Token scopes: pages_manage_posts, pages_read_engagement.
"""

import logging

import requests

from config import META_ACCESS_TOKEN, META_PAGE_ID, OPAL_META_ACCESS_TOKEN, OPAL_META_PAGE_ID
from models import Post
from publishers.base import PublishError, full_text, image_public_url, require, validate_post_integrity

log = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v21.0"


def publish(post: Post) -> str:
    site = getattr(post, "site", getattr(post, "site_id", "ccm"))
    if str(site).lower() == "opal":
        access_token = OPAL_META_ACCESS_TOKEN or META_ACCESS_TOKEN
        page_id = OPAL_META_PAGE_ID or "102034409405004"
    else:
        access_token = META_ACCESS_TOKEN
        page_id = META_PAGE_ID

    require("facebook", META_ACCESS_TOKEN=access_token, META_PAGE_ID=page_id)
    validate_post_integrity(post, "facebook")

    image_url = image_public_url(post)
    if not image_url:
        raise PublishError("facebook: Missing public image URL — image is strictly mandatory.", retryable=False)

    r = requests.post(
        f"{GRAPH}/{page_id}/photos",
        data={"url": image_url, "message": full_text(post),
              "access_token": access_token},
        timeout=60,
    )
    if r.status_code != 200:
        raise PublishError(f"facebook publish failed: {r.status_code} {r.text[:300]}")
    body = r.json()
    return body.get("post_id") or body.get("id", "")
