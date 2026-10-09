from __future__ import annotations

import base64
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.apps.judge.runner import (  # noqa: E402
    CPP20_COMPILER_ARGV,
    IMAGE,
    MAX_INPUT_BYTES,
    MAX_SOURCE_BYTES,
    DockerRunner,
    RunnerInfrastructureError,
    _cleanup,
    _run_docker,
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
        expected_length = MAX_INPUT_BYTES + len(f"1 {MAX_INPUT_BYTES}\n") + 1
        self.assertEqual(len(encode_request(b"x", b"i" * MAX_INPUT_BYTES)), expected_length)


class DockerPolicyTests(unittest.TestCase):
    def test_container_has_fixed_isolation_and_resource_options(self) -> None:
        command = build_docker_create_args("firsterchuv-a3-01-" + "a" * 32, "run")
        joined = " ".join(command)
        for required in (
            "--pull=never",
            "--platform=linux/amd64",
            "--network=none",
            "--read-only",
            "--memory=536870912",
            "--memory-swap=536870912",
            "--cpus=1.0",
            "--pids-limit=64",
            "--user=65534:65534",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "/work:rw,exec,nosuid,nodev,size=64m,uid=65534,gid=65534",
            IMAGE,
        ):
            self.assertIn(required, joined)
        self.assertFalse(any(item == "--pid" or item.startswith("--pid=") for item in command))
        self.assertNotIn("--mount", command)
        self.assertNotIn("--volume", command)
        self.assertFalse(any(item.startswith("--env") or item == "-v" for item in command))
        self.assertFalse(any("docker.sock" in item for item in command))
        self.assertEqual(command[-1], "2000")

    def test_task_limits_are_trusted_bounded_docker_arguments(self) -> None:
        command = build_docker_create_args(
            "firsterchuv-a3-01-" + "d" * 32,
            "run",
            memory_limit_bytes=128 * 1024 * 1024,
            time_limit_ms=725,
        )
        self.assertIn("--memory=134217728", command)
        self.assertIn("--memory-swap=134217728", command)
        self.assertEqual(command[-1], "725")
        for invalid in (True, 31 * 1024 * 1024, 512 * 1024 * 1024 + 1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                build_docker_create_args("firsterchuv-a3-01-" + "e" * 32, "run", memory_limit_bytes=invalid)
        for invalid in (True, 0, 120_001):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                build_docker_create_args("firsterchuv-a3-01-" + "f" * 32, "run", time_limit_ms=invalid)

    def test_only_registry_compiler_matching_the_image_profile_is_supported(self) -> None:
        runner = DockerRunner()
        compiler = SimpleNamespace(
            language_id="cpp20",
            image=IMAGE,
            source_filename="main.cpp",
            compile_argv=CPP20_COMPILER_ARGV,
        )
        self.assertTrue(runner.supports_compiler(compiler))
        self.assertFalse(runner.supports_compiler(SimpleNamespace(**{**vars(compiler), "image": "attacker/image"})))

    def test_container_name_cannot_be_supplied_by_a_caller(self) -> None:
        with self.assertRaises(ValueError):
            build_docker_create_args("arbitrary-name;touch /tmp/pwned", "run")

    def test_only_compile_and_run_modes_are_accepted(self) -> None:
        name = "firsterchuv-a3-01-" + "b" * 32
        self.assertEqual(build_docker_create_args(name, "compile")[-1], "compile")
        run_command = build_docker_create_args(name, "run")
        self.assertEqual(run_command[-2], "run")
        self.assertEqual(run_command[-1], "2000")
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
    @patch("backend.apps.judge.runner._cleanup")
    @patch("backend.apps.judge.runner._run_docker", side_effect=RunnerInfrastructureError("daemon unavailable"))
    def test_missing_docker_daemon_fails_closed(self, _docker, _cleanup) -> None:
        # This test checks only fail-closed control flow; it never starts Docker or solution code.
        with self.assertRaises(RunnerInfrastructureError):
            DockerRunner().execute(b"int main() { return 0; }", b"")
        _cleanup.assert_called_once()

    @patch("backend.apps.judge.runner._run_docker")
    def test_oom_is_true_only_for_exact_docker_state(self, docker_call) -> None:
        runner = DockerRunner()
        docker_call.return_value = subprocess.CompletedProcess([], 0, b"true\n", b"")
        self.assertTrue(runner._inspect_oom("a" * 64))
        docker_call.return_value = subprocess.CompletedProcess([], 0, b"false\n", b"")
        self.assertFalse(runner._inspect_oom("a" * 64))
        docker_call.return_value = subprocess.CompletedProcess([], 0, b"unknown\n", b"")
        with self.assertRaises(RunnerInfrastructureError):
            runner._inspect_oom("a" * 64)


class BoundedDockerPipeTests(unittest.TestCase):
    def test_streams_stdin_and_drains_both_bounded_output_pipes(self) -> None:
        payload = b"x" * (128 * 1024)
        script = (
            "import sys; data=sys.stdin.buffer.read(); "
            "sys.stderr.buffer.write(b'e' * 131072); "
            "sys.stdout.buffer.write(data)"
        )
        result = _run_docker(
            [sys.executable, "-c", script],
            timeout=5,
            input_data=payload,
            stdout_limit=len(payload),
            stderr_limit=131072,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, payload)
        self.assertEqual(result.stderr, b"e" * 131072)

    def test_stdout_overflow_kills_the_docker_cli(self) -> None:
        script = "import sys,time; sys.stdout.buffer.write(b'x'*4096); sys.stdout.flush(); time.sleep(10)"
        with self.assertRaisesRegex(RunnerInfrastructureError, "stdout exceeded"):
            _run_docker([sys.executable, "-c", script], timeout=5, stdout_limit=128)

    def test_stderr_overflow_kills_the_docker_cli(self) -> None:
        script = "import sys,time; sys.stderr.buffer.write(b'x'*4096); sys.stderr.flush(); time.sleep(10)"
        with self.assertRaisesRegex(RunnerInfrastructureError, "stderr exceeded"):
            _run_docker([sys.executable, "-c", script], timeout=5, stderr_limit=128)

    @patch("backend.apps.judge.runner.subprocess.Popen", side_effect=FileNotFoundError("docker is missing"))
    def test_missing_docker_binary_is_tolerated_only_for_missing_container_cleanup(self, _popen) -> None:
        _cleanup("firsterchuv-a3-01-" + "c" * 32, missing_ok=True)


if __name__ == "__main__":
    unittest.main()
