"""Each website's own images for social posts.

Until now every site's posts were illustrated from one folder of Corporate Cars
Melbourne fleet photographs, with a per-site starting offset so the sequences at
least differed. A second client's posts therefore carried another business's
cars.

A site's gallery is its own: images are uploaded through the dashboard, stored
per site, and handed out one after another so the same photograph does not open
every post. A site with no gallery of its own can draw on its WordPress media
library instead, when the blog agent is connected.
"""

import json
import mimetypes
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import LOGS_DIR
from core.logging.logger import get_agent_logger

logger = get_agent_logger("site-image-gallery")

GALLERY_ROOT = LOGS_DIR / "site_images"
INDEX_NAME = "gallery.json"

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_BYTES = 8 * 1024 * 1024  # 8 MB — Instagram rejects much larger anyway
MAX_IMAGES_PER_SITE = 200


def _safe_site(site_id: str) -> str:
    """A site id that cannot escape the gallery root."""
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", (site_id or "").strip().lower()).strip("-")
    if not cleaned:
        raise ValueError("A website id is required.")
    return cleaned


def site_dir(site_id: str) -> Path:
    return GALLERY_ROOT / _safe_site(site_id)


def _index_path(site_id: str) -> Path:
    return site_dir(site_id) / INDEX_NAME


def _read_index(site_id: str) -> Dict[str, Any]:
    path = _index_path(site_id)
    if not path.exists():
        return {"images": [], "cursor": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("images", [])
        data.setdefault("cursor", 0)
        return data
    except Exception as e:
        logger.warning("Gallery index unreadable for %s: %s", site_id, e)
        return {"images": [], "cursor": 0}


def _write_index(site_id: str, data: Dict[str, Any]) -> None:
    path = _index_path(site_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def list_images(site_id: str) -> List[Dict[str, Any]]:
    """This site's images, oldest first, with the order they will be used."""
    data = _read_index(site_id)
    out = []
    for position, img in enumerate(data["images"]):
        out.append({**img, "position": position})
    return out


def add_image(site_id: str, filename: str, content: bytes, content_type: str,
              caption: str = "") -> Dict[str, Any]:
    """Store one image for this site. Raises ValueError with a reason."""
    site = _safe_site(site_id)
    extension = ALLOWED_TYPES.get((content_type or "").split(";")[0].strip().lower())
    if not extension:
        guessed = mimetypes.guess_type(filename or "")[0]
        extension = ALLOWED_TYPES.get(guessed or "")
    if not extension:
        raise ValueError("Only JPG, PNG and WebP images can be uploaded.")
    if not content:
        raise ValueError("That file is empty.")
    if len(content) > MAX_BYTES:
        raise ValueError(
            f"That image is {len(content) / 1024 / 1024:.1f} MB. "
            f"The limit is {MAX_BYTES // 1024 // 1024} MB."
        )

    data = _read_index(site)
    if len(data["images"]) >= MAX_IMAGES_PER_SITE:
        raise ValueError(
            f"This gallery already holds {MAX_IMAGES_PER_SITE} images. "
            f"Remove some before adding more."
        )

    # Instagram fetches the picture itself and cannot present a session, so
    # these files are also reachable at an unguessable public path. The name
    # carries the entropy: 16 bytes, not the 4 a local-only name would need.
    # The image is about to be published publicly in any case.
    stored_name = f"{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(16)}{extension}"
    target = site_dir(site) / stored_name
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as f:
        f.write(content)

    record = {
        "id": stored_name,
        "original_name": (filename or stored_name)[:120],
        "caption": (caption or "").strip()[:200],
        "bytes": len(content),
        "uploaded_at": datetime.now().isoformat(timespec="seconds"),
        "times_used": 0,
        "last_used_at": None,
    }
    data["images"].append(record)
    _write_index(site, data)
    logger.info("Image added to %s gallery: %s (%d bytes)", site, stored_name, len(content))
    return record


def delete_image(site_id: str, image_id: str) -> bool:
    site = _safe_site(site_id)
    data = _read_index(site)
    remaining = [i for i in data["images"] if i.get("id") != image_id]
    if len(remaining) == len(data["images"]):
        return False

    # Only ever unlink inside this site's own folder.
    target = site_dir(site) / Path(image_id).name
    try:
        if target.exists() and target.parent == site_dir(site):
            target.unlink()
    except OSError as e:
        logger.warning("Could not remove %s: %s", target, e)

    data["images"] = remaining
    if data["cursor"] >= len(remaining):
        data["cursor"] = 0
    _write_index(site, data)
    return True


def image_path(site_id: str, image_id: str) -> Optional[Path]:
    """The file for one image, or None. Never resolves outside the site."""
    candidate = site_dir(site_id) / Path(image_id).name
    if candidate.exists() and candidate.parent == site_dir(site_id):
        return candidate
    return None


def next_images(site_id: str, count: int) -> List[Dict[str, Any]]:
    """The next `count` images, continuing where the last campaign stopped.

    One after another rather than at random, so a gallery of six images is seen
    six times before any of them repeats. The cursor is stored, so a campaign
    created tomorrow carries on rather than starting from the first image again.
    """
    site = _safe_site(site_id)
    data = _read_index(site)
    images = data["images"]
    if not images:
        return []

    cursor = data.get("cursor", 0) % len(images)
    picked = []
    now = datetime.now().isoformat(timespec="seconds")
    for step in range(count):
        index = (cursor + step) % len(images)
        image = images[index]
        image["times_used"] = image.get("times_used", 0) + 1
        image["last_used_at"] = now
        picked.append(dict(image))

    data["cursor"] = (cursor + count) % len(images)
    _write_index(site, data)
    return picked


def gallery_summary(site_id: str) -> Dict[str, Any]:
    data = _read_index(site_id)
    images = data["images"]
    return {
        "count": len(images),
        "next_up": images[data.get("cursor", 0) % len(images)]["id"] if images else None,
        "total_bytes": sum(i.get("bytes", 0) for i in images),
    }
