# Project Brief — TaskForge

**Authors:** Mohamed Salem Maidan, Daniel Zayas
**Course:** CIT 411 – Python Programming, Atlantis University
**Instructor:** Professor Parnell Dujor
**Date:** June 23, 2026

## What does it do?
TaskForge is a command-line task manager for people whose to-do lists aren't
flat. A task can have subtasks (which can have their own subtasks), so a
project like "Launch website" can be broken into "Design," "Build," and
"Deploy," each with their own checklist underneath. TaskForge also supports
**recurring** tasks (e.g., "Water plants every 7 days") that automatically
roll their due date forward instead of disappearing when completed.

## Who uses it?
Individuals who manage personal or small-project to-do lists from the
terminal and want structure (nesting, priority, due dates, recurrence)
without the overhead of a web app or a database server. It's aimed at
developers and power users comfortable with a CLI.

## Smallest version that proves the concept
A user can, from the terminal:
1. Add a top-level task (`taskforge add "Launch website"`).
2. Add subtasks under it (`taskforge add "Design" --parent 1`).
3. List the tree and see a computed completion percentage.
4. Mark a task complete and see progress roll up to its parent.
5. Close the terminal and reopen it — the data is still there (JSON file
   persistence), proving the app is genuinely useful across sessions.

Everything else (recurrence, stats, sorting, overdue detection) builds on
top of that minimal loop.

## Why this domain fits the assignment
- **Recursion arises naturally**: computing a task's progress from its
  subtasks, serializing/deserializing a task tree to/from JSON, and finding
  a task by ID in a tree are all recursive by nature — not recursion bolted
  on for a grade.
- **Inheritance arises naturally**: a `RecurringTask` *is a* `Task` with one
  behavioral difference (completing it reschedules it instead of closing
  it), which is a textbook case for overriding a method rather than
  branching on a flag everywhere.
- **Dunder methods have real jobs**: `__iter__` walks the whole subtree,
  `__len__` counts descendants, `__lt__` orders tasks for a sorted list
  view, `__contains__` checks membership by ID — each maps to something a
  user actually does with the CLI.
