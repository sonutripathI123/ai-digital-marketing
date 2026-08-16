"""
Central Task Queue & State Tracking.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from core.models.task import AgentTask, TaskStatus
from config.settings import LOGS_DIR

TASKS_STORE_FILE = LOGS_DIR / "tasks_history.json"


class TaskQueue:
    def __init__(self):
        self._tasks: Dict[str, AgentTask] = {}
        self._load_from_disk()

    def _save_to_disk(self) -> None:
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            data = [t.model_dump() for t in self._tasks.values()]
            with open(TASKS_STORE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            pass

    def _load_from_disk(self) -> None:
        if TASKS_STORE_FILE.exists():
            try:
                with open(TASKS_STORE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        task = AgentTask.model_validate(item)
                        self._tasks[task.task_id] = task
            except Exception:
                pass

    def add(self, task: AgentTask) -> None:
        self._tasks[task.task_id] = task
        self._save_to_disk()

    def get(self, task_id: str) -> Optional[AgentTask]:
        return self._tasks.get(task_id)

    def list_all(self, status: Optional[TaskStatus] = None, agent_id: Optional[str] = None) -> List[AgentTask]:
        result = list(self._tasks.values())
        if status:
            result = [t for t in result if t.status == status]
        if agent_id:
            result = [t for t in result if t.agent_id == agent_id]
        return result

    def update_status(self, task_id: str, status: TaskStatus, output_data: Optional[dict] = None, error_message: Optional[str] = None) -> Optional[AgentTask]:
        task = self.get(task_id)
        if task:
            task.status = status
            if output_data is not None:
                task.output_data = output_data
            if error_message is not None:
                task.error_message = error_message
            self._save_to_disk()
        return task

