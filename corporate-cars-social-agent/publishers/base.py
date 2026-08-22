"""Shared publisher helpers."""

import logging
from pathlib import Path

from config import IMAGE_BASE_URL, IMAGE_LIBRARY_PATH
from models import Post

log = logging.getLogger(__name__)


class PublishError(Exception):
    """Raised when a platform publish fails. retryable=False stops retries."""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class MissingCredentials(PublishError):
    def __init__(self, platform: str, names: list[str]):
        super().__init__(
            f"{platform}: missing credentials in .env: {', '.join(names)}", retryable=False
        )


def require(platform: str, **creds: str) -> None:
    missing = [name for name, value in creds.items() if not value]
    if missing:
        raise MissingCredentials(platform, missing)


def full_text(post: Post) -> str:
    """Caption + hashtags as posted."""
    if post.hashtags:
        return f"{post.caption}\n\n{post.hashtags}"
    return post.caption


def image_local_path(post: Post) -> Path | None:
    if post.image is None:
        return None
    p = Path(post.image.filepath)
    if p.exists():
        return p
    if hasattr(post.image, "filename") and post.image.filename:
        fallback = Path(IMAGE_LIBRARY_PATH) / post.image.filename
        if fallback.exists():
            return fallback
        matches = list(Path(IMAGE_LIBRARY_PATH).glob(f"**/{post.image.filename}"))
        if matches:
            return matches[0]
    return None


def image_public_url(post: Post) -> str | None:
    """
    Map a local library file to its public URL.
    Required by Instagram, Threads, Facebook and Pinterest — Meta/Pinterest
    fetch the image from a URL rather than accepting an upload.
    """
    if post.image is None:
        return None
    if getattr(post.image, "public_url", None) and str(post.image.public_url).startswith("http"):
        return post.image.public_url

    import os
    import urllib.parse

    rel_path = None
    if post.image.filepath:
        try:
            rel_path = Path(post.image.filepath).resolve().relative_to(IMAGE_LIBRARY_PATH.resolve())
        except (ValueError, RuntimeError):
            pass

    if not rel_path and getattr(post.image, "category", None) and post.image.filename:
        rel_path = Path(post.image.category) / post.image.filename
    elif not rel_path and post.image.filename:
        matches = list(Path(IMAGE_LIBRARY_PATH).glob(f"**/{post.image.filename}"))
        if matches:
            try:
                rel_path = matches[0].relative_to(IMAGE_LIBRARY_PATH)
            except ValueError:
                rel_path = Path(post.image.filename)
        else:
            rel_path = Path(post.image.filename)

    rel_str = str(rel_path).replace("\\", "/")
    parts = [urllib.parse.quote(part) for part in rel_str.split("/")]
    encoded_path = "/".join(parts)

    cloud_base = os.getenv("RENDER_EXTERNAL_URL", "https://ai-digital-marketing-gm68.onrender.com").rstrip("/")
    return f"{cloud_base}/social-images/{encoded_path}"


def validate_post_integrity(post: Post, platform: str) -> None:
    """
    STRICT DUAL CONTENT + IMAGE MANDATORY VALIDATION:
    Enforces that a post MUST have BOTH substantive caption text AND a verified image.
    Never publish image-only or text-only posts across any platform.
    """
    # 1. Text caption validation
    caption = (post.caption or "").strip()
    if not caption or len(caption) < 25:
        raise PublishError(
            f"{platform}: Post rejected by Content Guard — substantive caption is missing (found {len(caption)} chars, min 25 required). Both image AND content are strictly mandatory.",
            retryable=False
        )

    # 2. Image attachment validation
    if post.image is None and not post.image_id:
        raise PublishError(
            f"{platform}: Post rejected by Image Guard — no image attached. Both image AND content are strictly mandatory.",
            retryable=False
        )

    # 3. Image file / URL validation
    local_p = image_local_path(post)
    pub_url = image_public_url(post)

    if not local_p and not pub_url:
        raise PublishError(
            f"{platform}: Post rejected by Image Guard — image file or public CDN URL could not be resolved.",
            retryable=False
        )
