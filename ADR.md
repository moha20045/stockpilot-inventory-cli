# Architecture Decision Log — TaskForge

Format: each entry is a decision, the context that led to it, and the
alternatives that were considered but not chosen.

---

## ADR-001: Domain — hierarchical task manager

**Decision:** Build a CLI task manager where tasks can nest arbitrarily
(subtasks of subtasks), rather than a flat to-do list.

**Context:** The assignment requires recursion to be used naturally and
inheritance to model something real. A flat to-do list has neither a
natural tree to recurse over nor an obvious "is-a" relationship between
task types.

**Alternatives considered:**
- *Flat to-do list with tags* — simpler, but recursion would have to be
  bolted on artificially (e.g., a recursive tag-matching function nobody
  would actually write this way).
- *Personal library/media tracker* — inheritance (Book/Movie extends
  MediaItem) is natural, but there's no natural recursive structure
  without inventing nested "collections," which felt more forced than
  a task tree.

**Consequence:** Every recursive function in the codebase (`progress`,
`find`, `count_all`, `to_dict`/`from_dict`, `_find_parent`) exists because
the data is a tree, not because the assignment required a recursive
function somewhere.

---

## ADR-002: `src/` layout over flat package layout

**Decision:** Put the package under `src/taskforge/` rather than a
top-level `taskforge/` next to `tests/`.

**Context:** A flat layout lets `import taskforge` succeed just because
the current working directory is on `sys.path`, which can hide packaging
bugs (missing `__init__.py`, wrong `packages` config) that only surface
after a real `pip install`.

**Alternatives considered:** Flat layout — simpler for a very small
script, but doesn't match how most real-world, portfolio-quality Python
packages are structured, and was explicitly requested by the assignment.

**Consequence:** `pip install -e .` is the only way to get `taskforge`
importable/runnable during development, which forced early verification
that packaging metadata (`pyproject.toml`, `[tool.setuptools.packages.find]`)
was correct rather than discovering it at the end.

---

## ADR-003: JSON over CSV for persistence

**Decision:** Persist tasks as a single JSON file, not CSV.

**Context:** Tasks form a tree (a task owns a list of subtask objects,
each with their own fields). CSV is a natural fit for flat, rectangular
data; representing a variable-depth tree in CSV would require an extra
parent-id column and a reconstruction step, adding complexity without
benefit.

**Alternatives considered:** CSV with a `parent_id` column — would work,
but `to_dict`/`from_dict` (nested dicts) map onto JSON far more directly
than onto rows, and JSON keeps the recursive serialization logic simple
and symmetric (serialize a subtree, deserialize a subtree).

**Consequence:** The whole task forest is loaded and saved as one file
per operation, which is simple and fine at personal-task-list scale, but
wouldn't scale to thousands of tasks without moving to a real database or
partial writes.

---

## ADR-004: `RecurringTask` overrides `mark_complete`, not a `recurring: bool` flag

**Decision:** Model recurrence as a subclass (`RecurringTask(Task)`) that
overrides `mark_complete()`, instead of adding a `recurring` boolean field
to `Task` and branching on it inside `mark_complete()`.

**Context:** The assignment requires at least one inheritance relationship
used meaningfully, not just declared. A boolean flag would satisfy "the
feature works" but not "inheritance does something."

**Alternatives considered:** `is_recurring: bool` field on `Task` with an
`if self.is_recurring:` branch in `mark_complete()` — works, but pushes
recurrence-specific fields (`recurrence_days`, `last_completed`) onto
every `Task` even when unused, and scatters recurrence logic through a
method that's otherwise about plain completion.

**Consequence:** Adding a second task variant later (e.g., a task with an
approval step) means adding another `Task` subclass, not another
conditional branch in `mark_complete()`.

---

## ADR-005: `@dataclass(eq=False, repr=False)` to keep hand-written dunders

**Decision:** Disable the dataclass-generated `__eq__` and `__repr__` on
`Task`, and write both by hand (identity by `id`, and a compact repr).

**Context:** The default dataclass `__eq__` compares every field,
including `subtasks` — so two tasks with the same id but different
subtask lists (e.g., one loaded from disk before a subtask was added,
one after) would compare unequal, which doesn't match "these are the same
task." Two tasks should be equal if they're the same task, identified by
`id`.

**Alternatives considered:** Leave the dataclass defaults — simpler, but
`__eq__` semantics would be wrong for a mutable tree structure like this,
and the assignment specifically calls out `__eq__` as something to
implement deliberately.

**Consequence:** `__hash__` had to be written by hand too (dataclasses set
`__hash__ = None` when a custom `__eq__` is combined with `eq=True`;
setting `eq=False` sidesteps that and lets us define both ourselves,
consistently, off of `id`).

---

## ADR-006: Logging goes to stdout at INFO by default, DEBUG with `-v`

**Decision:** Configure `logging.basicConfig` once, at CLI startup, with
a `StreamHandler` to stdout, INFO by default and DEBUG behind `-v`.

**Context:** This is a single-user CLI tool run interactively, not a
long-running service — a separate log file would just be one more thing
for a user to find and clean up, and stdout logs are visible immediately
in the same terminal session where the command was run.

**Alternatives considered:** Log to a file under `~/.taskforge/` — more
"production-like," but adds a second artifact to explain in the README
for a tool whose whole point is fast terminal feedback. Kept as a
plausible follow-up if TaskForge ever grew a daemon/reminder mode.

**Consequence:** Every command's output includes log lines above the
actual result, which is intentional for a class demo (it shows the
logging is real) but is somewhat noisier than a typical CLI tool; a
`--quiet` flag would be a reasonable follow-up.
