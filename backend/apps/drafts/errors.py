class DraftError(ValueError):
    """A draft request or state transition is invalid."""


class DraftNotFound(LookupError):
    """A draft is unknown or not visible to the requesting participant."""


class DraftRevisionConflict(RuntimeError):
    """The draft changed since the client read its expected revision."""

    def __init__(self, current):
        self.current = current
        super().__init__("draft revision changed")


class DraftStorageBusy(RuntimeError):
    """SQLite stayed busy after the bounded draft-save retry budget."""


class WorkspaceDenied(LookupError):
    """The workspace port denies access to this match/run/problem."""


class WorkspaceUnavailable(RuntimeError):
    """The production workspace access port is not configured."""
