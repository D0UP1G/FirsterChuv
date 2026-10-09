import unittest

from domain.bracket import (
    BracketInputError,
    SeededParticipant,
    generate_single_elimination,
)


def entrants(count: int) -> list[SeededParticipant]:
    return [
        SeededParticipant(participant_id=f"player-{seed}", seed=seed)
        for seed in range(1, count + 1)
    ]


class GenerateSingleEliminationTests(unittest.TestCase):
    def test_two_participants_form_one_match(self) -> None:
        plan = generate_single_elimination(entrants(2))

        self.assertEqual(plan.bracket_size, 2)
        self.assertEqual(len(plan.nodes), 1)
        self.assertEqual(plan.nodes[0].round_index, 0)
        self.assertEqual(plan.nodes[0].kind, "MATCH")
        self.assertEqual(
            tuple(slot.participant_id for slot in plan.nodes[0].slots),
            ("player-1", "player-2"),
        )

    def test_three_participants_get_one_bye_without_a_played_match(self) -> None:
        plan = generate_single_elimination(entrants(3))

        first_round = [node for node in plan.nodes if node.round_index == 0]
        final = next(node for node in plan.nodes if node.round_index == 1)
        bye = next(node for node in first_round if node.kind == "BYE")
        played = [node for node in plan.nodes if node.kind == "MATCH"]

        self.assertEqual(len(played), 2)
        self.assertEqual(len(first_round), 2)
        self.assertEqual(bye.automatic_winner_id, "player-1")
        self.assertEqual(bye.slots[1].resolution, "BYE")
        self.assertEqual(final.slots[0].resolution, "PLAYER")
        self.assertEqual(final.slots[0].participant_id, "player-1")
        self.assertEqual(final.slots[0].source_match_key, bye.key)
        self.assertEqual(final.slots[1].resolution, "WAITING")

    def test_four_participants_use_deterministic_high_seed_pairings(self) -> None:
        plan = generate_single_elimination(entrants(4))
        first_round = [node for node in plan.nodes if node.round_index == 0]

        self.assertEqual(plan.bracket_size, 4)
        self.assertEqual(
            [tuple(slot.participant_id for slot in node.slots) for node in first_round],
            [("player-1", "player-4"), ("player-2", "player-3")],
        )
        self.assertEqual(sum(node.kind == "MATCH" for node in plan.nodes), 3)
        self.assertFalse(any(node.kind == "BYE" for node in plan.nodes))

    def test_five_participants_get_three_byes_and_no_fake_matches(self) -> None:
        plan = generate_single_elimination(entrants(5))
        by_round = {
            round_index: [node for node in plan.nodes if node.round_index == round_index]
            for round_index in range(3)
        }

        self.assertEqual(plan.bracket_size, 8)
        self.assertEqual([len(by_round[index]) for index in range(3)], [4, 2, 1])
        self.assertEqual(sum(node.kind == "BYE" for node in plan.nodes), 3)
        self.assertEqual(sum(node.kind == "MATCH" for node in plan.nodes), 4)
        self.assertEqual(
            [node.automatic_winner_id for node in by_round[0] if node.kind == "BYE"],
            ["player-1", "player-2", "player-3"],
        )
        final = by_round[2][0]
        self.assertEqual(final.slots[0].resolution, "WAITING")
        self.assertEqual(final.slots[1].resolution, "WAITING")

    def test_seed_order_is_normalized_and_generation_is_repeatable(self) -> None:
        roster = [
            SeededParticipant("player-3", 30),
            SeededParticipant("player-1", 10),
            SeededParticipant("player-2", 20),
        ]

        plan = generate_single_elimination(roster)

        self.assertEqual(plan.participant_ids, ("player-1", "player-2", "player-3"))
        self.assertEqual(plan, generate_single_elimination(roster))
        self.assertEqual(len({node.key for node in plan.nodes}), len(plan.nodes))

    def test_each_entrant_occupies_one_first_round_slot(self) -> None:
        for count in range(2, 6):
            with self.subTest(count=count):
                plan = generate_single_elimination(entrants(count))
                first_round = [node for node in plan.nodes if node.round_index == 0]
                first_round_ids = [
                    slot.participant_id
                    for node in first_round
                    for slot in node.slots
                    if slot.resolution == "PLAYER" and slot.source_match_key is None
                ]

                self.assertCountEqual(first_round_ids, plan.participant_ids)

    def test_invalid_rosters_are_rejected(self) -> None:
        invalid_rosters = [
            [],
            [SeededParticipant("player-1", 1)],
            [SeededParticipant("player-1", 1), SeededParticipant("player-1", 2)],
            [SeededParticipant("player-1", 1), SeededParticipant("player-2", 1)],
            [SeededParticipant("player-1", 0), SeededParticipant("player-2", 2)],
            [SeededParticipant("player-1", True), SeededParticipant("player-2", 2)],  # type: ignore[arg-type]
            [SeededParticipant("player-1", 1.5), SeededParticipant("player-2", 2)],  # type: ignore[arg-type]
            [SeededParticipant("", 1), SeededParticipant("player-2", 2)],
        ]

        for roster in invalid_rosters:
            with self.subTest(roster=roster), self.assertRaises(BracketInputError):
                generate_single_elimination(roster)


if __name__ == "__main__":
    unittest.main()
