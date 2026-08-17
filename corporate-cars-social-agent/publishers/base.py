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
    Map a local library file to its public URL (IMAGE_BASE_URL mirrors /images).
    Required by Instagram, Threads, Facebook and Pinterest — Meta/Pinterest
    fetch the image from a URL rather than accepting an upload.
    """
    if post.image is None or not IMAGE_BASE_URL:
        return None
    if getattr(post.image, "public_url", None):
        return post.image.public_url
    try:
        rel = Path(post.image.filepath).resolve().relative_to(IMAGE_LIBRARY_PATH.resolve())
    except ValueError:
        rel = Path(post.image.filename)
    return f"{IMAGE_BASE_URL}/{post.image.filename}"
