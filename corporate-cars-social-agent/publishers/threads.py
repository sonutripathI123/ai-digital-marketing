"""
Threads publisher — Threads Graph API (graph.threads.net).
Two-step like Instagram: create a container, then publish.

Requires: THREADS_ACCESS_TOKEN, THREADS_USER_ID, and a public image URL
for image posts (falls back to text-only if no IMAGE_BASE_URL).
Token scopes: threads_basic, threads_content_publish.
"""

import logging

import requests

from config import THREADS_ACCESS_TOKEN, THREADS_USER_ID
from models import Post
from publishers.base import PublishError, full_text, image_public_url, require

log = logging.getLogger(__name__)
API = "https://graph.threads.net/v1.0"


def publish(post: Post) -> str:
    require("threads", THREADS_ACCESS_TOKEN=THREADS_ACCESS_TOKEN, THREADS_USER_ID=THREADS_USER_ID)

    image_url = image_public_url(post)
    data = {"text": full_text(post)[:500], "access_token": THREADS_ACCESS_TOKEN}
    if image_url:
        data.update({"media_type": "IMAGE", "image_url": image_url})
    else:
        data["media_type"] = "TEXT"

    r = requests.post(f"{API}/{THREADS_USER_ID}/threads", data=data, timeout=60)
    if r.status_code != 200:
        raise PublishError(f"threads container creation failed: {r.status_code} {r.text[:300]}")
    creation_id = r.json()["id"]

    r = requests.post(
        f"{API}/{THREADS_USER_ID}/threads_publish",
        data={"creation_id": creation_id, "access_token": THREADS_ACCESS_TOKEN},
        timeout=60,
    )
    if r.status_code != 200:
        raise PublishError(f"threads publish failed: {r.status_code} {r.text[:300]}")
    return r.json()["id"]
