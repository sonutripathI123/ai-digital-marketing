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


def init_db():
    Base.metadata.create_all(engine)
    print(f"Database initialized at {DATABASE_URL}")


if __name__ == "__main__":
    init_db()
