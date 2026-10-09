"""Real local execution against immutable ProblemBundleV1 versions."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Protocol

from django.db import Error as DjangoDatabaseError

from backend.apps.common.contracts import (
    JudgeInfrastructureError,
    JudgeResult,
    JudgeVerdict,
    ProblemCatalogV1,
    TrustedJudgeJob,
)
from backend.apps.problems.bundle import ProblemBundleV1
from backend.apps.problems.compilers import COMPILERS, CompilerSpec
from backend.apps.problems.errors import ProblemNotReady
from .runner import (
    MAX_SOURCE_BYTES,
    DockerRunner,
    ExecutionResult,
    RunnerInfrastructureError,
)

from .policy import ExecutionLimits, MAX_JOB_WALL_TIME_MS

MAX_COMPILE_DIAGNOSTICS_BYTES = 8 * 1024
SUPPORTED_LANGUAGE_IDS = frozenset({"cpp20"})


class SandboxPort(Protocol):
    def supports_compiler(self, compiler: CompilerSpec) -> bool: ...

    def compile(self, source: bytes) -> ExecutionResult: ...

    def run(
        self,
        artifact: bytes,
        stdin: bytes,
        *,
        time_limit_ms: int,
        memory_limit_bytes: int,
    ) -> ExecutionResult: ...


class LocalJudge:
    """JudgeProvider implementation. Production defaults always use DockerRunner."""

    def __init__(
        self,
        catalog: ProblemCatalogV1,
        *,
        compiler_registry: Mapping[str, CompilerSpec] = COMPILERS,
        sandbox: SandboxPort | None = None,
    ) -> None:
        self._catalog = catalog
        self._compiler_registry = compiler_registry
        self._sandbox = sandbox if sandbox is not None else DockerRunner()

    def is_supported(self, language_id: str) -> bool:
        compiler = self._compiler_registry.get(language_id)
        return bool(
            compiler
            and compiler.verified
            and language_id in SUPPORTED_LANGUAGE_IDS
            and self._sandbox.supports_compiler(compiler)
        )

    def execute(self, job: TrustedJudgeJob) -> JudgeResult:
        compiler = self._compiler_registry.get(job.language_id)
        if compiler is None or not self.is_supported(job.language_id):
            raise JudgeInfrastructureError("compiler_unavailable")

        try:
            bundle = self._catalog.load_bundle(job.problem_id, job.problem_version)
        except (ProblemNotReady, DjangoDatabaseError) as error:
            raise JudgeInfrastructureError("problem_bundle_unavailable") from error
        self._validate_bundle_identity(bundle, job)

        if any(item.role == "checker" for item in bundle.private_artifacts):
            # The normalized model stores checker bytes, but the official invocation
            # protocol and verdict codes are defined by the organizer package README.
            raise JudgeInfrastructureError("checker_protocol_unavailable")
        if not bundle.tests or any(test.expected_output is None for test in bundle.tests):
            raise JudgeInfrastructureError("expected_output_or_checker_unavailable")

        try:
            source = job.source.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise JudgeInfrastructureError("submission_source_invalid") from error
        if not source or len(source) > MAX_SOURCE_BYTES:
            raise JudgeInfrastructureError("submission_source_out_of_bounds")

        limits = ExecutionLimits.from_task(
            time_limit_ms=bundle.time_limit_ms,
            memory_limit_bytes=bundle.memory_limit_bytes,
        )
        started = time.monotonic()
        try:
            compiled = self._sandbox.compile(source)
            if compiled.status in {
                "COMPILE_ERROR",
                "COMPILE_TIMEOUT",
                "COMPILE_ARTIFACT_LIMIT",
                "MEMORY_LIMIT",
            }:
                return JudgeResult(
                    verdict="CE",
                    compile_diagnostics=(
                        _bounded_diagnostics(compiled.stderr)
                        or ("Compiler exceeded the configured memory limit." if compiled.status == "MEMORY_LIMIT" else "")
                    ),
                    metrics={"elapsedMs": _elapsed_ms(started), "testCount": len(bundle.tests)},
                )
            if compiled.status != "COMPILED" or not compiled.artifact:
                raise JudgeInfrastructureError("compiler_execution_failed")

            for index, test in enumerate(bundle.tests, start=1):
                if len(test.input) > 8 * 1024 * 1024:
                    raise JudgeInfrastructureError("test_input_out_of_bounds")
                elapsed = _elapsed_ms(started)
                if elapsed + limits.time_limit_ms > MAX_JOB_WALL_TIME_MS:
                    raise JudgeInfrastructureError("judge_job_wall_limit_exceeded")
                result = self._sandbox.run(
                    compiled.artifact,
                    test.input,
                    time_limit_ms=limits.time_limit_ms,
                    memory_limit_bytes=limits.memory_limit_bytes,
                )
                verdict = _runtime_verdict(result)
                if verdict is not None:
                    return JudgeResult(
                        verdict=verdict,
                        metrics={
                            "elapsedMs": _elapsed_ms(started),
                            "testsPassed": index - 1,
                            "testCount": len(bundle.tests),
                        },
                        internal_reason=(
                            "output_limit_exceeded" if result.status == "OUTPUT_LIMIT" else None
                        ),
                    )
                expected = test.expected_output
                assert expected is not None  # checked above; private bundle invariant
                if result.stdout != expected:
                    return JudgeResult(
                        verdict="WA",
                        metrics={
                            "elapsedMs": _elapsed_ms(started),
                            "testsPassed": index - 1,
                            "testCount": len(bundle.tests),
                        },
                    )
        except RunnerInfrastructureError as error:
            raise JudgeInfrastructureError("sandbox_unavailable") from error

        return JudgeResult(
            verdict="OK",
            metrics={
                "elapsedMs": _elapsed_ms(started),
                "testsPassed": len(bundle.tests),
                "testCount": len(bundle.tests),
            },
        )

    @staticmethod
    def _validate_bundle_identity(bundle: ProblemBundleV1, job: TrustedJudgeJob) -> None:
        if (
            bundle.problem_id != job.problem_id
            or bundle.version != job.problem_version
            or bundle.checksum != job.problem_checksum
        ):
            raise JudgeInfrastructureError("problem_bundle_identity_mismatch")
        if job.language_id not in {language.id for language in bundle.languages}:
            raise JudgeInfrastructureError("language_not_in_problem_version")


def _runtime_verdict(result: ExecutionResult) -> JudgeVerdict | None:
    if result.status == "TIME_LIMIT":
        return "TL"
    if result.status == "MEMORY_LIMIT":
        return "ML"
    if result.status == "OUTPUT_LIMIT":
        return "RE"
    if result.status == "RUNTIME_ERROR":
        return "RE"
    if result.status == "KILLED_UNKNOWN":
        raise JudgeInfrastructureError("sandbox_termination_unclassified")
    if result.status == "EXITED" and result.exit_code == 0:
        return None
    raise JudgeInfrastructureError("sandbox_returned_invalid_result")


def _bounded_diagnostics(stderr: bytes) -> str:
    bounded = stderr[:MAX_COMPILE_DIAGNOSTICS_BYTES]
    text = bounded.decode("utf-8", errors="replace")
    return text.encode("utf-8")[:MAX_COMPILE_DIAGNOSTICS_BYTES].decode("utf-8", errors="ignore")


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))
