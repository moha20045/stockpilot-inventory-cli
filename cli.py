"""Command-line interface for TaskForge.

Run ``taskforge --help`` after installing the package (``pip install -e .``)
to see all available commands, or run this module directly with
``python -m taskforge.cli``.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import sys
from pathlib import Path

from .exceptions import TaskForgeError
from .models import Priority, RecurringTask, Task
from .storage import TaskStore

DEFAULT_DB = Path.home() / ".taskforge" / "tasks.json"


def setup_logging(verbose: bool) -> None:
    """Configure logging once, at CLI startup. Everything else in the
    package just calls logging.getLogger(__name__) and logs normally."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def parse_date(value: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'; expected YYYY-MM-DD"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="taskforge",
        description="TaskForge - a hierarchical CLI task manager",
    )
    parser.add_argument(
        "--db", default=str(DEFAULT_DB), help="Path to the JSON task database"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Add a new task")
    p_add.add_argument("title", help="Task title")
    p_add.add_argument("-d", "--description", default="")
    p_add.add_argument(
        "-p", "--priority", choices=[p.name for p in Priority], default="MEDIUM"
    )
    p_add.add_argument("--due", type=parse_date, default=None, metavar="YYYY-MM-DD")
    p_add.add_argument(
        "--parent", type=int, default=None, help="Parent task id (creates a subtask)"
    )
    p_add.add_argument(
        "--recur",
        type=int,
        default=None,
        metavar="DAYS",
        help="Make this a recurring task that reschedules every DAYS days",
    )

    p_list = sub.add_parser("list", help="List all tasks as a tree")
    p_list.add_argument(
        "--sort", action="store_true", help="Sort top-level tasks by priority/due date"
    )

    p_show = sub.add_parser("show", help="Show one task and its subtasks")
    p_show.add_argument("id", type=int)

    p_complete = sub.add_parser("complete", help="Mark a task complete")
    p_complete.add_argument("id", type=int)
    p_complete.add_argument(
        "--no-cascade", action="store_true", help="Don't complete subtasks too"
    )

    p_remove = sub.add_parser("remove", help="Remove a task")
    p_remove.add_argument("id", type=int)

    sub.add_parser("stats", help="Show summary statistics")

    return parser


def print_tree(task: Task, indent: int = 0) -> None:
    print("  " * indent + str(task))
    for st in task.subtasks:
        print_tree(st, indent + 1)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    logger = logging.getLogger("taskforge.cli")

    try:
        store = TaskStore(args.db)

        if args.command == "add":
            if args.recur:
                task: Task = RecurringTask(
                    title=args.title,
                    description=args.description,
                    priority=Priority[args.priority],
                    due_date=args.due,
                    recurrence_days=args.recur,
                )
            else:
                task = Task(
                    title=args.title,
                    description=args.description,
                    priority=Priority[args.priority],
                    due_date=args.due,
                )

            if args.parent is not None:
                parent = store.find(args.parent)
                parent.add_subtask(task)
                store.save()
            else:
                store.add(task)
            print(f"Added: {task}")

        elif args.command == "list":
            tasks = store.all_tasks()
            if not tasks:
                print('No tasks yet. Add one with: taskforge add "My first task"')
            else:
                if args.sort:
                    tasks = sorted(tasks)
                for t in tasks:
                    print_tree(t)

        elif args.command == "show":
            task = store.find(args.id)
            print_tree(task)
            print(f"Progress: {task.progress}%  Overdue: {task.is_overdue}")

        elif args.command == "complete":
            task = store.find(args.id)
            task.mark_complete(cascade=not args.no_cascade)
            store.save()
            print(f"Completed: {task}")

        elif args.command == "remove":
            store.remove(args.id)
            print(f"Removed task {args.id}")

        elif args.command == "stats":
            s = store.stats()
            print(f"Total tasks: {s['total']}")
            print(f"Completed:   {s['completed']}")
            print(f"Overdue:     {s['overdue']}")

    except TaskForgeError as exc:
        logger.error(str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
