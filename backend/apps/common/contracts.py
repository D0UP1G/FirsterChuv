"""Typed v1 boundaries shared by the platform, competition, and judge domains.

These contracts describe calls and immutable payloads only. They do not
implement access decisions, match rules, event storage, or code execution.
The module intentionally imports no optional domain app.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

JudgeVerdict = Literal["OK", "WA", "TL", "ML", "RE", "CE"]
WorkspacePurpose = Literal["metadata", "statement", "draft", "history"]
WorkspaceAction = Literal[
    "read_metadata",
    "read_statement",
    "read_draft",
    "write_draft",
    "submit",
    "read_history",
]


@dataclass(frozen=True, slots=True)
class SubmissionPermit:
    run_id: UUID
    elapsed_ms: int
    scoring_version: str


@dataclass(frozen=True, slots=True)
class JudgeResult:
    verdict: JudgeVerdict
    compile_diagnostics: str | None = None
    metrics: Mapping[str, int | float] | None = None
    internal_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AttemptReceipt:
    """Server-authored identity and timing for one accepted submission."""

    submission_id: UUID
    run_id: UUID
    user_id: UUID
    problem_id: UUID
    received_at: datetime
    elapsed_ms: int
    scoring_version: str


@dataclass(frozen=True, slots=True)
class ResultReceipt:
    """Final judge result paired with the immutable accepted-attempt identity."""

    submission_id: UUID
    run_id: UUID
    user_id: UUID
    problem_id: UUID
    received_at: datetime
    elapsed_ms: int
    scoring_version: str
    verdict: JudgeVerdict


@dataclass(frozen=True, slots=True)
class InfrastructureFailureReceipt:
    """Server allowlisted failure code only; never diagnostics or a verdict."""

    submission_id: UUID
    run_id: UUID
    reason_code: str
    retryable: bool


class InfrastructureFailureSink(Protocol):
    """Idempotent internal handoff for infrastructure failure outcomes."""

    def record_infrastructure_failure(self, receipt: InfrastructureFailureReceipt) -> None: ...


@dataclass(frozen=True, slots=True)
class ResultApplication:
    """Whether an idempotent result was applied to the active run."""

    applied: bool


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    """Access-filtered workspace projection returned by CompetitionGatewayV1."""

    actor_id: UUID
    run_id: UUID
    problem_id: UUID
    allowed_actions: frozenset[WorkspaceAction]
    condition_available: bool


class ProblemExample(Protocol):
    @property
    def input(self) -> str: ...

    @property
    def output(self) -> str: ...


class LanguageDescriptor(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def template(self) -> str: ...


class PublicAsset(Protocol):
    @property
    def asset_id(self) -> str: ...

    @property
    def media_type(self) -> str: ...

    @property
    def contents(self) -> bytes: ...


class PrivateTestCase(Protocol):
    @property
    def input(self) -> bytes: ...

    @property
    def expected_output(self) -> bytes | None: ...


class PrivateArtifact(Protocol):
    @property
    def role(self) -> str: ...

    @property
    def source_path(self) -> str: ...

    @property
    def language_id(self) -> str | None: ...

    @property
    def contents(self) -> bytes: ...


class ProblemSummaryV1(Protocol):
    """Structural view of immutable public metadata from ProblemCatalogV1."""

    @property
    def problem_id(self) -> UUID: ...

    @property
    def version(self) -> str: ...

    @property
    def label(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def statement_markdown(self) -> str: ...

    @property
    def asset_ids(self) -> tuple[str, ...]: ...

    @property
    def examples(self) -> tuple[ProblemExample, ...]: ...

    @property
    def time_limit_ms(self) -> int: ...

    @property
    def memory_limit_bytes(self) -> int: ...

    @property
    def languages(self) -> tuple[LanguageDescriptor, ...]: ...


class ProblemBundleV1(Protocol):
    """Structural view of normalized public data and trusted private judge data."""

    @property
    def problem_id(self) -> UUID: ...

    @property
    def version(self) -> str: ...

    @property
    def checksum(self) -> str: ...

    @property
    def label(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def statement_markdown(self) -> str: ...

    @property
    def assets(self) -> tuple[PublicAsset, ...]: ...

    @property
    def examples(self) -> tuple[ProblemExample, ...]: ...

    @property
    def time_limit_ms(self) -> int: ...

    @property
    def memory_limit_bytes(self) -> int: ...

    @property
    def languages(self) -> tuple[LanguageDescriptor, ...]: ...

    @property
    def tests(self) -> tuple[PrivateTestCase, ...]: ...

    @property
    def private_artifacts(self) -> tuple[PrivateArtifact, ...]: ...


@dataclass(frozen=True, slots=True)
class PublicAccessContext:
    """Safe public scope returned after public or unlisted-token authorization."""

    tournament_id: UUID
    public: bool
    read_only: bool = True


@dataclass(frozen=True, slots=True)
class TrustedJudgeJob:
    """Trusted worker input; execution policy is selected by the provider."""

    submission_id: UUID
    source: str
    language_id: str
    problem_id: UUID
    problem_version: str
    problem_checksum: str


@dataclass(frozen=True, slots=True)
class RunProblemSnapshot:
    """Immutable problem identity assigned to one run; checksum is SHA-256."""

    run_id: UUID
    problem_id: UUID
    problem_version: str
    problem_checksum: str


class RunProblemSnapshotProvider(Protocol):
    """Resolve a problem version/checksum from the requested run assignment."""

    def resolve(self, run_id: UUID, problem_id: UUID) -> RunProblemSnapshot: ...


class MatchPort(Protocol):
    """Legacy local boundary retained until the v1 gateway is connected."""

    def assert_can_submit(self, user, match_id: UUID, problem_id: UUID) -> SubmissionPermit:
        """Authorize a submit and return the current run/time snapshot."""


class CompetitionGatewayV1(Protocol):
    """Competition admission, ledger, result, and workspace authorization."""

    def authorize_submission(
        self,
        actor_id: UUID,
        match_id: UUID,
        run_id: UUID,
        problem_id: UUID,
        received_at: datetime,
    ) -> SubmissionPermit:
        """Validate participant, membership, current run, task, and deadline."""

    def register_accepted(self, receipt: AttemptReceipt) -> None:
        """Persist an immutable pending receipt in the submission transaction."""

    def apply_result(self, receipt: ResultReceipt) -> ResultApplication:
        """Apply a final result idempotently; stale runs must not change current score."""

    def authorize_workspace(
        self,
        actor_id: UUID,
        match_id: UUID,
        run_id: UUID,
        problem_id: UUID,
        purpose: WorkspacePurpose,
    ) -> WorkspaceContext:
        """Return only the actions and statement visibility granted to this actor."""


class ProblemCatalogV1(Protocol):
    """Ready problem metadata and private normalized bundle provider."""

    def describe_ready(
        self, problem_ids: Sequence[UUID]
    ) -> tuple[ProblemSummaryV1, ...]:
        """Return immutable public snapshots or fail for unknown/not-ready IDs."""

    def load_bundle(self, problem_id: UUID, version: str) -> ProblemBundleV1:
        """Load trusted private tests/checker data for one immutable version."""


class PublicAccessV1(Protocol):
    """Public and unlisted read-only access check, separate from invites."""

    def assert_can_view(
        self, tournament_id: UUID, share_token: str | None = None
    ) -> PublicAccessContext:
        """Authorize a public view without granting participant/admin actions."""


class JudgeProvider(Protocol):
    def execute(self, job: TrustedJudgeJob) -> JudgeResult:
        """Run one trusted judge job and return a bounded result."""


class LanguageRegistry(Protocol):
    """Server-owned allowlist of languages supported by the judge deployment."""

    def is_supported(self, language_id: str) -> bool:
        """Return whether the exact stable language ID is configured."""


class JudgeInfrastructureError(RuntimeError):
    """Raised for sandbox/worker failure; it is not a contestant verdict."""


class EventWriter(Protocol):
    def append(
        self, scope: str, event_type: str, public_payload: Mapping[str, object]
    ) -> int:
        """Persist an allowlisted public event with the related state change."""
