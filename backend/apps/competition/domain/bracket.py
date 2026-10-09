"""Deterministic single-elimination bracket layout.

The module is deliberately independent of Django until the shared tournament
and roster models are available. Callers pass active entrants with unique
manual seeds; this builder sorts and normalizes that order, but does not freeze
or mutate a roster.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SlotResolution = Literal["PLAYER", "BYE", "WAITING"]
NodeKind = Literal["MATCH", "BYE"]


class BracketInputError(ValueError):
    """Raised when entrants cannot form a valid seeded bracket."""


@dataclass(frozen=True, slots=True)
class SeededParticipant:
    participant_id: str
    seed: int


@dataclass(frozen=True, slots=True)
class BracketSlot:
    resolution: SlotResolution
    participant_id: str | None = None
    source_match_key: str | None = None


@dataclass(frozen=True, slots=True)
class BracketNode:
    key: str
    round_index: int
    position: int
    kind: NodeKind
    slots: tuple[BracketSlot, BracketSlot]
    automatic_winner_id: str | None = None


@dataclass(frozen=True, slots=True)
class BracketPlan:
    bracket_size: int
    participant_ids: tuple[str, ...]
    nodes: tuple[BracketNode, ...]


@dataclass(slots=True)
class _DraftNode:
    start: int
    round_index: int
    kind: NodeKind
    left: _DraftNode | SeededParticipant | None
    right: _DraftNode | SeededParticipant | None
    automatic_winner_id: str | None = None
    key: str = ""
    position: int = -1


def _seed_order(bracket_size: int) -> list[int]:
    """Return conventional high-seed pairings for a power-of-two bracket."""
    order = [1, 2]
    while len(order) < bracket_size:
        previous_size = len(order)
        order = [
            seed
            for current_seed in order
            for seed in (current_seed, 2 * previous_size + 1 - current_seed)
        ]
    return order


def _to_slot(source: _DraftNode | SeededParticipant | None) -> BracketSlot:
    if source is None:
        return BracketSlot(resolution="BYE")
    if isinstance(source, SeededParticipant):
        return BracketSlot(resolution="PLAYER", participant_id=source.participant_id)

    if source.kind == "BYE":
        return BracketSlot(
            resolution="PLAYER",
            participant_id=source.automatic_winner_id,
            source_match_key=source.key,
        )

    return BracketSlot(resolution="WAITING", source_match_key=source.key)


def generate_single_elimination(
    participants: list[SeededParticipant] | tuple[SeededParticipant, ...],
    *,
    first_round_pairings: (
        list[tuple[str | None, str | None]]
        | tuple[tuple[str | None, str | None], ...]
        | None
    ) = None,
) -> BracketPlan:
    """Build a stable, seeded bracket with explicit bye states and no fake runs.

    Seeds are ranked in ascending order and normalized to positions 1..N. A
    node of kind ``BYE`` records the walkover in the bracket; it does not
    represent a played match and must not create a ``MatchRun``. Empty
    both-bye subtrees are omitted. Real match nodes reference unresolved
    upstream matches as ``WAITING`` slots and resolved bye winners as
    ``PLAYER`` slots.
    """
    entrants = tuple(participants)
    if len(entrants) < 2:
        raise BracketInputError("at least two participants are required")

    participant_ids = [entrant.participant_id for entrant in entrants]
    if any(
        not isinstance(participant_id, str) or not participant_id.strip()
        for participant_id in participant_ids
    ):
        raise BracketInputError("participant IDs must be non-empty strings")
    if len(set(participant_ids)) != len(participant_ids):
        raise BracketInputError("participant IDs must be unique")
    if any(type(entrant.seed) is not int or entrant.seed < 1 for entrant in entrants):
        raise BracketInputError("seeds must be positive integers")
    if len({entrant.seed for entrant in entrants}) != len(entrants):
        raise BracketInputError("seeds must be unique")

    seeded = tuple(sorted(entrants, key=lambda entrant: entrant.seed))
    bracket_size = 1 << (len(seeded) - 1).bit_length()
    leaves: list[SeededParticipant | None] = [None] * bracket_size
    if first_round_pairings is None:
        for position, seed in enumerate(_seed_order(bracket_size)):
            if seed <= len(seeded):
                leaves[position] = seeded[seed - 1]
    else:
        entrants_by_id = {entrant.participant_id: entrant for entrant in seeded}
        if len(first_round_pairings) != bracket_size // 2:
            raise BracketInputError(
                "manual pairings must provide every first-round position"
            )
        seen_ids: set[str] = set()
        for position, pairing in enumerate(first_round_pairings):
            if not isinstance(pairing, tuple) or len(pairing) != 2:
                raise BracketInputError(
                    "each manual pairing must contain exactly two participant IDs"
                )
            if pairing == (None, None):
                raise BracketInputError("a first-round pairing cannot be empty")
            for offset, participant_id in enumerate(pairing):
                if participant_id is None:
                    continue
                if not isinstance(participant_id, str) or not participant_id.strip():
                    raise BracketInputError(
                        "manual pairing participant IDs must be non-empty strings"
                    )
                if participant_id not in entrants_by_id:
                    raise BracketInputError(
                        "manual pairings may use only active bracket participants"
                    )
                if participant_id in seen_ids:
                    raise BracketInputError(
                        "a participant cannot occupy multiple first-round slots"
                    )
                seen_ids.add(participant_id)
                leaves[position * 2 + offset] = entrants_by_id[participant_id]
        if seen_ids != set(entrants_by_id):
            raise BracketInputError(
                "manual pairings must place every active participant exactly once"
            )

    draft_nodes: list[_DraftNode] = []

    def build(
        start: int, width: int, round_index: int
    ) -> _DraftNode | SeededParticipant | None:
        if width == 2:
            left = leaves[start]
            right = leaves[start + 1]
            if left is None and right is None:
                return None
            if left is None or right is None:
                winner = right if left is None else left
                assert winner is not None
                node = _DraftNode(
                    start=start,
                    round_index=round_index,
                    kind="BYE",
                    left=left,
                    right=right,
                    automatic_winner_id=winner.participant_id,
                )
            else:
                node = _DraftNode(
                    start=start,
                    round_index=round_index,
                    kind="MATCH",
                    left=left,
                    right=right,
                )
            draft_nodes.append(node)
            return node

        half = width // 2
        left = build(start, half, round_index - 1)
        right = build(start + half, half, round_index - 1)
        if left is None:
            return right
        if right is None:
            return left

        node = _DraftNode(
            start=start,
            round_index=round_index,
            kind="MATCH",
            left=left,
            right=right,
        )
        draft_nodes.append(node)
        return node

    max_round_index = bracket_size.bit_length() - 2
    build(0, bracket_size, max_round_index)

    for round_index in sorted({node.round_index for node in draft_nodes}):
        round_nodes = sorted(
            (node for node in draft_nodes if node.round_index == round_index),
            key=lambda node: node.start,
        )
        for position, node in enumerate(round_nodes):
            node.position = position
            node.key = f"r{round_index + 1}-p{position + 1}"

    nodes = tuple(
        BracketNode(
            key=node.key,
            round_index=node.round_index,
            position=node.position,
            kind=node.kind,
            slots=(_to_slot(node.left), _to_slot(node.right)),
            automatic_winner_id=node.automatic_winner_id,
        )
        for node in sorted(draft_nodes, key=lambda item: (item.round_index, item.position))
    )
    return BracketPlan(
        bracket_size=bracket_size,
        participant_ids=tuple(entrant.participant_id for entrant in seeded),
        nodes=nodes,
    )
