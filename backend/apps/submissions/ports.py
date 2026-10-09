"""Local DI ports matching the P3/A2 contract; no runtime fallback adapters."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SubmissionPermit:
    run_id: UUID
    elapsed_ms: int
    scoring_version: str


@dataclass(frozen=True, slots=True)
class AttemptReceipt:
    submission_id: UUID
    user_id: UUID
    match_id: UUID
    run_id: UUID
    problem_id: UUID
    received_at: datetime
    elapsed_ms: int
    scoring_version: str


@dataclass(frozen=True, slots=True)
class ResultReceipt:
    submission_id: UUID
    user_id: UUID
    match_id: UUID
    run_id: UUID
    problem_id: UUID
    received_at: datetime
    elapsed_ms: int
    scoring_version: str
    verdict: str


class CompetitionGatewayV1(Protocol):
    def authorize_submission(
        self,
        actor_id: UUID,
        match_id: UUID,
        run_id: UUID,
        problem_id: UUID,
        received_at: datetime,
    ) -> SubmissionPermit: ...

    def register_accepted(self, receipt: AttemptReceipt) -> None: ...


class EventWriter(Protocol):
    def append(self, scope: str, event_type: str, public_payload: Mapping[str, object]) -> object: ...


class ResultSink(Protocol):
    def apply_result(self, receipt: ResultReceipt) -> bool: ...


class LanguageRegistry(Protocol):
    def is_supported(self, language_id: str) -> bool: ...
