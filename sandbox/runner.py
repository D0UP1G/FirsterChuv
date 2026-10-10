"""Compatibility import for the runner packaged with the judge Django app."""

from backend.apps.judge.runner import (
    CPP20_COMPILER_ARGV,
    DEFAULT_RUN_TIME_LIMIT_MS,
    IMAGE,
    MAX_ARTIFACT_BYTES,
    MAX_DIAGNOSTICS_BYTES,
    MAX_INPUT_BYTES,
    MAX_MEMORY_LIMIT_BYTES,
    MAX_OUTPUT_BYTES,
    MAX_RUN_TIME_LIMIT_MS,
    MAX_SOURCE_BYTES,
    MIN_MEMORY_LIMIT_BYTES,
    DockerRunner,
    ExecutionResult,
    RunnerInfrastructureError,
    build_docker_create_args,
    encode_request,
    parse_response,
    _cleanup,
    _run_docker,
)
