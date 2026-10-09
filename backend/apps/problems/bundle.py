"""Internal ProblemBundleV1 schema and its public/private projections.

This normalized schema is owned by FirsterChuv. It is not an organizer archive
format; external package mapping belongs to the later P3-06 adapter.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID

from .archive import read_archive
from .compilers import COMPILERS
from .errors import ProblemBundleError

MAX_MANIFEST_BYTES = 1024 * 1024
MAX_STATEMENT_BYTES = 256 * 1024
MAX_TEMPLATE_BYTES = 32 * 1024
MAX_TEXT_EXAMPLE_BYTES = 64 * 1024
MAX_EXAMPLES = 32
MAX_ASSETS = 256
MAX_TESTS = 2048
MAX_BUNDLE_ID_BYTES = 64
ASSET_TYPES = {
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".webp": ("image/webp", b"RIFF"),
}


@dataclass(frozen=True, slots=True)
class ProblemExample:
    input: str
    output: str


@dataclass(frozen=True, slots=True)
class LanguageTemplate:
    id: str
    name: str
    template: str


@dataclass(frozen=True, slots=True)
class PublicAsset:
    asset_id: str
    media_type: str
    contents: bytes


@dataclass(frozen=True, slots=True)
class PrivateTestCase:
    input: bytes
    expected_output: bytes | None


@dataclass(frozen=True, slots=True)
class PrivateArtifact:
    role: str
    source_path: str
    language_id: str | None
    contents: bytes


@dataclass(frozen=True, slots=True)
class PublicProblemVersion:
    problem_id: UUID
    version: str
    label: str
    title: str
    statement_markdown: str
    asset_ids: tuple[str, ...]
    examples: tuple[ProblemExample, ...]
    time_limit_ms: int
    memory_limit_bytes: int
    languages: tuple[LanguageTemplate, ...]


@dataclass(frozen=True, slots=True)
class ProblemBundleV1:
    problem_id: UUID
    version: str
    checksum: str
    label: str
    title: str
    statement_markdown: str
    assets: tuple[PublicAsset, ...]
    examples: tuple[ProblemExample, ...]
    time_limit_ms: int
    memory_limit_bytes: int
    languages: tuple[LanguageTemplate, ...]
    tests: tuple[PrivateTestCase, ...]
    private_artifacts: tuple[PrivateArtifact, ...]

    @property
    def has_complete_judge_data(self) -> bool:
        checkers = [item for item in self.private_artifacts if item.role == "checker"]
        if len(checkers) > 1 or (checkers and checkers[0].language_id is None):
            return False
        has_checker = bool(checkers)
        return bool(self.tests and self.languages and (has_checker or all(test.expected_output is not None for test in self.tests)))

    def public_projection(self) -> PublicProblemVersion:
        return PublicProblemVersion(
            problem_id=self.problem_id,
            version=self.version,
            label=self.label,
            title=self.title,
            statement_markdown=self.statement_markdown,
            asset_ids=tuple(asset.asset_id for asset in self.assets),
            examples=self.examples,
            time_limit_ms=self.time_limit_ms,
            memory_limit_bytes=self.memory_limit_bytes,
            languages=self.languages,
        )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProblemBundleError("manifest contains a duplicate key")
        result[key] = value
    return result


def _object(
    value: Any,
    required: set[str],
    optional: set[str] | frozenset[str] = frozenset(),
) -> Mapping[str, Any]:
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - required - optional:
        raise ProblemBundleError("manifest object has an invalid shape")
    return value


def _optional_language_id(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProblemBundleError(f"manifest {field} must be a registered language ID or null")
    if value not in COMPILERS:
        raise ProblemBundleError(f"manifest {field} is not registered")
    return value


def _text(value: Any, field: str, *, max_bytes: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not allow_empty):
        raise ProblemBundleError(f"manifest {field} must be text")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ProblemBundleError(f"manifest {field} is not valid UTF-8 text") from error
    if len(encoded) > max_bytes or "\x00" in value:
        raise ProblemBundleError(f"manifest {field} exceeds its text limit")
    return value


def _positive_integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0 or value > 2**63 - 1:
        raise ProblemBundleError(f"manifest {field} must be a positive integer")
    return value


def _file(files: Mapping[str, bytes], path: Any, prefix: str, *, field: str) -> bytes:
    if not isinstance(path, str) or not path.startswith(prefix):
        raise ProblemBundleError(f"manifest {field} must reference a file in {prefix}")
    try:
        return files[path]
    except KeyError as error:
        raise ProblemBundleError(f"manifest {field} references a missing file") from error


def _validate_asset(path: str, media_type: Any, contents: bytes) -> str:
    if not path.startswith("public/assets/"):
        raise ProblemBundleError("public assets must be stored under public/assets/")
    suffix = path.rsplit("/", 1)[-1].lower()
    extension = "." + suffix.rsplit(".", 1)[-1] if "." in suffix else ""
    declared_type = ASSET_TYPES.get(extension)
    if declared_type is None or media_type != declared_type[0]:
        raise ProblemBundleError("public asset has an unsupported content type")
    signature = declared_type[1]
    if not contents.startswith(signature):
        raise ProblemBundleError("public asset content does not match its content type")
    if extension == ".webp" and (len(contents) < 12 or contents[8:12] != b"WEBP"):
        raise ProblemBundleError("public asset content does not match its content type")
    return declared_type[0]


def _checksum(manifest: Mapping[str, Any], files: Mapping[str, bytes]) -> str:
    canonical_manifest = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(b"FirsterChuv:ProblemBundleV1\x00")
    digest.update(len(canonical_manifest).to_bytes(8, "big"))
    digest.update(canonical_manifest)
    for path, contents in sorted(files.items()):
        if path == "manifest.json":
            continue
        encoded_path = path.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


def parse_problem_bundle(archive_bytes: bytes) -> ProblemBundleV1:
    """Parse FirsterChuv's internal normalized archive, never organizer input directly."""
    files = read_archive(archive_bytes)
    manifest_bytes = files.get("manifest.json")
    if manifest_bytes is None or len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise ProblemBundleError("archive must contain a bounded manifest.json")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProblemBundleError("manifest.json is not valid UTF-8 JSON") from error

    root = _object(manifest, {"schemaVersion", "problemId", "version", "public", "private"})
    if (
        not isinstance(root["schemaVersion"], int)
        or isinstance(root["schemaVersion"], bool)
        or root["schemaVersion"] != 1
    ):
        raise ProblemBundleError("only internal ProblemBundleV1 is supported")
    try:
        problem_id = UUID(root["problemId"])
    except (ValueError, TypeError, AttributeError) as error:
        raise ProblemBundleError("manifest problemId must be a UUID") from error
    version = root["version"]
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", version):
        raise ProblemBundleError("manifest version has an invalid format")

    public = _object(
        root["public"],
        {"label", "title", "statementMarkdown", "assets", "examples", "limits", "languages"},
    )
    label = _text(public["label"], "label", max_bytes=MAX_BUNDLE_ID_BYTES)
    title = _text(public["title"], "title", max_bytes=512)
    statement = _text(public["statementMarkdown"], "statementMarkdown", max_bytes=MAX_STATEMENT_BYTES)

    assets_data = public["assets"]
    if not isinstance(assets_data, list) or len(assets_data) > MAX_ASSETS:
        raise ProblemBundleError("manifest assets must be a bounded list")
    assets: list[PublicAsset] = []
    asset_ids: set[str] = set()
    for item in assets_data:
        asset = _object(item, {"assetId", "path", "mediaType"})
        asset_id = _text(asset["assetId"], "assetId", max_bytes=MAX_BUNDLE_ID_BYTES)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", asset_id) or asset_id in asset_ids:
            raise ProblemBundleError("manifest assetId is invalid or duplicated")
        contents = _file(files, asset["path"], "public/assets/", field="asset path")
        media_type = _validate_asset(asset["path"], asset["mediaType"], contents)
        assets.append(PublicAsset(asset_id, media_type, contents))
        asset_ids.add(asset_id)

    examples_data = public["examples"]
    if not isinstance(examples_data, list) or len(examples_data) > MAX_EXAMPLES:
        raise ProblemBundleError("manifest examples must be a bounded list")
    examples: list[ProblemExample] = []
    for item in examples_data:
        example = _object(item, {"input", "output"})
        examples.append(
            ProblemExample(
                _text(example["input"], "example input", max_bytes=MAX_TEXT_EXAMPLE_BYTES, allow_empty=True),
                _text(example["output"], "example output", max_bytes=MAX_TEXT_EXAMPLE_BYTES, allow_empty=True),
            )
        )

    limits = _object(public["limits"], {"timeLimitMs", "memoryLimitBytes"})
    time_limit_ms = _positive_integer(limits["timeLimitMs"], "timeLimitMs")
    memory_limit_bytes = _positive_integer(limits["memoryLimitBytes"], "memoryLimitBytes")

    languages_data = public["languages"]
    if not isinstance(languages_data, list) or not languages_data or len(languages_data) > 16:
        raise ProblemBundleError("manifest must declare at least one supported language")
    languages: list[LanguageTemplate] = []
    seen_languages: set[str] = set()
    for item in languages_data:
        language = _object(item, {"id"}, {"template"})
        language_id = language["id"]
        if not isinstance(language_id, str) or language_id in seen_languages:
            raise ProblemBundleError("manifest language id is invalid or duplicated")
        try:
            compiler = COMPILERS[language_id]
        except KeyError as error:
            raise ProblemBundleError("manifest declares an unsupported compiler") from error
        template = _text(
            language.get("template", compiler.default_template),
            "language template",
            max_bytes=MAX_TEMPLATE_BYTES,
            allow_empty=True,
        )
        languages.append(LanguageTemplate(compiler.language_id, compiler.display_name, template))
        seen_languages.add(language_id)

    tests: list[PrivateTestCase] = []
    artifacts: list[PrivateArtifact] = []
    private = root["private"]
    if private is not None:
        private_data = _object(
            private,
            {
                "tests",
                "checkerPath",
                "checkerLanguageId",
                "validatorPath",
                "validatorLanguageId",
                "referenceSolutionPath",
                "referenceSolutionLanguageId",
            },
        )
        tests_data = private_data["tests"]
        if not isinstance(tests_data, list) or len(tests_data) > MAX_TESTS:
            raise ProblemBundleError("manifest private tests must be a bounded list")
        for item in tests_data:
            test = _object(item, {"inputPath", "expectedOutputPath"})
            test_input = _file(files, test["inputPath"], "private/tests/", field="test input path")
            expected_path = test["expectedOutputPath"]
            expected_output = None if expected_path is None else _file(
                files, expected_path, "private/tests/", field="expected output path"
            )
            tests.append(PrivateTestCase(test_input, expected_output))
        for role, path_key, language_key, prefix in (
            ("checker", "checkerPath", "checkerLanguageId", "private/checkers/"),
            ("validator", "validatorPath", "validatorLanguageId", "private/validators/"),
            ("reference", "referenceSolutionPath", "referenceSolutionLanguageId", "private/references/"),
        ):
            language_id = _optional_language_id(private_data[language_key], language_key)
            path = private_data[path_key]
            if path is not None:
                contents = _file(files, path, prefix, field=path_key)
                if not contents:
                    raise ProblemBundleError(f"manifest {path_key} references an empty file")
                artifacts.append(PrivateArtifact(role, path, language_id, contents))
            elif language_id is not None:
                raise ProblemBundleError(f"manifest {language_key} requires an artifact path")

    return ProblemBundleV1(
        problem_id=problem_id,
        version=version,
        checksum=_checksum(root, files),
        label=label,
        title=title,
        statement_markdown=statement,
        assets=tuple(assets),
        examples=tuple(examples),
        time_limit_ms=time_limit_ms,
        memory_limit_bytes=memory_limit_bytes,
        languages=tuple(languages),
        tests=tuple(tests),
        private_artifacts=tuple(artifacts),
    )
