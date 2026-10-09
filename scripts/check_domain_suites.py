"""Run standalone domain suites without registering not-yet-integrated apps."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOMAIN_SUITES = (
    Path("backend/apps/competition/tests/test_bracket.py"),
    Path("backend/apps/competition/tests/test_clock.py"),
    Path("backend/apps/competition/tests/test_scoring.py"),
)


def main() -> int:
    found = [relative for relative in DOMAIN_SUITES if (ROOT / relative).is_file()]
    if not found:
        print("No standalone competition domain suites exist in this ref; nothing to run.")
        return 0

    for relative in found:
        print(f"Running standalone domain suite: {relative}", flush=True)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                str(relative.parent),
                "-p",
                relative.name,
                "-v",
            ],
            cwd=ROOT,
            check=False,
        )
        if completed.returncode:
            return completed.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
