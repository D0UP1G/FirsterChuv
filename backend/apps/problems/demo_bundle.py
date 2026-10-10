"""Synthetic normalized bundle for local M0 wiring; not an organizer package."""

from __future__ import annotations

import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

DEMO_PROBLEM_ID = "00000000-0000-0000-0000-000000000101"
DEMO_VERSION = "m0-demo-v1"
DEMO_ASSET_ID = "00000000-0000-0000-0000-000000000111"

# A valid one-pixel PNG. It exercises the public asset path without bundling a
# copyrighted task image or treating this synthetic data as official content.
_DEMO_IMAGE = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000b49444154789c6360000200000500017a5eab3f0000000049454e44ae426082"
)


def build_demo_problem_archive() -> bytes:
    """Build deterministic internal ProblemBundleV1 data for the M0 demo."""
    manifest = {
        "schemaVersion": 1,
        "problemId": DEMO_PROBLEM_ID,
        "version": DEMO_VERSION,
        "public": {
            "label": "A",
            "title": "Сумма двух чисел · synthetic M0",
            "statementMarkdown": (
                "# Сумма двух чисел\n\n"
                "Даны целые числа $a$ и $b$. Выведите их сумму $a+b$.\n\n"
                f"![Схематичное изображение задачи](/api/v1/problem-assets/{DEMO_ASSET_ID})\n\n"
                "| Вход | Выход |\n|---|---|\n| `2 3` | `5` |\n\n"
                "Ограничения: $-10^9 \\le a,b \\le 10^9$.\n"
            ),
            "assets": [
                {
                    "assetId": DEMO_ASSET_ID,
                    "path": "public/assets/demo.png",
                    "mediaType": "image/png",
                }
            ],
            "examples": [
                {"input": "2 3\n", "output": "5\n"},
                {"input": "10 -4\n", "output": "6\n"},
            ],
            "limits": {"timeLimitMs": 2000, "memoryLimitBytes": 536870912},
            "languages": [{"id": "cpp20"}],
        },
        "private": {
            "tests": [
                {"inputPath": "private/tests/001.in", "expectedOutputPath": "private/tests/001.out"},
                {"inputPath": "private/tests/002.in", "expectedOutputPath": "private/tests/002.out"},
            ],
            "checkerPath": None,
            "checkerLanguageId": None,
            "validatorPath": None,
            "validatorLanguageId": None,
            "referenceSolutionPath": "private/references/reference.cpp",
            "referenceSolutionLanguageId": "cpp20",
        },
    }
    files = {
        "manifest.json": json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
        "public/assets/demo.png": _DEMO_IMAGE,
        "private/tests/001.in": b"2 3\n",
        "private/tests/001.out": b"5\n",
        "private/tests/002.in": b"10 -4\n",
        "private/tests/002.out": b"6\n",
        "private/references/reference.cpp": (
            b"#include <iostream>\nint main() { long long a, b; "
            b"if (std::cin >> a >> b) std::cout << a + b << '\\n'; }\n"
        ),
    }
    stream = BytesIO()
    with ZipFile(stream, mode="w", compression=ZIP_DEFLATED) as archive:
        for name, contents in sorted(files.items()):
            archive.writestr(name, contents)
    return stream.getvalue()
