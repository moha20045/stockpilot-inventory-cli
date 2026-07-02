"""Custom exceptions for TaskForge.

Keeping a small exception hierarchy lets the CLI layer catch one base
class (TaskForgeError) and print a clean message, while still letting
callers distinguish failure modes programmatically if they need to.
"""


class TaskForgeError(Exception):
    """Base class for all TaskForge-specific errors."""


class TaskNotFoundError(TaskForgeError):
    """Raised when a task id does not exist in the store."""


class InvalidTaskDataError(TaskForgeError):
    """Raised when task data is malformed (bad JSON, empty title, etc.)."""
