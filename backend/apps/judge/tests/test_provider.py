from dataclasses import replace
from unittest import TestCase

from backend.apps.common.contracts import JudgeInfrastructureError, TrustedJudgeJob
from backend.apps.judge.policy import ExecutionLimits
from backend.apps.judge.provider import LocalJudge
from backend.apps.problems.bundle import PrivateArtifact, parse_problem_bundle
from backend.apps.problems.compilers import COMPILERS
from backend.apps.problems.tests.bundle_fixtures import PROBLEM_ID, make_bundle_archive
from backend.apps.judge.runner import ExecutionResult

TEST_COMPILERS = {"cpp20": replace(COMPILERS["cpp20"], verified=True)}


class MemoryCatalog:
    def __init__(self, bundle):
        self.bundle = bundle
        self.requested = None

    def load_bundle(self, problem_id, version):
        self.requested = (problem_id, version)
        return self.bundle


class TestSandbox:
    """Test-only execution double; never selected by runtime configuration."""

    def __init__(self, *, compile_result=None, run_results=()):
        self.compile_result = compile_result or ExecutionResult("COMPILED", 0, None, b"", b"", b"binary")
        self.run_results = list(run_results)
        self.compile_sources = []
        self.run_calls = []

    def supports_compiler(self, compiler):
        return compiler.language_id == "cpp20"

    def compile(self, source):
        self.compile_sources.append(source)
        return self.compile_result

    def run(self, artifact, stdin, *, time_limit_ms, memory_limit_bytes):
        self.run_calls.append((artifact, stdin, time_limit_ms, memory_limit_bytes))
        return self.run_results.pop(0)


def make_bundle():
    return parse_problem_bundle(make_bundle_archive())


def make_job(bundle, *, source="int main() { return 0; }", language_id="cpp20"):
    return TrustedJudgeJob(
        submission_id=PROBLEM_ID,
        source=source,
        language_id=language_id,
        problem_id=bundle.problem_id,
        problem_version=bundle.version,
        problem_checksum=bundle.checksum,
    )


def exited(stdout=b"3\n"):
    return ExecutionResult("EXITED", 0, None, stdout, b"")


class LocalJudgeTests(TestCase):
    def test_ok_uses_pinned_bundle_checksum_and_task_limits_per_test(self):
        bundle = make_bundle()
        second_test = replace(bundle.tests[0], input=b"4 5\n", expected_output=b"9\n")
        bundle = replace(
            bundle,
            tests=(bundle.tests[0], second_test),
            time_limit_ms=725,
            memory_limit_bytes=128 * 1024 * 1024,
        )
        catalog = MemoryCatalog(bundle)
        sandbox = TestSandbox(run_results=(exited(), exited(b"9\n")))

        result = LocalJudge(catalog, compiler_registry=TEST_COMPILERS, sandbox=sandbox).execute(
            make_job(bundle)
        )

        self.assertEqual(result.verdict, "OK")
        self.assertEqual(catalog.requested, (bundle.problem_id, bundle.version))
        self.assertEqual(
            sandbox.run_calls,
            [
                (b"binary", b"1 2\n", 725, 128 * 1024 * 1024),
                (b"binary", b"4 5\n", 725, 128 * 1024 * 1024),
            ],
        )

    def test_checksum_mismatch_is_infrastructure_failure_before_compile(self):
        bundle = make_bundle()
        sandbox = TestSandbox(run_results=(exited(),))
        job = replace(make_job(bundle), problem_checksum="0" * 64)

        with self.assertRaisesRegex(JudgeInfrastructureError, "identity_mismatch"):
            LocalJudge(MemoryCatalog(bundle), compiler_registry=TEST_COMPILERS, sandbox=sandbox).execute(job)
        self.assertEqual(sandbox.compile_sources, [])

    def test_unverified_or_unknown_compiler_fails_closed(self):
        bundle = make_bundle()
        sandbox = TestSandbox(run_results=(exited(),))
        judge = LocalJudge(MemoryCatalog(bundle), sandbox=sandbox)

        self.assertFalse(judge.is_supported("cpp20"))
        with self.assertRaisesRegex(JudgeInfrastructureError, "compiler_unavailable"):
            judge.execute(make_job(bundle))
        with self.assertRaisesRegex(JudgeInfrastructureError, "compiler_unavailable"):
            LocalJudge(MemoryCatalog(bundle), compiler_registry=TEST_COMPILERS, sandbox=sandbox).execute(
                make_job(bundle, language_id="not-registered")
            )
        self.assertEqual(sandbox.compile_sources, [])

    def test_checker_without_confirmed_protocol_is_infrastructure_failure(self):
        bundle = make_bundle()
        bundle = replace(
            bundle,
            private_artifacts=(
                *bundle.private_artifacts,
                PrivateArtifact("checker", "private/checkers/checker.cpp", "cpp20", b"checker"),
            ),
        )
        sandbox = TestSandbox(run_results=(exited(),))

        with self.assertRaisesRegex(JudgeInfrastructureError, "checker_protocol_unavailable"):
            LocalJudge(MemoryCatalog(bundle), compiler_registry=TEST_COMPILERS, sandbox=sandbox).execute(
                make_job(bundle)
            )
        self.assertEqual(sandbox.compile_sources, [])

    def test_compile_failure_is_ce_with_bounded_private_diagnostics(self):
        bundle = make_bundle()
        sandbox = TestSandbox(
            compile_result=ExecutionResult("COMPILE_ERROR", 1, None, b"", b"x" * 50_000)
        )

        result = LocalJudge(MemoryCatalog(bundle), compiler_registry=TEST_COMPILERS, sandbox=sandbox).execute(
            make_job(bundle)
        )

        self.assertEqual(result.verdict, "CE")
        self.assertEqual(len(result.compile_diagnostics.encode("utf-8")), 8 * 1024)
        self.assertEqual(sandbox.run_calls, [])

    def test_runtime_verdicts_are_mapped_only_from_sandbox_statuses(self):
        bundle = make_bundle()
        cases = (
            (ExecutionResult("TIME_LIMIT", None, None, b"", b""), "TL", None),
            (ExecutionResult("MEMORY_LIMIT", None, 9, b"", b""), "ML", None),
            (ExecutionResult("RUNTIME_ERROR", 1, None, b"", b""), "RE", None),
            (ExecutionResult("OUTPUT_LIMIT", None, None, b"", b""), "RE", "output_limit_exceeded"),
            (exited(b"wrong\n"), "WA", None),
        )
        for run_result, expected_verdict, expected_reason in cases:
            with self.subTest(verdict=expected_verdict, status=run_result.status):
                sandbox = TestSandbox(run_results=(run_result,))
                result = LocalJudge(
                    MemoryCatalog(bundle), compiler_registry=TEST_COMPILERS, sandbox=sandbox
                ).execute(make_job(bundle))
                self.assertEqual(result.verdict, expected_verdict)
                self.assertEqual(result.internal_reason, expected_reason)

    def test_unconfirmed_kill_is_not_a_contestant_verdict(self):
        bundle = make_bundle()
        sandbox = TestSandbox(run_results=(ExecutionResult("KILLED_UNKNOWN", None, 9, b"", b""),))

        with self.assertRaisesRegex(JudgeInfrastructureError, "termination_unclassified"):
            LocalJudge(MemoryCatalog(bundle), compiler_registry=TEST_COMPILERS, sandbox=sandbox).execute(
                make_job(bundle)
            )

    def test_unrepresentable_task_limits_fail_closed(self):
        bundle = replace(make_bundle(), memory_limit_bytes=1024)
        sandbox = TestSandbox(run_results=(exited(),))

        with self.assertRaisesRegex(JudgeInfrastructureError, "task_memory_limit_unsupported"):
            LocalJudge(MemoryCatalog(bundle), compiler_registry=TEST_COMPILERS, sandbox=sandbox).execute(
                make_job(bundle)
            )
        self.assertEqual(sandbox.compile_sources, [])

    def test_result_contains_no_submission_source_or_test_data(self):
        bundle = make_bundle()
        source = "private source marker"
        sandbox = TestSandbox(run_results=(exited(),))

        result = LocalJudge(MemoryCatalog(bundle), compiler_registry=TEST_COMPILERS, sandbox=sandbox).execute(
            make_job(bundle, source=source)
        )

        self.assertEqual(result.verdict, "OK")
        self.assertNotIn(source, repr(result))
        self.assertNotIn("1 2", repr(result))


class ExecutionPolicyTests(TestCase):
    def test_task_limits_are_strict_integers_inside_service_caps(self):
        self.assertEqual(
            ExecutionLimits.from_task(time_limit_ms=1000, memory_limit_bytes=32 * 1024 * 1024),
            ExecutionLimits(time_limit_ms=1000, memory_limit_bytes=32 * 1024 * 1024),
        )
        for value in (0, True, 120_001):
            with self.subTest(time_limit_ms=value), self.assertRaises(JudgeInfrastructureError):
                ExecutionLimits.from_task(time_limit_ms=value, memory_limit_bytes=64 * 1024 * 1024)
        for value in (True, 32 * 1024 * 1024 - 1, 512 * 1024 * 1024 + 1):
            with self.subTest(memory_limit_bytes=value), self.assertRaises(JudgeInfrastructureError):
                ExecutionLimits.from_task(time_limit_ms=1000, memory_limit_bytes=value)
