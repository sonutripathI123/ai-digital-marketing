"""
Scheduler Abstraction Layer for the Command Center.
Provides cron/interval job registration, schedule monitoring,
and an autonomous background execution daemon thread.
"""

import time
import logging
import threading
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("scheduler_manager")


class ScheduleJob(BaseModel):
    job_id: str
    agent_id: str
    cron_expression: str
    action: str
    enabled: bool = True
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None


def match_cron_field(field_str: str, val: int) -> bool:
    """Evaluates whether integer val matches a cron field token."""
    field_str = field_str.strip()
    if field_str == "*":
        return True

    # Step: */5
    if field_str.startswith("*/"):
        try:
            step = int(field_str[2:])
            return (val % step) == 0
        except ValueError:
            return False

    # List: 1,3,5
    if "," in field_str:
        tokens = field_str.split(",")
        return any(match_cron_field(t, val) for t in tokens)

    # Range: 1-6
    if "-" in field_str:
        parts = field_str.split("-")
        if len(parts) == 2:
            try:
                start, end = int(parts[0]), int(parts[1])
                return start <= val <= end
            except ValueError:
                return False

    # Exact number
    try:
        return int(field_str) == val
    except ValueError:
        return False


def is_cron_due(cron_expr: str, dt_utc: datetime) -> bool:
    """
    Evaluates 5-part cron expression against UTC datetime.
    Format: [minute] [hour] [day_of_month] [month] [day_of_week]
    day_of_week: 0=Sunday, 1=Monday, ..., 6=Saturday, 7=Sunday
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False

    c_min, c_hr, c_dom, c_mon, c_dow = parts

    # ISO weekday: 1=Mon ... 7=Sun (converted to 0=Sun ... 6=Sat)
    iso_w = dt_utc.isoweekday()
    cron_dow = 0 if iso_w == 7 else iso_w

    if not match_cron_field(c_min, dt_utc.minute):
        return False
    if not match_cron_field(c_hr, dt_utc.hour):
        return False
    if not match_cron_field(c_dom, dt_utc.day):
        return False
    if not match_cron_field(c_mon, dt_utc.month):
        return False
    # Check both 0 and 7 for Sunday if needed
    if not (match_cron_field(c_dow, cron_dow) or (cron_dow == 0 and match_cron_field(c_dow, 7))):
        return False

    return True


class SchedulerManager:
    def __init__(self):
        self._jobs: Dict[str, ScheduleJob] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_minute_checked: Optional[str] = None

    def register_schedule(
        self,
        job_id: str,
        agent_id: str,
        cron_expression: str,
        action: str,
        callback: Optional[Callable] = None,
    ) -> ScheduleJob:
        job = ScheduleJob(
            job_id=job_id,
            agent_id=agent_id,
            cron_expression=cron_expression,
            action=action,
            next_run_at=datetime.now(timezone.utc).isoformat(),
        )
        self._jobs[job_id] = job
        if callback:
            self._callbacks[job_id] = callback
        return job

    def list_schedules(self, agent_id: Optional[str] = None) -> List[ScheduleJob]:
        jobs = list(self._jobs.values())
        if agent_id:
            jobs = [j for j in jobs if j.agent_id == agent_id]
        return jobs

    def trigger_now(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.enabled:
            job.last_run_at = datetime.now(timezone.utc).isoformat()
            callback = self._callbacks.get(job_id)
            if callback:
                try:
                    logger.info(f"Triggering scheduled job '{job_id}' for agent '{job.agent_id}'")
                    callback()
                except Exception as e:
                    logger.exception(f"Error executing scheduled job '{job_id}': {e}")
            return True
        return False

    def _tick_loop(self):
        """Background daemon ticking once every minute to evaluate and fire cron jobs."""
        logger.info("Autonomous Background Scheduler daemon started.")
        while self._running:
            try:
                now_utc = datetime.now(timezone.utc)
                current_min_key = now_utc.strftime("%Y-%m-%d %H:%M")

                if current_min_key != self._last_minute_checked:
                    self._last_minute_checked = current_min_key

                    for job_id, job in list(self._jobs.items()):
                        if job.enabled and is_cron_due(job.cron_expression, now_utc):
                            logger.info(f"Cron match for job '{job_id}' ({job.cron_expression}) at {current_min_key} UTC")
                            self.trigger_now(job_id)

            except Exception as e:
                logger.exception(f"Unexpected error in scheduler loop: {e}")

            time.sleep(15)  # Sleep 15s between resolution checks

    def start_background_runner(self):
        """Starts the background ticking daemon if not already running."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._tick_loop, daemon=True, name="SchedulerDaemon")
            self._thread.start()

    def stop_background_runner(self):
        self._running = False
