"""
LinkedIn organisation-page publisher — LinkedIn REST API.
Uploads the local image (registerUpload -> PUT binary), then creates a UGC post.

Requires: LINKEDIN_ACCESS_TOKEN, LINKEDIN_ORGANIZATION_URN
          (e.g. urn:li:organization:12345678).
Token scope: w_organization_social (via a LinkedIn Developer app with
Community Management / Marketing Developer Platform access).
"""

import logging

import requests

from config import LINKEDIN_ACCESS_TOKEN, LINKEDIN_ORGANIZATION_URN
from models import Post
from publishers.base import PublishError, full_text, image_local_path, require

log = logging.getLogger(__name__)
API = "https://api.linkedin.com/v2"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "X-Restli-Protocol-Version": "2.0.0",
    }


def _upload_image(path) -> str:
    register = requests.post(
        f"{API}/assets?action=registerUpload",
        headers=_headers(),
        json={
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": LINKEDIN_ORGANIZATION_URN,
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

    with open(path, "rb") as f:
        put = requests.put(upload_url, data=f,
                           headers={"Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}"},
                           timeout=120)
    if put.status_code not in (200, 201):
        raise PublishError(f"linkedin image upload failed: {put.status_code} {put.text[:300]}")
    return asset


def publish(post: Post) -> str:
    require("linkedin",
            LINKEDIN_ACCESS_TOKEN=LINKEDIN_ACCESS_TOKEN,
            LINKEDIN_ORGANIZATION_URN=LINKEDIN_ORGANIZATION_URN)

    media = []
    path = image_local_path(post)
    if path:
        asset = _upload_image(path)
        media = [{"status": "READY", "media": asset}]

    body = {
        "author": LINKEDIN_ORGANIZATION_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": full_text(post)},
                "shareMediaCategory": "IMAGE" if media else "NONE",
                **({"media": media} if media else {}),
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    r = requests.post(f"{API}/ugcPosts", headers=_headers(), json=body, timeout=60)
    if r.status_code != 201:
        raise PublishError(f"linkedin post failed: {r.status_code} {r.text[:300]}")
    return r.headers.get("x-restli-id") or r.json().get("id", "")
