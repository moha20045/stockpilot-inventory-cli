import datetime

import pytest

from taskforge.exceptions import InvalidTaskDataError
from taskforge.models import Priority, RecurringTask, Task


def test_empty_title_raises():
    with pytest.raises(InvalidTaskDataError):
        Task(title="   ")


def test_progress_leaf_task():
    t = Task(title="Leaf")
    assert t.progress == 0.0
    t.completed = True
    assert t.progress == 100.0


def test_progress_rolls_up_from_subtasks():
    parent = Task(title="Parent")
    a = Task(title="A", completed=True)
    b = Task(title="B", completed=False)
    parent.add_subtask(a)
    parent.add_subtask(b)
    assert parent.progress == 50.0


def test_mark_complete_cascades():
    parent = Task(title="Parent")
    child = Task(title="Child")
    parent.add_subtask(child)
    parent.mark_complete()
    assert parent.completed and child.completed


def test_find_and_contains_recursive():
    root = Task(title="Root")
    mid = Task(title="Mid")
    leaf = Task(title="Leaf")
    mid.add_subtask(leaf)
    root.add_subtask(mid)
    assert root.find(leaf.id) is leaf
    assert leaf.id in root
    assert 99999 not in root


def test_len_and_iter():
    root = Task(title="Root")
    root.add_subtask(Task(title="A"))
    root.add_subtask(Task(title="B"))
    assert len(root) == 3  # root + 2 children
    assert sum(1 for _ in root) == 3


def test_eq_and_hash_by_id():
    a = Task(title="A")
    b = Task.from_dict(a.to_dict())
    assert a == b
    assert hash(a) == hash(b)


def test_lt_sorts_by_priority_then_due_date():
    low = Task(title="Low", priority=Priority.LOW)
    high = Task(title="High", priority=Priority.HIGH)
    assert high < low
    assert sorted([low, high]) == [high, low]


def test_to_dict_from_dict_round_trip_recursive():
    root = Task(title="Root", due_date=datetime.date(2026, 8, 1))
    child = Task(title="Child")
    root.add_subtask(child)
    rebuilt = Task.from_dict(root.to_dict())
    assert rebuilt.title == "Root"
    assert rebuilt.due_date == datetime.date(2026, 8, 1)
    assert len(rebuilt.subtasks) == 1
    assert rebuilt.subtasks[0].title == "Child"


def test_recurring_task_reschedules_instead_of_closing():
    t = RecurringTask(
        title="Water plants",
        due_date=datetime.date(2026, 7, 1),
        recurrence_days=7,
    )
    t.mark_complete()
    assert t.completed is False
    assert t.due_date == datetime.date(2026, 7, 8)
    assert t.last_completed == datetime.date.today()


def test_recurring_task_is_a_task():
    t = RecurringTask(title="X")
    assert isinstance(t, Task)
