class ProblemBundleError(ValueError):
    """The internal normalized bundle failed validation."""


class ProblemNotReady(LookupError):
    """A requested problem version is unknown or not executable yet."""


class ProblemVersionConflict(ValueError):
    """An immutable problem version already exists with different content."""
