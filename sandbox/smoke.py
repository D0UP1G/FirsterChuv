#!/usr/bin/env python3
"""Execute checked-in smoke cases in disposable, bounded Docker containers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from runner import DockerRunner, ExecutionResult, RunnerInfrastructureError

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"
EXPECTED_VERDICTS = {
    "ok": "OK",
    "wa": "WA",
    "timeout": "TIME_LIMIT",
    "output-limit": "OUTPUT_LIMIT",
    "protocol-write": "BLOCKED",
}


def evaluate(name: str, result: ExecutionResult, expected: bytes) -> str:
    if result.status == "INFRASTRUCTURE_ERROR":
        raise RunnerInfrastructureError("sandbox returned an infrastructure failure")
    target = EXPECTED_VERDICTS[name]
    if target == "BLOCKED":
        if result.status != "EXITED" or result.exit_code != 0 or result.stdout != b"blocked\n":
            raise RuntimeError(f"{name}: supervisor protocol stream was not protected")
        return target
    if target in {"OK", "WA"}:
        if result.status != "EXITED" or result.exit_code != 0:
            raise RuntimeError(f"{name}: expected a completed process, got {result.status}")
        actual = "OK" if result.stdout == expected else "WA"
        if actual != target:
            raise RuntimeError(f"{name}: expected {target}, got {actual}")
        return actual
    if result.status != target:
        raise RuntimeError(f"{name}: expected {target}, got {result.status}")
    return target


def run_case(runner: DockerRunner, name: str) -> str:
    source = (FIXTURES / f"{name}.cpp").read_bytes()
    stdin = (FIXTURES / "input.txt").read_bytes() if name in {"ok", "wa"} else b""
    expected = (FIXTURES / "expected.txt").read_bytes() if name in {"ok", "wa"} else b""
    return evaluate(name, runner.execute(source, stdin), expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*EXPECTED_VERDICTS, "all"], default="all")
    args = parser.parse_args()
    names = list(EXPECTED_VERDICTS) if args.case == "all" else [args.case]
    runner = DockerRunner()
    try:
        for name in names:
            verdict = run_case(runner, name)
            print(f"{name}: {verdict}")
    except (RunnerInfrastructureError, RuntimeError, OSError) as error:
        print(f"NOT_VERIFIED: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
