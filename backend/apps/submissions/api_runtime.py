"""Production wiring of the participant-facing submission service in the API process.

The API process only admits and queues sources. It never receives Docker access or a
code-execution adapter; verdicts come from the separate trusted judge worker.
"""

from __future__ import annotations

from collections.abc import Mapping

from backend.apps.competition.gateway import get_competition_gateway
from backend.apps.judge.provider import SUPPORTED_LANGUAGE_IDS
from backend.apps.problems import compilers

from .adapters import CompetitionGatewayAdapter, EventWriterAdapter, LanguageRegistryAdapter
from .services import SubmissionService

# Event types the admission transaction may announce. `submission.accepted` has no public payload
# contract yet (its private fields must never reach the stream), so the writer accepts and drops it
# until the typed public producer exists; the map is refreshed from the public snapshot meanwhile.
_DROPPED_UNTIL_PUBLIC_PRODUCER = frozenset({"submission.accepted"})


class VerifiedLanguageRegistry:
    """A language is accepted only when its compiler was really verified, not by manifest claim."""

    def is_supported(self, language_id: str) -> bool:
        spec = compilers.COMPILERS.get(language_id)
        return bool(spec and spec.verified and language_id in SUPPORTED_LANGUAGE_IDS)


class AdmissionEventWriter:
    def append(self, scope: str, event_type: str, public_payload: Mapping[str, object]) -> None:
        if event_type not in _DROPPED_UNTIL_PUBLIC_PRODUCER:
            raise ValueError("unsupported admission event type")


def build_submission_service() -> SubmissionService:
    return SubmissionService(
        competition=CompetitionGatewayAdapter(get_competition_gateway()),
        event_writer=EventWriterAdapter(AdmissionEventWriter()),
        language_registry=LanguageRegistryAdapter(VerifiedLanguageRegistry()),
    )
