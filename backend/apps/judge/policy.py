"""Server-owned execution limits for one task test case."""

from dataclasses import dataclass

from backend.apps.common.contracts import JudgeInfrastructureError

MIN_TASK_MEMORY_BYTES = 32 * 1024 * 1024
MAX_TASK_MEMORY_BYTES = 512 * 1024 * 1024
MAX_TASK_TIME_LIMIT_MS = 120_000
MAX_JOB_WALL_TIME_MS = 300_000


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    time_limit_ms: int
    memory_limit_bytes: int

    @classmethod
    def from_task(cls, *, time_limit_ms: int, memory_limit_bytes: int) -> "ExecutionLimits":
        if (
            not isinstance(time_limit_ms, int)
            or isinstance(time_limit_ms, bool)
            or not 1 <= time_limit_ms <= MAX_TASK_TIME_LIMIT_MS
        ):
            raise JudgeInfrastructureError("task_time_limit_unsupported")
        if (
            not isinstance(memory_limit_bytes, int)
            or isinstance(memory_limit_bytes, bool)
            or not MIN_TASK_MEMORY_BYTES <= memory_limit_bytes <= MAX_TASK_MEMORY_BYTES
        ):
            raise JudgeInfrastructureError("task_memory_limit_unsupported")
        return cls(time_limit_ms, memory_limit_bytes)
