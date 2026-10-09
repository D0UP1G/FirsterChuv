class SubmissionError(ValueError):
    """A submission request or transition violates the queue contract."""


class IntegrationUnavailable(RuntimeError):
    """A required production authorization/result adapter is not configured."""


class IdempotencyConflict(SubmissionError):
    """An idempotency key was reused with a different request body."""


class QueueFull(SubmissionError):
    """The bounded queue cannot accept another pending submission."""


class SubmissionNotFound(LookupError):
    """The submission is unknown or not visible to the requesting author."""


class StaleLease(RuntimeError):
    """A worker attempted to use a lease that is no longer current."""
