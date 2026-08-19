"""
Corporate Cars Melbourne — Social Media Agent
Image library: sync local /images folder into the DB and pick the
least-recently-used image matching a keyword/topic so photos rotate.

Library layout:  images/<category>/<filename>
  e.g. images/mercedes-sclass/mercedes-sclass-01.jpg
Category = folder name. Tags = hyphen-separated words in the filename
(numbers stripped), e.g. "mercedes-sclass-airport-01.jpg" -> mercedes, sclass, airport.
"""

import logging
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from config import IMAGE_LIBRARY_PATH
from models import Image, Keyword

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Keyword-text token -> image category/tag tokens it should match.
# Current categories: sedan (S-Class), people-mover (V-Class),
# minibus (Sprinter), suv (Audi Q7), wedding-cars. Extend as you add folders.
TOKEN_SYNONYMS = {
    "airport": {"sedan", "suv"},
    "transfer": {"sedan", "suv"},
    "corporate": {"sedan", "suv"},
    "business": {"sedan", "suv"},
    "executive": {"sedan", "suv"},
    "chauffeur": {"sedan", "suv", "people", "mover"},
    "luxury": {"sedan", "suv"},
    "wedding": {"wedding", "cars", "bridal"},
    "bridal": {"wedding", "cars"},
    "event": {"sedan", "people", "mover"},
    "events": {"sedan", "people", "mover"},
    "conference": {"people", "mover", "minibus"},
    "group": {"people", "mover", "minibus", "van"},
    "family": {"suv", "people", "mover"},
    "van": {"people", "mover", "minibus"},
    "winery": {"people", "mover", "minibus"},
    "tour": {"people", "mover", "minibus"},
    "tours": {"people", "mover", "minibus"},
    "cruise": {"sedan", "people", "mover"},
    "hotel": {"sedan", "suv"},
}


def _tokens_from_filename(path: Path) -> list[str]:
    stem = re.sub(r"\d+", "", path.stem)
    return [t for t in re.split(r"[-_\s]+", stem.lower()) if len(t) > 1]


def sync_images(session: Session) -> tuple[int, int]:
    """Scan IMAGE_LIBRARY_PATH and upsert Image rows. Returns (added, removed)."""
    found = {}
    if not IMAGE_LIBRARY_PATH.exists():
        log.warning("Image library path does not exist: %s", IMAGE_LIBRARY_PATH)
        return (0, 0)

    for f in sorted(IMAGE_LIBRARY_PATH.rglob("*")):
        if f.suffix.lower() not in IMAGE_EXTENSIONS or not f.is_file():
            continue
        rel = f.relative_to(IMAGE_LIBRARY_PATH)
        category = rel.parts[0] if len(rel.parts) > 1 else "uncategorised"
        found[f.name] = {
            "filepath": str(f.resolve()),
            "category": category,
            "tags": ",".join(_tokens_from_filename(f)),
        }

    added = 0
    existing = {img.filename: img for img in session.query(Image).all()}
    for filename, meta in found.items():
        if filename in existing:
            img = existing[filename]
            img.filepath, img.category, img.tags = meta["filepath"], meta["category"], meta["tags"]
        else:
            session.add(Image(filename=filename, **meta))
            added += 1

    removed = 0
    for filename, img in existing.items():
        if filename not in found:
            session.delete(img)
            removed += 1

    session.commit()
    return (added, removed)


def _match_tokens(keyword: Keyword | None, topic: str) -> tuple[set[str], set[str]]:
    """Returns (direct tokens from the keyword text, synonym-expanded tokens)."""
    text = topic.lower()
    if keyword is not None:
        text += " " + keyword.keyword.lower() + " " + (keyword.category or "").lower()
    raw = set(re.split(r"[^a-z0-9]+", text)) - {""}
    # naive singular/plural bridging so "car" matches "cars" etc.
    raw |= {t + "s" for t in raw} | {t[:-1] for t in raw if t.endswith("s")}
    expanded = set()
    for token in raw:
        expanded |= TOKEN_SYNONYMS.get(token, set())
    return raw, expanded - raw


def select_image(session: Session, topic: str, keyword: Keyword | None = None) -> Image | None:
    """
    Pick the least-recently-used image whose category/tags overlap the topic.
    Specialty categories (e.g. 'wedding-cars') are STRICTLY gated: they are ONLY
    selected if the topic/keyword explicitly contains wedding/bridal keywords.
    For corporate, airport, executive, or general posts, wedding images are strictly
    excluded and executive fleet images (sedan, suv, people-mover, minibus) are selected.
    Marks the chosen image as used (rotation guarantee).
    """
    images = session.query(Image).all()
    if not images:
        return None

    direct, synonyms = _match_tokens(keyword, topic)

    is_wedding_topic = bool({"wedding", "weddings", "bridal", "bride", "groom", "marriage"} & direct)

    if is_wedding_topic:
        # Only select from wedding cars
        candidate_images = [
            img for img in images 
            if (img.category or "").lower() in ("wedding-cars", "wedding", "bridal")
        ]
        if not candidate_images:
            candidate_images = images
    else:
        # Strictly exclude wedding cars from corporate, airport, chauffeur, and general posts
        candidate_images = [
            img for img in images 
            if (img.category or "").lower() not in ("wedding-cars", "wedding", "bridal")
        ]
        if not candidate_images:
            candidate_images = images

    def overlap(img: Image) -> int:
        img_tokens = set((img.category or "").lower().split("-"))
        img_tokens |= set((img.tags or "").lower().split(","))
        specific_direct = direct - {"car", "cars"}
        return 2 * len(img_tokens & specific_direct) + len(img_tokens & synonyms)

    def lru_key(img: Image):
        # Strict Fair Sequential Round-Robin:
        # Lowest use_count first, then oldest last_used_at (or never used), then stable ID
        return (img.use_count or 0, img.last_used_at or datetime.min, img.id)

    # Sort strictly by lowest use count and oldest usage to cycle through all images 1-by-1
    candidate_images.sort(key=lru_key)
    chosen = candidate_images[0]

    chosen.last_used_at = datetime.utcnow()
    chosen.use_count = (chosen.use_count or 0) + 1
    session.commit()
    return chosen
