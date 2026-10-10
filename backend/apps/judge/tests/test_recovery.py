import json
import subprocess
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from backend.apps.judge.runner import (
    LEASE_LABEL,
    OWNER_LABEL,
    OWNER_VALUE,
    SUBMISSION_LABEL,
    RunnerInfrastructureError,
    cleanup_orphaned_claim_containers,
)


class OrphanContainerRecoveryTests(TestCase):
    @patch("backend.apps.judge.runner._run_docker")
    @patch("backend.apps.submissions.models.Submission.objects.filter")
    def test_reaper_keeps_current_lease_and_removes_only_expired_claim(self, filter_claim, docker):
        active_submission, expired_submission = uuid4(), uuid4()
        active_token, expired_token = uuid4(), uuid4()
        active_container, expired_container = "a" * 64, "b" * 64
        docker.side_effect = [
            subprocess.CompletedProcess([], 0, f"{active_container}\n{expired_container}\n".encode(), b""),
            subprocess.CompletedProcess([], 0, json.dumps({
                OWNER_LABEL: OWNER_VALUE,
                SUBMISSION_LABEL: str(active_submission),
                LEASE_LABEL: str(active_token),
            }).encode(), b""),
            subprocess.CompletedProcess([], 0, json.dumps({
                OWNER_LABEL: OWNER_VALUE,
                SUBMISSION_LABEL: str(expired_submission),
                LEASE_LABEL: str(expired_token),
            }).encode(), b""),
            subprocess.CompletedProcess([], 0, b"", b""),
        ]
        filter_claim.return_value.exists.side_effect = [True, False]

        removed = cleanup_orphaned_claim_containers(
            now=datetime(2026, 10, 10, tzinfo=timezone.utc)
        )

        self.assertEqual(removed, 1)
        self.assertEqual(filter_claim.call_count, 2)
        self.assertEqual(docker.call_args.args[0], ["docker", "rm", "--force", expired_container])

    @patch("backend.apps.judge.runner._run_docker")
    def test_reaper_fails_closed_on_unlabelled_or_malformed_container(self, docker):
        container_id = "c" * 64
        docker.side_effect = [
            subprocess.CompletedProcess([], 0, f"{container_id}\n".encode(), b""),
            subprocess.CompletedProcess([], 0, b"{}", b""),
        ]

        with self.assertRaisesRegex(RunnerInfrastructureError, "missing valid claim labels"):
            cleanup_orphaned_claim_containers(now=datetime(2026, 10, 10, tzinfo=timezone.utc))

        self.assertEqual(docker.call_count, 2)
