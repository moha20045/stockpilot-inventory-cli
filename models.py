"""Domain model for TaskForge.

Design summary
--------------
- ``Task`` is a ``@dataclass`` holding a single task and, recursively, its
  subtasks. Most of the "interesting" behavior (progress calculation,
  serialization, search) is naturally recursive because the data itself
  is a tree.
- ``RecurringTask`` inherits from ``Task`` and overrides ``mark_complete``
  so that "completing" the task reschedules it instead of closing it.
- ``@dataclass(eq=False, repr=False)`` is used deliberately: we want our
  own hand-written ``__eq__``/``__repr__`` (see below) instead of the
  dataclass-generated field-by-field versions, so we tell the decorator
  not to generate them.
"""

from __future__ import annotations

import dataclasses
import datetime
import itertools
import logging
from enum import Enum
from typing import Iterator, List, Optional

from .exceptions import InvalidTaskDataError

logger = logging.getLogger(__name__)

# Monotonically increasing id generator shared by every Task ever created
# in this process. Using itertools.count keeps id assignment O(1) and
# collision-free without needing a database.
_id_counter = itertools.count(1)


class Priority(Enum):
    """Task priority, ordered from lowest to highest urgency."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    def __str__(self) -> str:  # nicer display than "Priority.HIGH"
        return self.name.title()


@dataclasses.dataclass(eq=False, repr=False)
class Task:
    """A single task, which may itself contain nested subtasks."""

    title: str
    description: str = ""
    priority: Priority = Priority.MEDIUM
    due_date: Optional[datetime.date] = None
    completed: bool = False
    id: int = dataclasses.field(default_factory=lambda: next(_id_counter))
    created_at: datetime.datetime = dataclasses.field(
        default_factory=datetime.datetime.now
    )
    subtasks: List["Task"] = dataclasses.field(default_factory=list)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise InvalidTaskDataError("Task title cannot be empty")
        logger.debug("Created task %r", self)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def progress(self) -> float:
        """Completion percentage (0-100), computed recursively.

        A leaf task is either 0% or 100% done. A task with subtasks is the
        average progress of its children -- so a parent automatically
        reflects how much of its own subtree is finished.
        """
        if not self.subtasks:
            return 100.0 if self.completed else 0.0
        return round(sum(st.progress for st in self.subtasks) / len(self.subtasks), 1)

    @property
    def is_overdue(self) -> bool:
        """True if this task has a due date in the past and isn't done."""
        return bool(
            self.due_date
            and not self.completed
            and self.due_date < datetime.date.today()
        )

    # ------------------------------------------------------------------
    # Business behavior (instance methods)
    # ------------------------------------------------------------------
    def add_subtask(self, subtask: "Task") -> None:
        """Attach a subtask to this task."""
        self.subtasks.append(subtask)
        logger.info("Added subtask '%s' under '%s'", subtask.title, self.title)

    def mark_complete(self, cascade: bool = True) -> None:
        """Mark this task done.

        If ``cascade`` is True (default), all descendant subtasks are
        marked done too -- finishing a project finishes its checklist.
        """
        if cascade:
            for st in self.subtasks:
                st.mark_complete(cascade=True)
        self.completed = True
        logger.info("Completed task '%s' (id=%s)", self.title, self.id)

    # ------------------------------------------------------------------
    # Recursive tree operations
    # ------------------------------------------------------------------
    def find(self, task_id: int) -> Optional["Task"]:
        """Depth-first search this subtree for a task with the given id."""
        if self.id == task_id:
            return self
        for st in self.subtasks:
            found = st.find(task_id)
            if found is not None:
                return found
        return None

    def count_all(self) -> int:
        """Count this task plus every descendant subtask, recursively."""
        return 1 + sum(st.count_all() for st in self.subtasks)

    # ------------------------------------------------------------------
    # Serialization (alternate constructor + recursive (de)serializer)
    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Alternate constructor: rebuild a task (and its subtree) from a
        plain dict, e.g. one loaded from JSON.

        Rebuilding the ``subtasks`` list is a recursive call to this same
        classmethod, since each subtask is itself a full task tree.
        """
        subtasks = [cls.from_dict(sd) for sd in data.get("subtasks", [])]
        due = data.get("due_date")
        return cls(
            title=data["title"],
            description=data.get("description", ""),
            priority=Priority[data.get("priority", "MEDIUM")],
            due_date=datetime.date.fromisoformat(due) if due else None,
            completed=data.get("completed", False),
            id=data.get("id", next(_id_counter)),
            subtasks=subtasks,
        )

    def to_dict(self) -> dict:
        """Recursively serialize this task and its subtasks to a
        JSON-safe dict."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.name,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed": self.completed,
            "subtasks": [st.to_dict() for st in self.subtasks],
        }

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------
    def __iter__(self) -> Iterator["Task"]:
        """Depth-first iteration over this task and every descendant.

        Lets callers write ``for t in some_task: ...`` to walk a whole
        subtree without manually recursing.
        """
        yield self
        for st in self.subtasks:
            yield from st

    def __len__(self) -> int:
        """Number of tasks in this subtree (self + all descendants)."""
        return self.count_all()

    def __contains__(self, task_id: int) -> bool:
        """Support ``task_id in some_task``."""
        return self.find(task_id) is not None

    def __lt__(self, other: "Task") -> bool:
        """Order by priority (highest first), then by due date (soonest
        first). Lets ``sorted(tasks)`` produce a sensible worklist."""
        if not isinstance(other, Task):
            return NotImplemented
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value
        self_due = self.due_date or datetime.date.max
        other_due = other.due_date or datetime.date.max
        return self_due < other_due

    def __eq__(self, other: object) -> bool:
        """Two tasks are equal if they have the same id."""
        if not isinstance(other, Task):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __str__(self) -> str:
        mark = "x" if self.completed else " "
        return f"[{mark}] #{self.id} {self.title} ({self.priority}) - {self.progress}%"

    def __repr__(self) -> str:
        return (
            f"Task(id={self.id!r}, title={self.title!r}, "
            f"priority={self.priority!r}, completed={self.completed!r}, "
            f"subtasks={len(self.subtasks)})"
        )


@dataclasses.dataclass(eq=False, repr=False)
class RecurringTask(Task):
    """A task that reschedules itself instead of staying "done".

    Inherits every field and dunder method from ``Task``; the only
    behavioral change is ``mark_complete``, which rolls the due date
    forward by ``recurrence_days`` and reopens the task.
    """

    recurrence_days: int = 7
    last_completed: Optional[datetime.date] = None

    def mark_complete(self, cascade: bool = True) -> None:
        """Complete subtasks as usual, then roll this task's due date
        forward instead of leaving it marked done."""
        super().mark_complete(cascade=cascade)
        self.last_completed = datetime.date.today()
        if self.due_date:
            self.due_date = self.due_date + datetime.timedelta(
                days=self.recurrence_days
            )
        self.completed = False
        logger.info(
            "Recurring task '%s' rolled forward to %s", self.title, self.due_date
        )

    def __str__(self) -> str:
        return super().__str__() + f" [recurs every {self.recurrence_days}d]"
