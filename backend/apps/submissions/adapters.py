"""Adapters from submissions-local ports to stable common v1 providers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TypeVar
from uuid import UUID

from backend.apps.common.contracts import (
    AttemptReceipt as CommonAttemptReceipt,
    CompetitionGatewayV1 as CommonCompetitionGatewayV1,
    EventWriter as CommonEventWriter,
    LanguageRegistry as CommonLanguageRegistry,
    ResultApplication,
    ResultReceipt as CommonResultReceipt,
    SubmissionPermit as CommonSubmissionPermit,
)

from .errors import IntegrationUnavailable
from .ports import (
    AttemptReceipt,
    EventWriter,
    LanguageRegistry,
    ResultReceipt,
    ResultSink,
    SubmissionPermit,
)

_Port = TypeVar("_Port")


def _require_methods(port: _Port | None, *, name: str, methods: tuple[str, ...]) -> _Port:
    if port is None:
        raise IntegrationUnavailable(f"{name} requires a configured production port")
    missing = tuple(method for method in methods if not callable(getattr(port, method, None)))
    if missing:
        raise TypeError(f"{name} port is missing required methods")
    return port


class CompetitionGatewayAdapter:
    """Map queue receipts to common v1 without leaking local match identity."""

    def __init__(self, gateway: CommonCompetitionGatewayV1 | None) -> None:
        self.gateway = _require_methods(
            gateway,
            name="CompetitionGatewayV1",
            methods=("authorize_submission", "register_accepted"),
        )

    def authorize_submission(
        self,
        actor_id: UUID,
        match_id: UUID,
        run_id: UUID,
        problem_id: UUID,
        received_at: datetime,
    ) -> SubmissionPermit:
        permit = self.gateway.authorize_submission(actor_id, match_id, run_id, problem_id, received_at)
        if not isinstance(permit, CommonSubmissionPermit):
            raise TypeError("CompetitionGatewayV1 returned an invalid submission permit")
        return SubmissionPermit(
            run_id=permit.run_id,
            elapsed_ms=permit.elapsed_ms,
            scoring_version=permit.scoring_version,
        )

    def register_accepted(self, receipt: AttemptReceipt) -> None:
        if not isinstance(receipt, AttemptReceipt):
            raise TypeError("submissions accepted receipt has an invalid type")
        self.gateway.register_accepted(
            CommonAttemptReceipt(
                submission_id=receipt.submission_id,
                run_id=receipt.run_id,
                user_id=receipt.user_id,
                problem_id=receipt.problem_id,
                received_at=receipt.received_at,
                elapsed_ms=receipt.elapsed_ms,
                scoring_version=receipt.scoring_version,
            )
        )


class EventWriterAdapter:
    """Forward only the queue service's already allowlisted event payloads."""

    def __init__(self, writer: CommonEventWriter | None) -> None:
        self.writer = _require_methods(writer, name="EventWriter", methods=("append",))

    def append(self, scope: str, event_type: str, public_payload: Mapping[str, object]) -> object:
        return self.writer.append(scope, event_type, public_payload)


class LanguageRegistryAdapter:
    """Expose the common language allowlist through the local queue port."""

    def __init__(self, registry: CommonLanguageRegistry | None) -> None:
        self.registry = _require_methods(registry, name="LanguageRegistry", methods=("is_supported",))

    def is_supported(self, language_id: str) -> bool:
        return self.registry.is_supported(language_id)


class ResultSinkAdapter:
    """Map queue receipts to common idempotent result application."""

    def __init__(self, gateway: CommonCompetitionGatewayV1 | None) -> None:
        self.gateway = _require_methods(gateway, name="CompetitionGatewayV1", methods=("apply_result",))

    def apply_result(self, receipt: ResultReceipt) -> bool:
        if not isinstance(receipt, ResultReceipt):
            raise TypeError("submissions result receipt has an invalid type")
        application = self.gateway.apply_result(
            CommonResultReceipt(
                submission_id=receipt.submission_id,
                run_id=receipt.run_id,
                user_id=receipt.user_id,
                problem_id=receipt.problem_id,
                received_at=receipt.received_at,
                elapsed_ms=receipt.elapsed_ms,
                scoring_version=receipt.scoring_version,
                verdict=receipt.verdict,
            )
        )
        if not isinstance(application, ResultApplication):
            raise TypeError("CompetitionGatewayV1 returned an invalid result application")
        # False means already applied or superseded; the delivery itself succeeded.
        return application.applied
