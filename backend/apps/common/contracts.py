"""Stable module boundaries shared by the competition and judging domains.

These protocols describe calls; they do not implement match rules, event
storage, or code execution. Those remain owned by agents 2 and 3.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SubmissionPermit:
    run_id: UUID
    elapsed_ms: int
    scoring_version: str


@dataclass(frozen=True, slots=True)
class JudgeResult:
    verdict: str
    compile_diagnostics: str | None = None
    metrics: Mapping[str, int | float] | None = None
    internal_reason: str | None = None


class MatchPort(Protocol):
    def assert_can_submit(self, user, match_id: UUID, problem_id: UUID) -> SubmissionPermit:
        """Authorize a submit and return the current run/time snapshot."""


class JudgeProvider(Protocol):
    def execute(self, job) -> JudgeResult:
        """Run one trusted judge job and return a bounded result."""


class EventWriter(Protocol):
    def append(self, scope: str, event_type: str, public_payload: Mapping[str, object]):
        """Persist an allowlisted public event with the related state change."""
