"""Transactional generation and reset of persisted single-elimination brackets."""

from collections.abc import Sequence
from uuid import UUID

from django.db import models, transaction

from backend.apps.competition.domain.bracket import (
    BracketInputError,
    BracketPlan,
    SeededParticipant,
    generate_single_elimination,
)
from backend.apps.competition.models import Match, MatchRun, MatchSlot
from backend.apps.tournaments.models import Tournament, TournamentParticipant
from backend.apps.tournaments.services import (
    EDITABLE_TOURNAMENT_STATUSES,
    freeze_roster,
    retry_sqlite_locked_write,
)


class BracketPersistenceError(RuntimeError):
    """Raised when stored bracket state violates its generation invariants."""


class BracketResetConflict(BracketPersistenceError):
    """Raised when a bracket has progressed beyond the explicit reset boundary."""


class BracketLifecycleConflict(BracketPersistenceError):
    """Raised when bracket mutations target a non-editable tournament."""

    status_code = 409
    code = "tournament_not_editable"


def _claim_editable_tournament(tournament_id: UUID | str) -> Tournament:
    """Acquire the tournament write lock before reading its lifecycle or bracket.

    SQLite does not provide effective row locks through ``select_for_update``.
    This conditional no-op UPDATE is deliberately the first data statement in
    each mutator's transaction, serializing it with archive/start transitions.
    """
    changed = Tournament.objects.filter(
        pk=tournament_id,
        status__in=EDITABLE_TOURNAMENT_STATUSES,
    ).update(updated_at=models.F("updated_at"))
    if changed == 0:
        if not Tournament.objects.filter(pk=tournament_id).exists():
            raise Tournament.DoesNotExist("Турнир не найден.")
        raise BracketLifecycleConflict(
            "Сетку можно создавать и изменять только у чернового или запланированного турнира."
        )
    return Tournament.objects.get(pk=tournament_id)


def _ordered_matches(tournament_id: UUID | str) -> list[Match]:
    return list(
        Match.objects.filter(tournament_id=tournament_id)
        .prefetch_related("slots__participant", "slots__upstream_match", "winner")
        .order_by("round_index", "position", "id")
    )


def _build_plan(
    roster: list[TournamentParticipant],
    first_round_pairings: Sequence[Sequence[UUID | str | None]] | None = None,
) -> BracketPlan:
    entrants = [
        SeededParticipant(participant_id=str(entry.pk), seed=rank)
        for rank, entry in enumerate(roster, start=1)
    ]
    normalized_pairings = (
        tuple(
            tuple(
                None if participant_id is None else str(participant_id)
                for participant_id in pair
            )
            for pair in first_round_pairings
        )
        if first_round_pairings is not None
        else None
    )
    return generate_single_elimination(
        entrants,
        first_round_pairings=normalized_pairings,
    )


def _save_plan(
    tournament: Tournament,
    roster: list[TournamentParticipant],
    plan: BracketPlan,
) -> list[Match]:
    """Persist one already validated layout; caller owns the transaction."""
    participant_by_id = {str(entry.pk): entry for entry in roster}

    matches_by_key: dict[str, Match] = {}
    for node in plan.nodes:
        winner = (
            participant_by_id[node.automatic_winner_id]
            if node.automatic_winner_id is not None
            else None
        )
        matches_by_key[node.key] = Match.objects.create(
            tournament=tournament,
            bracket_key=node.key,
            round_index=node.round_index,
            position=node.position,
            kind=node.kind,
            status=Match.Status.BYE if node.kind == "BYE" else Match.Status.WAITING,
            winner=winner,
        )

    for node in plan.nodes:
        match = matches_by_key[node.key]
        for slot_index, planned_slot in enumerate(node.slots):
            participant = (
                participant_by_id[planned_slot.participant_id]
                if planned_slot.participant_id is not None
                else None
            )
            upstream = (
                matches_by_key[planned_slot.source_match_key]
                if planned_slot.source_match_key is not None
                else None
            )
            MatchSlot.objects.create(
                match=match,
                slot_index=slot_index,
                resolution=planned_slot.resolution,
                participant=participant,
                upstream_match=upstream,
            )
            if upstream is not None:
                if upstream.next_match_id is not None:
                    raise BracketPersistenceError(
                        "Один матч не может продвигать участника в несколько слотов."
                    )
                upstream.next_match = match
                upstream.next_slot = slot_index
                upstream.save(update_fields=("next_match", "next_slot", "updated_at"))

    return _ordered_matches(tournament.pk)


@retry_sqlite_locked_write
@transaction.atomic
def generate_bracket(tournament_id: UUID | str) -> list[Match]:
    """Freeze the roster and create the bracket once, atomically.

    Repeated calls return the existing bracket and never duplicate matches.
    A failure after roster freeze rolls back the freeze with all bracket writes.
    """
    tournament = _claim_editable_tournament(tournament_id)

    existing = _ordered_matches(tournament.pk)
    if existing:
        if tournament.roster_frozen_at is None:
            raise BracketPersistenceError(
                "Сетка существует, но состав турнира не заморожен."
            )
        return existing

    roster = freeze_roster(tournament.pk)
    plan = _build_plan(roster)
    _save_plan(tournament, roster, plan)
    return _ordered_matches(tournament.pk)


def _assert_bracket_not_started(tournament_id: UUID) -> None:
    progressed_run = MatchRun.objects.filter(
        match__tournament_id=tournament_id,
    ).filter(
        models.Q(started_at__isnull=False)
        | models.Q(
            status__in=(
                MatchRun.Status.RUNNING,
                MatchRun.Status.PAUSED,
                MatchRun.Status.FINALIZING,
                MatchRun.Status.FINISHED,
                MatchRun.Status.TIED,
                MatchRun.Status.SUPERSEDED,
            )
        )
    ).exists()
    progressed_match = (
        Match.objects.filter(
            tournament_id=tournament_id,
            kind=Match.Kind.PLAYED,
        )
        .exclude(status__in=(Match.Status.WAITING, Match.Status.READY))
        .exists()
    )
    if progressed_run or progressed_match:
        raise BracketResetConflict(
            "Изменить сетку можно только до начала любого матча."
        )


def _clear_unstarted_bracket(tournament_id: UUID) -> None:
    MatchSlot.objects.filter(match__tournament_id=tournament_id).delete()
    Match.objects.filter(tournament_id=tournament_id).update(
        next_match=None,
        next_slot=None,
    )
    Match.objects.filter(tournament_id=tournament_id).delete()


@retry_sqlite_locked_write
@transaction.atomic
def reset_bracket(tournament_id: UUID | str) -> list[Match]:
    """Explicitly rebuild a frozen bracket while no match run has started."""
    tournament = _claim_editable_tournament(tournament_id)
    if not Match.objects.filter(tournament_id=tournament.pk).exists():
        raise BracketPersistenceError("Сетка ещё не создана.")

    _assert_bracket_not_started(tournament.pk)
    roster = freeze_roster(tournament.pk)
    _clear_unstarted_bracket(tournament.pk)
    plan = _build_plan(roster)
    _save_plan(tournament, roster, plan)
    return _ordered_matches(tournament.pk)


@retry_sqlite_locked_write
@transaction.atomic
def set_first_round_pairings(
    tournament_id: UUID | str,
    pairings: Sequence[Sequence[UUID | str | None]],
) -> list[Match]:
    """Replace all first-round pairs as one validated, pre-start operation.

    Pairings are ordered by first-round position and must contain every frozen
    roster participant exactly once. Empty seats may be represented by ``None``.
    The complete bracket is rebuilt so bye winners and downstream slots stay in
    sync with the edited first round.
    """
    tournament = _claim_editable_tournament(tournament_id)
    if not Match.objects.filter(tournament_id=tournament.pk).exists():
        raise BracketPersistenceError("Сетка ещё не создана.")
    if tournament.roster_frozen_at is None:
        raise BracketPersistenceError("Состав не заморожен для редактирования пар.")
    _assert_bracket_not_started(tournament.pk)

    roster = freeze_roster(tournament.pk)
    plan = _build_plan(roster, pairings)
    _clear_unstarted_bracket(tournament.pk)
    _save_plan(tournament, roster, plan)
    return _ordered_matches(tournament.pk)
