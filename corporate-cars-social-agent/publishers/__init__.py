"""Platform → publisher dispatch."""

from models import Platform, Post
from publishers import facebook, instagram, linkedin, pinterest, threads, x
from publishers.base import PublishError  # re-export for callers

_PUBLISHERS = {
    Platform.instagram: instagram.publish,
    Platform.facebook: facebook.publish,
    Platform.linkedin: linkedin.publish,
    Platform.x: x.publish,
    Platform.threads: threads.publish,
    Platform.pinterest: pinterest.publish,
}


def publish_post(post: Post) -> str:
    """Publish to the post's platform. Returns the platform post id."""
    return _PUBLISHERS[post.platform](post)
