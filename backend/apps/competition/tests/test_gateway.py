from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

from django.test import TestCase
from django.utils import timezone as django_timezone
from rest_framework.exceptions import NotFound

from backend.apps.accounts.models import User
from backend.apps.common.contracts import (
    AttemptReceipt,
    InfrastructureFailureReceipt,
    ResultApplication,
    ResultReceipt,
    RunProblemSnapshot,
    SubmissionPermit,
    WorkspaceContext,
)
from backend.apps.competition.gateway import (
    CompetitionGatewayConflict,
    CompetitionGatewayUnavailable,
    DjangoCompetitionGateway,
    RunProblemSnapshotUnavailable,
)
from backend.apps.competition.models import Match, MatchRun, MatchSlot
from backend.apps.competition.runtime import configure_match_run, start_match_run
from backend.apps.competition.services import generate_bracket
from backend.apps.tournaments.models import Tournament, TournamentParticipant
from backend.apps.tournaments.services import assign_participant


START = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)


class Catalog:
    def __init__(self, problem_id):
        self.problem_id = problem_id

    def describe_ready(self, problem_ids):
        return (
            SimpleNamespace(
                problem_id=self.problem_id,
                version="v3",
                label="A",
                time_limit_ms=1000,
                memory_limit_bytes=64_000_000,
                languages=(SimpleNamespace(id="python3"),),
            ),
        )

    def load_bundle(self, problem_id, version):
        return SimpleNamespace(problem_id=problem_id, version=version, checksum="a" * 64)


class CompetitionGatewayTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="gateway-admin@example.test",
            display_name="Admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        self.players = [
            User.objects.create_user(
                email=f"gateway-player-{index}@example.test",
                display_name=f"Player {index}",
                password="test-password-123456",
            )
            for index in range(4)
        ]
        self.tournament = Tournament.objects.create(
            title="Gateway test",
            starts_at=START,
            ends_at=START + timedelta(hours=1),
            participant_limit=4,
            created_by=self.admin,
        )
        for index, player in enumerate(self.players, start=1):
            assign_participant(self.tournament.pk, player.pk, seed=index)
        self.match = next(
            item
            for item in generate_bracket(self.tournament.pk)
            if item.kind == Match.Kind.PLAYED
        )
        self.problem_id = uuid4()
        self.run = configure_match_run(
            self.match.pk,
            problem_ids=[self.problem_id],
            allowed_duration_ms=600_000,
            start_mode="manual",
            scoring_rule=None,
            catalog=Catalog(self.problem_id),
        )
        self.frozen_players = tuple(
            User.objects.get(pk=UUID(value)) for value in self.run.participant_user_ids
        )
        self.outsider = next(
            player for player in self.players if player.pk not in {item.pk for item in self.frozen_players}
        )
        self.gateway = DjangoCompetitionGateway()

    def start(self):
        self.run = start_match_run(self.run.pk, now=START)

    def test_submission_permit_uses_frozen_member_run_problem_and_server_clock(self):
        self.start()

        permit = self.gateway.authorize_submission(
            self.frozen_players[0].pk,
            self.match.pk,
            self.run.pk,
            self.problem_id,
            START + timedelta(milliseconds=12_345),
        )

        self.assertEqual(
            permit,
            SubmissionPermit(self.run.pk, 12_345, self.run.scoring_version),
        )

    def test_gateway_bridges_accepted_result_and_infrastructure_failure_ports(self):
        self.start()
        accepted = AttemptReceipt(
            submission_id=uuid4(),
            run_id=self.run.pk,
            user_id=self.frozen_players[0].pk,
            problem_id=self.problem_id,
            received_at=START + timedelta(milliseconds=12_345),
            elapsed_ms=12_345,
            scoring_version=self.run.scoring_version,
        )
        self.gateway.register_accepted(accepted)
        result = ResultReceipt(
            submission_id=accepted.submission_id,
            run_id=accepted.run_id,
            user_id=accepted.user_id,
            problem_id=accepted.problem_id,
            received_at=accepted.received_at,
            elapsed_ms=accepted.elapsed_ms,
            scoring_version=accepted.scoring_version,
            verdict="OK",
        )

        self.assertEqual(self.gateway.apply_result(result), ResultApplication(applied=True))
        self.assertEqual(self.gateway.apply_result(result), ResultApplication(applied=False))

        pending = AttemptReceipt(
            submission_id=uuid4(),
            run_id=self.run.pk,
            user_id=self.frozen_players[1].pk,
            problem_id=self.problem_id,
            received_at=START + timedelta(milliseconds=25_000),
            elapsed_ms=25_000,
            scoring_version=self.run.scoring_version,
        )
        self.gateway.register_accepted(pending)
        self.gateway.record_infrastructure_failure(
            InfrastructureFailureReceipt(
                submission_id=pending.submission_id,
                run_id=pending.run_id,
                reason_code="judge_infrastructure_error",
                retryable=True,
            )
        )
        self.assertTrue(
            self.run.accepted_attempts.get(pk=pending.submission_id).infrastructure_failure.retryable
        )

    def test_submission_denies_actor_not_in_frozen_snapshot_even_if_mutable_slot_changes(self):
        self.start()
        slot = MatchSlot.objects.get(match=self.match, slot_index=0)
        slot.participant_id = self.outsider.tournament_entries.get(
            tournament=self.tournament
        ).pk
        slot.save(update_fields=("participant",))

        with self.assertRaises(NotFound):
            self.gateway.authorize_submission(
                self.outsider.pk,
                self.match.pk,
                self.run.pk,
                self.problem_id,
                START + timedelta(seconds=5),
            )
        allowed = self.gateway.authorize_submission(
            self.frozen_players[0].pk,
            self.match.pk,
            self.run.pk,
            self.problem_id,
            START + timedelta(seconds=5),
        )
        self.assertEqual(allowed.elapsed_ms, 5_000)

    def test_submission_requires_active_membership_and_rejects_wrong_match_problem_or_deadline(self):
        self.start()
        TournamentParticipant.objects.filter(
            tournament=self.tournament,
            user=self.frozen_players[0],
        ).update(status=TournamentParticipant.Status.REMOVED)
        with self.assertRaises(NotFound):
            self.gateway.authorize_submission(
                self.frozen_players[0].pk,
                self.match.pk,
                self.run.pk,
                self.problem_id,
                START + timedelta(seconds=5),
            )

        for match_id, problem_id, received_at, error in (
            (uuid4(), self.problem_id, START + timedelta(seconds=5), NotFound),
            (self.match.pk, uuid4(), START + timedelta(seconds=5), NotFound),
            (self.match.pk, self.problem_id, START + timedelta(milliseconds=600_000), CompetitionGatewayConflict),
        ):
            with self.subTest(error=error):
                with self.assertRaises(error):
                    self.gateway.authorize_submission(
                        self.frozen_players[1].pk,
                        match_id,
                        self.run.pk,
                        problem_id,
                        received_at,
                    )

    def test_submission_is_closed_before_start_and_after_run_is_superseded(self):
        with self.assertRaises(CompetitionGatewayConflict):
            self.gateway.authorize_submission(
                self.frozen_players[0].pk,
                self.match.pk,
                self.run.pk,
                self.problem_id,
                START + timedelta(seconds=1),
            )
        self.start()
        replacement = MatchRun.objects.create(
            match=self.match,
            sequence=self.run.sequence + 1,
            status=MatchRun.Status.READY,
            allowed_duration_ms=self.run.allowed_duration_ms,
            score_rule=self.run.score_rule,
            start_mode=self.run.start_mode,
            problem_versions=self.run.problem_versions,
            participant_user_ids=self.run.participant_user_ids,
        )
        MatchRun.objects.filter(pk=self.run.pk).update(status=MatchRun.Status.SUPERSEDED)
        Match.objects.filter(pk=self.match.pk).update(current_run=replacement, status=Match.Status.READY)

        with self.assertRaises(CompetitionGatewayConflict):
            self.gateway.authorize_submission(
                self.frozen_players[0].pk,
                self.match.pk,
                self.run.pk,
                self.problem_id,
                START + timedelta(seconds=2),
            )

    def test_workspace_actions_are_narrow_and_statement_stays_hidden_until_start(self):
        before = self.gateway.authorize_workspace(
            self.frozen_players[0].pk,
            self.match.pk,
            self.run.pk,
            self.problem_id,
            "statement",
        )
        self.assertIsInstance(before, WorkspaceContext)
        self.assertFalse(before.condition_available)
        self.assertNotIn("read_statement", before.allowed_actions)

        draft = self.gateway.authorize_workspace(
            self.frozen_players[0].pk,
            self.match.pk,
            self.run.pk,
            self.problem_id,
            "draft",
        )
        self.assertEqual(draft.allowed_actions, frozenset({"read_draft", "write_draft"}))
        self.assertNotIn("submit", draft.allowed_actions)
        metadata = self.gateway.authorize_workspace(
            self.frozen_players[0].pk,
            self.match.pk,
            self.run.pk,
            self.problem_id,
            "metadata",
        )
        history = self.gateway.authorize_workspace(
            self.frozen_players[0].pk,
            self.match.pk,
            self.run.pk,
            self.problem_id,
            "history",
        )
        self.assertEqual(metadata.allowed_actions, frozenset({"read_metadata"}))
        self.assertEqual(history.allowed_actions, frozenset({"read_history"}))

        self.run = start_match_run(
            self.run.pk,
            now=django_timezone.now() - timedelta(seconds=1),
        )
        statement = self.gateway.authorize_workspace(
            self.frozen_players[0].pk,
            self.match.pk,
            self.run.pk,
            self.problem_id,
            "statement",
        )
        self.assertTrue(statement.condition_available)
        self.assertEqual(statement.allowed_actions, frozenset({"read_statement"}))
        draft = self.gateway.authorize_workspace(
            self.frozen_players[0].pk,
            self.match.pk,
            self.run.pk,
            self.problem_id,
            "draft",
        )
        self.assertEqual(draft.allowed_actions, frozenset({"read_draft", "write_draft", "submit"}))

    def test_workspace_hides_foreign_or_admin_source_and_allows_admin_statement(self):
        with self.assertRaises(NotFound):
            self.gateway.authorize_workspace(
                self.outsider.pk,
                self.match.pk,
                self.run.pk,
                self.problem_id,
                "metadata",
            )
        with self.assertRaises(NotFound):
            self.gateway.authorize_workspace(
                self.admin.pk,
                self.match.pk,
                self.run.pk,
                self.problem_id,
                "draft",
            )
        admin_statement = self.gateway.authorize_workspace(
            self.admin.pk,
            self.match.pk,
            self.run.pk,
            self.problem_id,
            "statement",
        )
        self.assertTrue(admin_statement.condition_available)
        self.assertEqual(admin_statement.allowed_actions, frozenset({"read_statement"}))

    def test_snapshot_provider_returns_only_the_persisted_run_version_and_checksum(self):
        snapshot = self.gateway.resolve(self.run.pk, self.problem_id)

        self.assertEqual(
            snapshot,
            RunProblemSnapshot(self.run.pk, self.problem_id, "v3", "a" * 64),
        )

    def test_snapshot_provider_resolves_superseded_run_and_fails_closed_on_corruption(self):
        older_run_id = self.run.pk
        replacement = MatchRun.objects.create(
            match=self.match,
            sequence=self.run.sequence + 1,
            status=MatchRun.Status.READY,
            allowed_duration_ms=self.run.allowed_duration_ms,
            score_rule=self.run.score_rule,
            start_mode=self.run.start_mode,
            problem_versions=[{
                "problemId": str(self.problem_id),
                "version": "v4",
                "checksum": "b" * 64,
            }],
            participant_user_ids=self.run.participant_user_ids,
        )
        MatchRun.objects.filter(pk=older_run_id).update(status=MatchRun.Status.SUPERSEDED)
        Match.objects.filter(pk=self.match.pk).update(current_run=replacement, status=Match.Status.READY)

        old_snapshot = self.gateway.resolve(older_run_id, self.problem_id)
        new_snapshot = self.gateway.resolve(replacement.pk, self.problem_id)
        self.assertEqual(old_snapshot.problem_version, "v3")
        self.assertEqual(old_snapshot.problem_checksum, "a" * 64)
        self.assertEqual(new_snapshot.problem_version, "v4")

        MatchRun.objects.filter(pk=older_run_id).update(
            problem_versions=[{"problemId": str(self.problem_id), "version": "v3", "checksum": "invalid"}]
        )
        with self.assertRaises(RunProblemSnapshotUnavailable):
            self.gateway.resolve(older_run_id, self.problem_id)
        with self.assertRaises(CompetitionGatewayUnavailable):
            self.gateway.authorize_workspace(
                self.frozen_players[0].pk,
                self.match.pk,
                older_run_id,
                self.problem_id,
                "statement",
            )
