"""
Corporate Cars Melbourne — Social Media Agent CLI.

  python cli.py init
  python cli.py add-keywords "airport transfer, corporate travel" --category "airport transfer"
  python cli.py sync-images
  python cli.py generate --keywords "airport transfer" --platform instagram
  python cli.py generate --keywords "airport transfer, wedding cars" --platform all --no-ai
  python cli.py schedule --weeks 2
  python cli.py publish-due            (dry run by default)
  python cli.py publish-due --live
  python cli.py status
  python cli.py list-posts --status draft
"""

import logging

import typer

import config
from app_logging import setup_logging
from models import (Keyword, Platform, Post, PostStatus, Schedule,
                    SessionLocal, init_db)

app = typer.Typer(help="Corporate Cars Melbourne social media agent", no_args_is_help=True)
log = logging.getLogger("cli")


def _session():
    setup_logging()
    return SessionLocal()


@app.command()
def init():
    """Create the database and sync the image library."""
    setup_logging()
    init_db()
    from image_selector import sync_images
    session = SessionLocal()
    added, removed = sync_images(session)
    typer.echo(f"Image library synced: {added} added, {removed} removed.")
    session.close()


@app.command("add-keywords")
def add_keywords(
    keywords: str = typer.Argument(..., help="comma-separated keywords"),
    category: str = typer.Option(None, help="category for all of these keywords"),
):
    """Add keywords to the pool."""
    from content_generator import get_or_create_keyword
    session = _session()
    for kw in [k.strip() for k in keywords.split(",") if k.strip()]:
        get_or_create_keyword(session, kw, category)
        typer.echo(f"  + {kw}" + (f"  [{category}]" if category else ""))
    session.close()


@app.command("sync-images")
def sync_images_cmd():
    """Rescan the /images folder into the database."""
    from image_selector import sync_images
    session = _session()
    added, removed = sync_images(session)
    typer.echo(f"Synced: {added} added, {removed} removed.")
    session.close()


@app.command()
def generate(
    keywords: str = typer.Option(..., "--keywords", help="comma-separated keywords"),
    platform: str = typer.Option("all", "--platform",
                                 help="instagram|facebook|linkedin|x|threads|pinterest|all"),
    category: str = typer.Option(None, help="category applied to new keywords"),
    no_ai: bool = typer.Option(False, "--no-ai",
                               help="use offline template content (no Claude API call)"),
):
    """Generate draft posts (status=draft) for keyword × platform."""
    from content_generator import GenerationError, generate_post, get_or_create_keyword

    platforms = list(Platform) if platform == "all" else [Platform(platform)]
    session = _session()
    kws = [get_or_create_keyword(session, k, category)
           for k in keywords.split(",") if k.strip()]

    for kw in kws:
        for p in platforms:
            try:
                post = generate_post(session, kw, p, use_ai=not no_ai)
            except GenerationError as e:
                typer.secho(f"  [FAILED] {p.value} / {kw.keyword}: {e}", fg=typer.colors.RED)
                continue
            img = post.image.filename if post.image else "(no image)"
            typer.secho(f"\n-- draft #{post.id}  {p.value}  \"{kw.keyword}\"  image: {img}",
                        fg=typer.colors.GREEN, bold=True)
            typer.echo(post.caption)
            if post.hashtags:
                typer.echo(post.hashtags)
    session.close()


@app.command()
def schedule(weeks: int = typer.Option(1, "--weeks", help="number of weeks to queue")):
    """Queue drafts: 2 posts per platform per week, at staggered Melbourne-time slots."""
    from scheduler import schedule_posts
    session = _session()
    created = schedule_posts(session, weeks=weeks)
    typer.echo(f"\nScheduled {len(created)} post(s).")
    session.close()


@app.command("publish-due")
def publish_due_cmd(
    live: bool = typer.Option(False, "--live", help="actually publish (default is dry run)"),
):
    """Publish everything whose scheduled time has passed."""
    from publishing import publish_due
    session = _session()
    dry_run = config.DRY_RUN and not live
    if dry_run:
        typer.secho("DRY RUN — nothing will be posted (use --live to publish)",
                    fg=typer.colors.YELLOW)
    counts = publish_due(session, dry_run=dry_run)
    typer.echo(f"Result: {counts}")
    session.close()


@app.command()
def status():
    """Counts of posts by platform and status, plus upcoming schedule."""
    from sqlalchemy import func
    session = _session()

    typer.secho("\nPosts by platform / status:", bold=True)
    rows = (session.query(Post.platform, Post.status, func.count(Post.id))
            .group_by(Post.platform, Post.status).all())
    if not rows:
        typer.echo("  (none yet)")
    for platform, st, n in rows:
        typer.echo(f"  {platform.value:<10} {st.value:<10} {n}")

    typer.secho("\nNext scheduled posts (Melbourne time):", bold=True)
    upcoming = (session.query(Schedule).join(Post)
                .filter(Schedule.published == False)  # noqa: E712
                .order_by(Schedule.publish_at.asc()).limit(10).all())
    if not upcoming:
        typer.echo("  (nothing queued)")
    from datetime import timezone
    for s in upcoming:
        local = s.publish_at.replace(tzinfo=timezone.utc).astimezone(config.TIMEZONE)
        typer.echo(f"  #{s.post_id:<4} {s.post.platform.value:<10} "
                   f"{local.strftime('%a %d %b %Y %H:%M')}  \"{s.post.keyword.keyword if s.post.keyword else ''}\"")
    session.close()


@app.command("list-posts")
def list_posts(
    status_filter: str = typer.Option(None, "--status", help="draft|scheduled|published|failed"),
):
    """List posts, optionally filtered by status."""
    session = _session()
    q = session.query(Post).order_by(Post.id.asc())
    if status_filter:
        q = q.filter(Post.status == PostStatus(status_filter))
    posts = q.all()
    if not posts:
        typer.echo("No posts found.")
    for p in posts:
        img = p.image.filename if p.image else "-"
        err = f"  ERROR: {p.error_message[:80]}" if p.error_message else ""
        typer.echo(f"#{p.id:<4} {p.platform.value:<10} {p.status.value:<10} "
                   f"\"{p.keyword.keyword if p.keyword else '?'}\"  img:{img}{err}")
        typer.echo(f"      {p.caption[:110].replace(chr(10), ' ')}")
    session.close()


if __name__ == "__main__":
    app()
