"""
Phase 3: publishing daemon. Checks the DB every N minutes (default 5,
PUBLISH_CHECK_INTERVAL_MINUTES in .env) and publishes anything due.

Run:      python run_scheduler.py            # honours DRY_RUN from .env
Live:     python run_scheduler.py --live
One-off:  python run_scheduler.py --once
"""

import argparse
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from app_logging import setup_logging
from models import SessionLocal, init_db
from publishing import publish_due

log = logging.getLogger("run_scheduler")


def check_and_publish(dry_run: bool) -> None:
    session = SessionLocal()
    try:
        counts = publish_due(session, dry_run=dry_run)
        if any(counts.values()):
            log.info("Publish cycle: %s", counts)
    except Exception:
        log.exception("Publish cycle crashed")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Corporate Cars Melbourne publish daemon")
    parser.add_argument("--live", action="store_true",
                        help="actually publish (overrides DRY_RUN=true in .env)")
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    args = parser.parse_args()

    setup_logging()
    init_db()
    dry_run = config.DRY_RUN and not args.live
    log.info("Daemon starting — interval %d min, mode: %s",
             config.PUBLISH_CHECK_INTERVAL_MINUTES, "DRY RUN" if dry_run else "LIVE")

    if args.once:
        check_and_publish(dry_run)
        return

    scheduler = BlockingScheduler(timezone=str(config.TIMEZONE))
    scheduler.add_job(check_and_publish, "interval",
                      minutes=config.PUBLISH_CHECK_INTERVAL_MINUTES,
                      args=[dry_run], next_run_time=None)
    check_and_publish(dry_run)  # immediate first pass
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Daemon stopped")


if __name__ == "__main__":
    main()
