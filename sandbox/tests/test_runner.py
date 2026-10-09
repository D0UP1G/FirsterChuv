from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import (  # noqa: E402
    IMAGE,
    MAX_INPUT_BYTES,
    MAX_SOURCE_BYTES,
    DockerRunner,
    RunnerInfrastructureError,
    build_docker_create_args,
    encode_request,
    parse_response,
)


class RequestProtocolTests(unittest.TestCase):
    def test_request_contains_lengths_and_raw_bytes(self) -> None:
        self.assertEqual(encode_request(b"int main(){}", b"in\x00put"), b"12 6\nint main(){}in\x00put")

    def test_source_and_input_caps_are_enforced(self) -> None:
        with self.assertRaises(ValueError):
            encode_request(b"x" * (MAX_SOURCE_BYTES + 1), b"")
        with self.assertRaises(ValueError):
            encode_request(b"x", b"x" * (MAX_INPUT_BYTES + 1))
        with self.assertRaises(ValueError):
            encode_request(b"", b"")


class DockerPolicyTests(unittest.TestCase):
    def test_container_has_fixed_isolation_and_resource_options(self) -> None:
        command = build_docker_create_args("firsterchuv-a3-01-" + "a" * 32, "run")
        joined = " ".join(command)
        for required in (
            "--pull=never",
            "--platform=linux/amd64",
            "--network=none",
            "--pid=private",
            "--read-only",
            "--memory=512m",
            "--memory-swap=512m",
            "--cpus=1.0",
            "--pids-limit=64",
            "--user=65534:65534",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "/work:rw,exec,nosuid,nodev,size=64m,uid=65534,gid=65534",
            IMAGE,
        ):
            self.assertIn(required, joined)
        self.assertNotIn("--mount", command)
        self.assertNotIn("--volume", command)
        self.assertFalse(any(item.startswith("--env") or item == "-v" for item in command))
        self.assertFalse(any("docker.sock" in item for item in command))

    def test_container_name_cannot_be_supplied_by_a_caller(self) -> None:
        with self.assertRaises(ValueError):
            build_docker_create_args("arbitrary-name;touch /tmp/pwned", "run")

    def test_only_compile_and_run_modes_are_accepted(self) -> None:
        name = "firsterchuv-a3-01-" + "b" * 32
        self.assertEqual(build_docker_create_args(name, "compile")[-1], "compile")
        self.assertEqual(build_docker_create_args(name, "run")[-1], "run")
        with self.assertRaises(ValueError):
            build_docker_create_args(name, "shell")


class ResponseProtocolTests(unittest.TestCase):
    def test_decodes_bounded_container_response(self) -> None:
        stdout_b64 = base64.b64encode(b"42\n").decode("ascii")
        response = (
            '{"status":"EXITED","exitCode":0,"signal":null,'
            f'"stdoutBase64":"{stdout_b64}","stderrBase64":"","artifactBase64":""}}'
        ).encode("ascii")
        parsed = parse_response(response)
        self.assertEqual(parsed.status, "EXITED")
        self.assertEqual(parsed.stdout, b"42\n")
        self.assertEqual(parsed.stderr, b"")

    def test_invalid_or_unknown_status_is_infrastructure_error(self) -> None:
        with self.assertRaises(RunnerInfrastructureError):
            parse_response(b'{"status":"OK","exitCode":0,"signal":null,"stdoutBase64":"","stderrBase64":"","artifactBase64":""}')
        with self.assertRaises(RunnerInfrastructureError):
            parse_response(b"not-json")
        with self.assertRaises(RunnerInfrastructureError):
            parse_response(b'{"status":"EXITED","exitCode":0,"signal":null,"stdoutBase64":"***","stderrBase64":"","artifactBase64":""}')


class NoRuntimeClaimTests(unittest.TestCase):
    @patch("runner._cleanup")
    @patch("runner._run_docker", side_effect=RunnerInfrastructureError("daemon unavailable"))
    def test_missing_docker_daemon_fails_closed(self, _docker, _cleanup) -> None:
        # This test checks only fail-closed control flow; it never starts Docker or solution code.
        with self.assertRaises(RunnerInfrastructureError):
            DockerRunner().execute(b"int main() { return 0; }", b"")
        _cleanup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
