"""Persistence layer for TaskForge.

``TaskStore`` owns the list of top-level tasks and handles reading/writing
them to a JSON file on disk. It is deliberately a plain (non-dataclass)
class: its job is behavior (I/O, search, stats), not just holding fields.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Union

from .exceptions import InvalidTaskDataError, TaskNotFoundError
from .models import RecurringTask, Task

logger = logging.getLogger(__name__)


class TaskStore:
    """Loads, holds, and saves a forest of top-level Tasks as JSON."""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.tasks: List[Task] = []
        if self.path.exists():
            self.load()
        else:
            logger.info("No existing database at %s; starting fresh", self.path)

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------
    def load(self) -> None:
        """Read the JSON file and rebuild the task tree from it."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise InvalidTaskDataError(f"Corrupt task file at {self.path}: {exc}") from exc
        except OSError as exc:
            raise InvalidTaskDataError(f"Could not read {self.path}: {exc}") from exc

        self.tasks = []
        for item in raw:
            cls = RecurringTask if "recurrence_days" in item else Task
            self.tasks.append(cls.from_dict(item))
        logger.info("Loaded %d top-level task(s) from %s", len(self.tasks), self.path)

    def save(self) -> None:
        """Write the current task tree to the JSON file (pretty-printed)."""
        data = []
        for t in self.tasks:
            d = t.to_dict()
            if isinstance(t, RecurringTask):
                d["recurrence_days"] = t.recurrence_days
            data.append(d)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as exc:
            raise InvalidTaskDataError(f"Could not write {self.path}: {exc}") from exc
        logger.info("Saved %d top-level task(s) to %s", len(self.tasks), self.path)

    # ------------------------------------------------------------------
    # CRUD-ish operations
    # ------------------------------------------------------------------
    def add(self, task: Task) -> None:
        self.tasks.append(task)
        self.save()

    def find(self, task_id: int) -> Task:
        """Find a task anywhere in the forest by id, or raise."""
        for t in self.tasks:
            found = t.find(task_id)
            if found is not None:
                return found
        raise TaskNotFoundError(f"No task with id {task_id}")

    def remove(self, task_id: int) -> None:
        """Remove a task (top-level or nested) by id."""
        for t in self.tasks:
            if t.id == task_id:
                self.tasks.remove(t)
                self.save()
                return
        for t in self.tasks:
            parent = self._find_parent(t, task_id)
            if parent is not None:
                parent.subtasks = [st for st in parent.subtasks if st.id != task_id]
                self.save()
                return
        raise TaskNotFoundError(f"No task with id {task_id}")

    def _find_parent(self, task: Task, target_id: int):
        """Recursively locate the parent of the task with ``target_id``."""
        for st in task.subtasks:
            if st.id == target_id:
                return task
            found = self._find_parent(st, target_id)
            if found is not None:
                return found
        return None

    def all_tasks(self) -> List[Task]:
        return list(self.tasks)

    def stats(self) -> dict:
        """Aggregate counts across the whole forest, using Task.__iter__."""
        total = completed = overdue = 0
        for top in self.tasks:
            for t in top:  # uses Task.__iter__
                total += 1
                completed += int(t.completed)
                overdue += int(t.is_overdue)
        return {"total": total, "completed": completed, "overdue": overdue}
