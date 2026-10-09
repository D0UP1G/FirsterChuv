import unittest
from uuid import uuid4

from backend.apps.competition.domain.admin_actions import (
    AdminAction,
    AdminActionError,
    AdminActor,
    AdminCommand,
    MatchAdminSnapshot,
    ReplacementParticipant,
    RunStatus,
    plan_extension,
    plan_pause,
    plan_rematch,
    plan_replacement,
    plan_resume,
    plan_technical_result,
)
from backend.apps.competition.domain.command_store import (
    AdminCommandIntent,
    AdminCommandStore,
    AdminCommandStoreError,
    lookup_command,
    record_command,
)


ACTOR_ID = uuid4()
PLAYER_A = uuid4()
PLAYER_B = uuid4()
PLAYER_C = uuid4()
MATCH_ID = uuid4()
RUN_ID = uuid4()


def actor(*, role="admin", is_active=True):
    return AdminActor(user_id=ACTOR_ID, role=role, is_active=is_active)


def command(*, reason="admin action", command_id="command-1", admin=None):
    return AdminCommand(actor=admin or actor(), command_id=command_id, reason=reason)


def snapshot(
    status=RunStatus.RUNNING,
    *,
    run_id=RUN_ID,
    players=(PLAYER_A, PLAYER_B),
    downstream_started=False,
):
    return MatchAdminSnapshot(
        match_id=MATCH_ID,
        run_id=run_id,
        run_status=status,
        participant_user_ids=players,
        downstream_started=downstream_started,
    )


def command_intent(action, *, command_value=None, parameters=(), match_id=MATCH_ID):
    return AdminCommandIntent(
        match_id=match_id,
        command=command_value or command(),
        action=action,
        parameters=parameters,
    )


class AdminActionContextTests(unittest.TestCase):
    def test_only_active_admin_actor_can_be_constructed(self):
        with self.assertRaisesRegex(AdminActionError, "admin role"):
            actor(role="participant")
        with self.assertRaisesRegex(AdminActionError, "active admin"):
            actor(is_active=False)

    def test_actor_and_match_ids_must_be_valid_uuids(self):
        with self.assertRaisesRegex(AdminActionError, "UUID"):
            AdminActor(user_id="bad-id", role="admin", is_active=True)
        with self.assertRaisesRegex(AdminActionError, "UUID"):
            MatchAdminSnapshot(
                match_id="bad-id",
                run_id=RUN_ID,
                run_status=RunStatus.RUNNING,
                participant_user_ids=(PLAYER_A, PLAYER_B),
            )
        with self.assertRaisesRegex(AdminActionError, "cannot occupy both"):
            snapshot(players=(PLAYER_A, PLAYER_A))

    def test_command_requires_nonempty_idempotency_key_and_valid_reason(self):
        with self.assertRaisesRegex(AdminActionError, "command_id"):
            command(command_id=" ")
        with self.assertRaisesRegex(AdminActionError, "reason"):
            command(reason=" " * 2)


class AdminCommandStoreTests(unittest.TestCase):
    def test_exact_retry_returns_original_plan_before_state_revalidation(self):
        request = command(command_id="pause-retry", reason="Safety stop")
        intent = command_intent(AdminAction.PAUSE, command_value=request)
        plan = plan_pause(snapshot(), request)
        store = record_command(AdminCommandStore(), intent, plan)

        self.assertIsNone(lookup_command(AdminCommandStore(), intent))
        self.assertEqual(lookup_command(store, intent), plan)
        self.assertIs(record_command(store, intent, plan), store)
        self.assertEqual(len(store.receipts), 1)

    def test_reusing_key_with_changed_reason_is_a_conflict(self):
        request = command(command_id="pause-conflict", reason="Safety stop")
        intent = command_intent(AdminAction.PAUSE, command_value=request)
        store = record_command(
            AdminCommandStore(), intent, plan_pause(snapshot(), request)
        )
        changed = command_intent(
            AdminAction.PAUSE,
            command_value=command(command_id="pause-conflict", reason="Other reason"),
        )

        with self.assertRaisesRegex(AdminCommandStoreError, "different intent"):
            lookup_command(store, changed)

    def test_reusing_key_with_changed_action_argument_is_a_conflict(self):
        request = command(command_id="extend-conflict", reason="Longer round")
        plan = plan_extension(
            snapshot(), request, seconds=30, max_extension_seconds=600
        )
        original = command_intent(
            AdminAction.EXTEND,
            command_value=request,
            parameters=(("extension_seconds", 30),),
        )
        store = record_command(AdminCommandStore(), original, plan)
        changed = command_intent(
            AdminAction.EXTEND,
            command_value=request,
            parameters=(("extension_seconds", 60),),
        )

        with self.assertRaisesRegex(AdminCommandStoreError, "different intent"):
            lookup_command(store, changed)

    def test_fingerprint_distinguishes_integer_from_boolean_parameters(self):
        request = command(command_id="extend-bool", reason="Short extension")
        plan = plan_extension(
            snapshot(), request, seconds=1, max_extension_seconds=600
        )
        intent = command_intent(
            AdminAction.EXTEND,
            command_value=request,
            parameters=(("extension_seconds", 1),),
        )
        store = record_command(AdminCommandStore(), intent, plan)
        boolean_payload = command_intent(
            AdminAction.EXTEND,
            command_value=request,
            parameters=(("extension_seconds", True),),
        )

        with self.assertRaisesRegex(AdminCommandStoreError, "different intent"):
            lookup_command(store, boolean_payload)

    def test_command_key_isolated_by_match_and_actor_is_in_request_fingerprint(self):
        request = command(command_id="pause-scope", reason="Safety stop")
        intent = command_intent(AdminAction.PAUSE, command_value=request)
        store = record_command(
            AdminCommandStore(), intent, plan_pause(snapshot(), request)
        )
        other_match = command_intent(
            AdminAction.PAUSE,
            command_value=request,
            match_id=uuid4(),
        )
        other_admin = command_intent(
            AdminAction.PAUSE,
            command_value=command(
                command_id="pause-scope",
                reason="Safety stop",
                admin=AdminActor(user_id=uuid4(), role="admin", is_active=True),
            ),
        )

        self.assertIsNone(lookup_command(store, other_match))
        with self.assertRaisesRegex(AdminCommandStoreError, "different intent"):
            lookup_command(store, other_admin)

    def test_recorded_plan_must_match_intent_arguments(self):
        request = command(command_id="extend-plan", reason="Longer round")
        intent = command_intent(
            AdminAction.EXTEND,
            command_value=request,
            parameters=(("extension_seconds", 60),),
        )
        plan = plan_extension(
            snapshot(), request, seconds=30, max_extension_seconds=600
        )

        with self.assertRaisesRegex(AdminCommandStoreError, "does not match"):
            record_command(AdminCommandStore(), intent, plan)

    def test_replacement_intent_uses_normalized_participant_ids(self):
        request = command(command_id="replace-1", reason="Player withdrew")
        replacement = ReplacementParticipant(
            user_id=PLAYER_C,
            role="participant",
            is_active=True,
        )
        plan = plan_replacement(
            snapshot(RunStatus.READY),
            request,
            old_user_id=PLAYER_A,
            replacement=replacement,
        )
        intent = command_intent(
            AdminAction.REPLACE_PARTICIPANT,
            command_value=request,
            parameters=(
                ("replaced_user_id", PLAYER_A),
                ("replacement_user_id", PLAYER_C),
            ),
        )

        store = record_command(AdminCommandStore(), intent, plan)

        self.assertEqual(lookup_command(store, intent), plan)

    def test_intent_rejects_unsupported_parameters_and_duplicate_names(self):
        request = command(command_id="pause-parameters")

        with self.assertRaisesRegex(AdminCommandStoreError, "do not match"):
            command_intent(
                AdminAction.PAUSE,
                command_value=request,
                parameters=(("unexpected", "value"),),
            )
        with self.assertRaisesRegex(AdminCommandStoreError, "unique"):
            command_intent(
                AdminAction.EXTEND,
                command_value=request,
                parameters=(
                    ("extension_seconds", 30),
                    ("extension_seconds", 60),
                ),
            )


class PauseResumeExtensionTests(unittest.TestCase):
    def test_pause_requires_running_run_and_reason(self):
        plan = plan_pause(snapshot(), command(command_id="pause-1", reason="Safety stop"))

        self.assertEqual(plan.action, AdminAction.PAUSE)
        self.assertEqual(plan.expected_run_status, RunStatus.RUNNING)
        self.assertEqual(plan.run_status_after, RunStatus.PAUSED)
        self.assertEqual(plan.reason, "Safety stop")
        self.assertEqual(plan.actor_user_id, ACTOR_ID)
        self.assertEqual(plan.command_id, "pause-1")

        with self.assertRaisesRegex(AdminActionError, "not allowed"):
            plan_pause(snapshot(RunStatus.READY), command())
        with self.assertRaisesRegex(AdminActionError, "reason is required"):
            plan_pause(snapshot(), command(reason=None))

    def test_resume_only_from_paused_and_reason_is_optional_per_api_contract(self):
        plan = plan_resume(
            snapshot(RunStatus.PAUSED),
            command(command_id="resume-1", reason=None),
        )

        self.assertEqual(plan.action, AdminAction.RESUME)
        self.assertEqual(plan.run_status_after, RunStatus.RUNNING)
        self.assertIsNone(plan.reason)
        with self.assertRaisesRegex(AdminActionError, "not allowed"):
            plan_resume(snapshot(RunStatus.RUNNING), command())

    def test_extension_is_positive_bounded_and_only_during_active_run(self):
        plan = plan_extension(
            snapshot(RunStatus.PAUSED),
            command(reason="Final round extension"),
            seconds=120,
            max_extension_seconds=300,
        )

        self.assertEqual(plan.action, AdminAction.EXTEND)
        self.assertEqual(plan.run_status_after, RunStatus.PAUSED)
        self.assertEqual(plan.extension_seconds, 120)
        for seconds, maximum in ((0, 300), (-1, 300), (301, 300), (True, 300), (1, 0)):
            with self.subTest(seconds=seconds, maximum=maximum):
                with self.assertRaises(AdminActionError):
                    plan_extension(
                        snapshot(),
                        command(),
                        seconds=seconds,
                        max_extension_seconds=maximum,
                    )
        with self.assertRaisesRegex(AdminActionError, "not allowed"):
            plan_extension(
                snapshot(RunStatus.READY),
                command(),
                seconds=10,
                max_extension_seconds=300,
            )


class TechnicalResultAndRematchTests(unittest.TestCase):
    def test_technical_result_requires_active_player_reason_and_unstarted_downstream(self):
        plan = plan_technical_result(
            snapshot(RunStatus.FINALIZING),
            command(reason="Opponent withdrew"),
            winner_user_id=PLAYER_A,
        )

        self.assertEqual(plan.action, AdminAction.TECHNICAL_RESULT)
        self.assertEqual(plan.run_status_after, RunStatus.FINISHED)
        self.assertEqual(plan.winner_user_id, PLAYER_A)
        with self.assertRaisesRegex(AdminActionError, "participant"):
            plan_technical_result(snapshot(), command(), winner_user_id=PLAYER_C)
        with self.assertRaisesRegex(AdminActionError, "reason is required"):
            plan_technical_result(snapshot(), command(reason=None), winner_user_id=PLAYER_A)
        with self.assertRaisesRegex(AdminActionError, "downstream match started"):
            plan_technical_result(
                snapshot(downstream_started=True),
                command(),
                winner_user_id=PLAYER_A,
            )
        with self.assertRaisesRegex(AdminActionError, "not allowed"):
            plan_technical_result(
                snapshot(RunStatus.FINISHED),
                command(),
                winner_user_id=PLAYER_A,
            )

    def test_rematch_supersedes_old_run_without_carrying_score(self):
        plan = plan_rematch(snapshot(RunStatus.TIED), command(reason="Agreed rematch"))

        self.assertEqual(plan.action, AdminAction.REMATCH)
        self.assertEqual(plan.run_status_after, RunStatus.SUPERSEDED)
        self.assertTrue(plan.supersede_current_run)
        self.assertTrue(plan.new_run_required)
        self.assertFalse(plan.carry_score_to_new_run)

        finished = plan_rematch(
            snapshot(RunStatus.FINISHED),
            command(command_id="rematch-finished", reason="Before downstream start"),
        )
        self.assertTrue(finished.new_run_required)

    def test_rematch_rejects_pending_finalize_and_started_downstream(self):
        for context in (
            snapshot(RunStatus.FINALIZING),
            snapshot(RunStatus.FINISHED, downstream_started=True),
        ):
            with self.subTest(status=context.run_status, downstream=context.downstream_started):
                with self.assertRaises(AdminActionError):
                    plan_rematch(context, command())


class ParticipantReplacementTests(unittest.TestCase):
    def replacement(self, *, role="participant", is_active=True, user_id=PLAYER_C):
        return ReplacementParticipant(user_id=user_id, role=role, is_active=is_active)

    def test_prestart_replacement_changes_only_the_requested_slot(self):
        plan = plan_replacement(
            snapshot(RunStatus.READY, run_id=None),
            command(reason="Participant unavailable"),
            old_user_id=PLAYER_B,
            replacement=self.replacement(),
        )

        self.assertEqual(plan.action, AdminAction.REPLACE_PARTICIPANT)
        self.assertEqual(plan.slot_index, 1)
        self.assertEqual(plan.replaced_user_id, PLAYER_B)
        self.assertEqual(plan.replacement_user_id, PLAYER_C)
        self.assertFalse(plan.new_run_required)
        self.assertFalse(plan.supersede_current_run)

    def test_running_replacement_supersedes_run_and_never_transfers_score(self):
        plan = plan_replacement(
            snapshot(RunStatus.RUNNING),
            command(reason="Player disconnected"),
            old_user_id=PLAYER_A,
            replacement=self.replacement(),
        )

        self.assertEqual(plan.run_status_after, RunStatus.SUPERSEDED)
        self.assertTrue(plan.new_run_required)
        self.assertTrue(plan.supersede_current_run)
        self.assertFalse(plan.carry_score_to_new_run)

    def test_replacement_validates_slot_candidate_state_and_downstream(self):
        with self.assertRaisesRegex(AdminActionError, "old user"):
            plan_replacement(
                snapshot(RunStatus.READY),
                command(),
                old_user_id=PLAYER_C,
                replacement=self.replacement(),
            )
        with self.assertRaisesRegex(AdminActionError, "already occupies"):
            plan_replacement(
                snapshot(RunStatus.READY),
                command(),
                old_user_id=PLAYER_A,
                replacement=self.replacement(user_id=PLAYER_B),
            )
        with self.assertRaisesRegex(AdminActionError, "participant role"):
            self.replacement(role="admin")
        with self.assertRaisesRegex(AdminActionError, "must be active"):
            self.replacement(is_active=False)
        with self.assertRaisesRegex(AdminActionError, "not allowed"):
            plan_replacement(
                snapshot(RunStatus.FINALIZING),
                command(),
                old_user_id=PLAYER_A,
                replacement=self.replacement(),
            )
        with self.assertRaisesRegex(AdminActionError, "downstream match started"):
            plan_replacement(
                snapshot(RunStatus.READY, run_id=None, downstream_started=True),
                command(),
                old_user_id=PLAYER_A,
                replacement=self.replacement(),
            )


if __name__ == "__main__":
    unittest.main()
