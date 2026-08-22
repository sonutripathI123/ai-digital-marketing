"""
Instagram publisher — Meta Graph API content publishing.
Two-step: create a media container, then publish it.
Requires: META_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID, and a public
image URL (IMAGE_BASE_URL) — the Graph API fetches the image itself.

Token scopes needed: instagram_basic, instagram_content_publish,
pages_read_engagement (via a Facebook Page linked to the IG business account).
"""

import logging

import requests

from config import INSTAGRAM_BUSINESS_ACCOUNT_ID, META_ACCESS_TOKEN
from models import Post
from publishers.base import PublishError, full_text, image_public_url, require, validate_post_integrity

log = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v21.0"


def publish(post: Post) -> str:
    require("instagram",
            META_ACCESS_TOKEN=META_ACCESS_TOKEN,
            INSTAGRAM_BUSINESS_ACCOUNT_ID=INSTAGRAM_BUSINESS_ACCOUNT_ID)
    validate_post_integrity(post, "instagram")

    image_url = image_public_url(post)
    if not image_url:
        raise PublishError(
            "instagram: post has no public image URL — set IMAGE_BASE_URL and attach an image",
            retryable=False,
        )

    r = requests.post(
        f"{GRAPH}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media",
        data={"image_url": image_url, "caption": full_text(post),
              "access_token": META_ACCESS_TOKEN},
        timeout=60,
    )
    if r.status_code != 200:
        raise PublishError(f"instagram container creation failed: {r.status_code} {r.text[:300]}")
    creation_id = r.json()["id"]

    r = requests.post(
        f"{GRAPH}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish",
        data={"creation_id": creation_id, "access_token": META_ACCESS_TOKEN},
        timeout=60,
    )
    if r.status_code != 200:
        raise PublishError(f"instagram publish failed: {r.status_code} {r.text[:300]}")
    return r.json()["id"]
