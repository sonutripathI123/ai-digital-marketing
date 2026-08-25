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
from publishers.base import PublishError, full_text, image_local_path, require, validate_post_integrity

log = logging.getLogger(__name__)
API = "https://api.linkedin.com/v2"

OPAL_LINKEDIN_ORG_URN = "urn:li:organization:87379144"
CCM_LINKEDIN_ORG_URN = LINKEDIN_ORGANIZATION_URN or "urn:li:organization:109059206"


def get_org_urn(post: Post = None) -> str:
    if post is not None:
        site = getattr(post, "site", getattr(post, "site_id", "ccm"))
        if str(site).lower() == "opal":
            return OPAL_LINKEDIN_ORG_URN
    return CCM_LINKEDIN_ORG_URN


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "X-Restli-Protocol-Version": "2.0.0",
    }


def _upload_image(path, org_urn: str = CCM_LINKEDIN_ORG_URN) -> str:
    register = requests.post(
        f"{API}/assets?action=registerUpload",
        headers=_headers(),
        json={
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": org_urn,
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
    org_urn = get_org_urn(post)
    require("linkedin",
            LINKEDIN_ACCESS_TOKEN=LINKEDIN_ACCESS_TOKEN,
            LINKEDIN_ORGANIZATION_URN=org_urn)
    validate_post_integrity(post, "linkedin")

    path = image_local_path(post)
    if not path:
        raise PublishError("linkedin: Local image file missing — image is strictly mandatory.", retryable=False)

    asset = _upload_image(path, org_urn=org_urn)
    media = [{"status": "READY", "media": asset}]

    body = {
        "author": org_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": full_text(post)},
                "shareMediaCategory": "IMAGE",
                "media": media,
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    r = requests.post(f"{API}/ugcPosts", headers=_headers(), json=body, timeout=60)
    if r.status_code != 201:
        raise PublishError(f"linkedin post failed: {r.status_code} {r.text[:300]}")
    return r.headers.get("x-restli-id") or r.json().get("id", "")
