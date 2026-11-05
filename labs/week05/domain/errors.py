"""Business-rule failures. They carry no HTTP codes: the API layer decides how to show them."""


class DomainError(Exception):
    """Base class for every rule the domain enforces."""


class TaskNotFound(DomainError):
    """No such task, or it belongs to someone else (callers can't tell the difference)."""

    def __init__(self, task_id: str) -> None:
        super().__init__(f"Task '{task_id}' does not exist.")
        self.task_id = task_id


class TaskAlreadyFinished(DomainError):
    """The task is in a terminal state, so it can't be changed any more."""

    def __init__(self, task_id: str, state: str) -> None:
        super().__init__(f"Task '{task_id}' is already {state}.")
        self.task_id = task_id
        self.state = state


class IdempotencyKeyReused(DomainError):
    """The same idempotency key was sent with a different request."""

    def __init__(self) -> None:
        super().__init__(
            "This idempotency key was already used with a different request."
        )
