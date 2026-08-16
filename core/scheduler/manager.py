"""
Scheduler Abstraction Layer for the Command Center.
Provides cron/interval job registration and schedule monitoring.
"""

from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class ScheduleJob(BaseModel):
    job_id: str
    agent_id: str
    cron_expression: str
    action: str
    enabled: bool = True
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None


class SchedulerManager:
    def __init__(self):
        self._jobs: Dict[str, ScheduleJob] = {}
        self._callbacks: Dict[str, Callable] = {}

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
                callback()
            return True
        return False
