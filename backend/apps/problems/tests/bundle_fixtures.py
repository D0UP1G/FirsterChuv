import json
import zipfile
from io import BytesIO
from uuid import UUID

PROBLEM_ID = UUID("00000000-0000-0000-0000-000000000040")
PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-payload"


def normalized_manifest(*, with_private: bool = True) -> dict:
    return {
        "schemaVersion": 1,
        "problemId": str(PROBLEM_ID),
        "version": "synthetic-v1",
        "public": {
            "label": "A",
            "title": "Сумма — синтетическая задача",
            "statementMarkdown": "Найдите сумму $a+b$.\n",
            "assets": [{"assetId": "figure", "path": "public/assets/figure.png", "mediaType": "image/png"}],
            "examples": [{"input": "2 3\n", "output": "5\n"}],
            "limits": {"timeLimitMs": 2000, "memoryLimitBytes": 536870912},
            "languages": [{"id": "cpp20"}],
        },
        "private": (
            {
                "tests": [
                    {"inputPath": "private/tests/001.in", "expectedOutputPath": "private/tests/001.out"},
                ],
                "checkerPath": None,
                "checkerLanguageId": None,
                "validatorPath": None,
                "validatorLanguageId": None,
                "referenceSolutionPath": "private/references/reference.cpp",
                "referenceSolutionLanguageId": "cpp20",
            }
            if with_private
            else None
        ),
    }


def make_bundle_archive(
    *,
    manifest: dict | None = None,
    files: dict[str, bytes] | None = None,
    manifest_bytes: bytes | None = None,
    order: tuple[str, ...] | None = None,
) -> bytes:
    selected_manifest = normalized_manifest() if manifest is None else manifest
    selected_files = {"public/assets/figure.png": PNG_BYTES}
    if selected_manifest.get("private") is not None:
        selected_files.update(
            {
                "private/tests/001.in": b"1 2\n",
                "private/tests/001.out": b"3\n",
                "private/references/reference.cpp": b"int main() { return 0; }\n",
            }
        )
    if files:
        selected_files.update(files)
    members = {"manifest.json": json.dumps(selected_manifest, ensure_ascii=False).encode("utf-8"), **selected_files}
    if manifest_bytes is not None:
        members["manifest.json"] = manifest_bytes
    selected_order = order or tuple(members)
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in selected_order:
            archive.writestr(name, members[name])
    return stream.getvalue()
