"""
X (Twitter) publisher — API v2 for the tweet, v1.1 for media upload.
Uses OAuth 1.0a user-context signing (requests-oauthlib).

Requires: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET.
App must have Read & Write permissions (Free tier allows posting).
"""

import logging

import requests
from requests_oauthlib import OAuth1

from config import X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET, X_API_KEY, X_API_SECRET
from models import Post
from publishers.base import PublishError, full_text, image_local_path, require

log = logging.getLogger(__name__)

MEDIA_UPLOAD = "https://upload.twitter.com/1.1/media/upload.json"
TWEETS = "https://api.twitter.com/2/tweets"


def _auth() -> OAuth1:
    return OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)


def publish(post: Post) -> str:
    require("x", X_API_KEY=X_API_KEY, X_API_SECRET=X_API_SECRET,
            X_ACCESS_TOKEN=X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET=X_ACCESS_TOKEN_SECRET)
    auth = _auth()

    media_ids = []
    path = image_local_path(post)
    if path:
        with open(path, "rb") as f:
            r = requests.post(MEDIA_UPLOAD, files={"media": f}, auth=auth, timeout=120)
        if r.status_code not in (200, 201):
            raise PublishError(f"x media upload failed: {r.status_code} {r.text[:300]}")
        media_ids = [r.json()["media_id_string"]]

    payload: dict = {"text": full_text(post)[:280]}
    if media_ids:
        payload["media"] = {"media_ids": media_ids}

    r = requests.post(TWEETS, json=payload, auth=auth, timeout=60)
    if r.status_code != 201:
        raise PublishError(f"x tweet failed: {r.status_code} {r.text[:300]}")
    return r.json()["data"]["id"]
