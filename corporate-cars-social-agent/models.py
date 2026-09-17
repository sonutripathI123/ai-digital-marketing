"""
Corporate Cars Melbourne — Social Media Agent
SQLAlchemy models / database schema.

Run once to create the DB:
    from models import init_db
    init_db()
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime,
    Boolean, ForeignKey, Enum
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import enum

from config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


class Platform(str, enum.Enum):
    instagram = "instagram"
    facebook = "facebook"
    linkedin = "linkedin"
    x = "x"
    threads = "threads"
    pinterest = "pinterest"


class PostStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    published = "published"
    failed = "failed"


# ---------------------------------------------------------------------
# Keywords — input pool used to generate content
# ---------------------------------------------------------------------
class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True)
    keyword = Column(String(255), nullable=False, unique=True)
    category = Column(String(100))          # e.g. "airport transfer", "wedding", "corporate"
    priority = Column(Integer, default=1)   # higher = used more often
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------
# Images — local image library metadata
# ---------------------------------------------------------------------
class Image(Base):
    __tablename__ = "images"
    public_url = Column(String, nullable=True)
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False, unique=True)
    filepath = Column(String(500), nullable=False)
    category = Column(String(100))          # e.g. "mercedes-sclass", "sprinter-van"
    tags = Column(String(500))              # comma-separated freeform tags
    last_used_at = Column(DateTime, nullable=True)
    use_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------
# Posts — generated content, one row per platform per post
# ---------------------------------------------------------------------
class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    # Which website published this. Rows written before this column existed are
    # all Corporate Cars Melbourne's -- this was a single-brand database -- and
    # are backfilled to "ccm" by ensure_site_column() in db.py.
    site_id = Column(String(64), nullable=True, index=True)
    platform = Column(Enum(Platform), nullable=False)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=True)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=True)

    caption = Column(Text, nullable=False)
    hashtags = Column(String(500))
    cta = Column(String(255))
    status = Column(Enum(PostStatus), default=PostStatus.draft)

    platform_post_id = Column(String(255), nullable=True)   # set after publish
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    keyword = relationship("Keyword")
    image = relationship("Image")
    schedule_entry = relationship("Schedule", back_populates="post", uselist=False)


# ---------------------------------------------------------------------
# Schedule — when each post should go out
# ---------------------------------------------------------------------
class Schedule(Base):
    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, unique=True)
    publish_at = Column(DateTime, nullable=False)   # stored in UTC
    published = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime, nullable=True)

    post = relationship("Post", back_populates="schedule_entry")


def ensure_schema() -> None:
    """Add columns this code needs that an older database file lacks.

    create_all() creates missing tables; it does not alter existing ones. When
    site_id was added to Post, the code shipped expecting the column while the
    database on disk still lacked it, and every query raised
    "no such column: posts.site_id" until somebody altered the table by hand.

    Running this on import means the database repairs itself however it got
    there -- a restore, a copy from another machine, a checkout. It is
    idempotent and must never stop the process from starting.
    """
    from sqlalchemy import text

    try:
        with engine.begin() as conn:
            columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(posts)")}
            if not columns:
                return  # table not created yet; create_all will handle it
            if "site_id" not in columns:
                conn.exec_driver_sql("ALTER TABLE posts ADD COLUMN site_id VARCHAR(64)")
                # Rows written before the column existed are all the primary
                # site's: this was a single-brand database.
                conn.exec_driver_sql("UPDATE posts SET site_id = 'ccm' WHERE site_id IS NULL")
                conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_posts_site_id ON posts (site_id)")
    except Exception as e:  # pragma: no cover - never block startup
        import logging

        logging.getLogger("social-agent-models").warning(
            "Could not bring the posts table up to date: %s", e)


def init_db():
    Base.metadata.create_all(engine)
    ensure_schema()
    print(f"Database initialized at {DATABASE_URL}")


# The schema check runs on import, not only from init_db(), because the agent
# is reached through several entry points and only some of them call init_db().
ensure_schema()


if __name__ == "__main__":
    init_db()
