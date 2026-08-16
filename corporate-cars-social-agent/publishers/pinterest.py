"""
Pinterest publisher — Pinterest API v5.
Creates a pin on PINTEREST_BOARD_ID from a public image URL.
First caption line becomes the pin title; the rest is the description.

Requires: PINTEREST_ACCESS_TOKEN, PINTEREST_BOARD_ID, IMAGE_BASE_URL.
Token scopes: pins:write, boards:read.
"""

import logging

import requests

from config import PINTEREST_ACCESS_TOKEN, PINTEREST_BOARD_ID, WEBSITE_URL
from models import Post
from publishers.base import PublishError, image_public_url, require

log = logging.getLogger(__name__)
API = "https://api.pinterest.com/v5"


def publish(post: Post) -> str:
    require("pinterest",
            PINTEREST_ACCESS_TOKEN=PINTEREST_ACCESS_TOKEN,
            PINTEREST_BOARD_ID=PINTEREST_BOARD_ID)

    image_url = image_public_url(post)
    if not image_url:
        raise PublishError(
            "pinterest: post has no public image URL — set IMAGE_BASE_URL and attach an image",
            retryable=False,
        )

    lines = post.caption.split("\n", 1)
    title = lines[0][:100]
    description = (lines[1].strip() if len(lines) > 1 else post.caption)[:500]

    r = requests.post(
        f"{API}/pins",
        headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}"},
        json={
            "board_id": PINTEREST_BOARD_ID,
            "title": title,
            "description": description,
            "link": WEBSITE_URL,
            "media_source": {"source_type": "image_url", "url": image_url},
        },
        timeout=60,
    )
    if r.status_code != 201:
        raise PublishError(f"pinterest pin failed: {r.status_code} {r.text[:300]}")
    return r.json()["id"]
