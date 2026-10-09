"""Validate every v1 synthetic JSON example against its JSON Schema."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "contracts" / "mvp-v1"
SCHEMA_PATH = FIXTURES_DIR / "schemas.json"
EXPECTED_FIXTURES = {
    "bracket",
    "draft",
    "invite",
    "match",
    "problem",
    "public-match",
    "roster",
    "score-event",
    "submission",
}


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _validator(schema_document: dict[str, Any], fixture_name: str) -> Draft202012Validator:
    fixture_schema = {
        "$schema": schema_document["$schema"],
        "$defs": schema_document["$defs"],
        "$ref": f"#/$defs/{fixture_name}",
    }
    Draft202012Validator.check_schema(fixture_schema)
    return Draft202012Validator(fixture_schema, format_checker=FormatChecker())


def _errors(validator: Draft202012Validator, instance: Any) -> list[str]:
    problems = sorted(
        validator.iter_errors(instance),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    return [
        f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in problems
    ]


def main() -> int:
    try:
        schema_document = _load_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(schema_document)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"Invalid contract schema {SCHEMA_PATH.relative_to(ROOT)}: {error}", file=sys.stderr)
        return 1

    fixture_paths = {path.stem: path for path in FIXTURES_DIR.glob("*.json") if path != SCHEMA_PATH}
    fixture_names = set(fixture_paths)
    schema_names = set(schema_document.get("$defs", {})) & EXPECTED_FIXTURES
    errors: list[str] = []
    if fixture_names != EXPECTED_FIXTURES:
        errors.append(
            "fixture set mismatch: "
            f"missing={sorted(EXPECTED_FIXTURES - fixture_names)}, "
            f"unexpected={sorted(fixture_names - EXPECTED_FIXTURES)}"
        )
    if schema_names != EXPECTED_FIXTURES:
        errors.append(
            "schema set mismatch: "
            f"missing={sorted(EXPECTED_FIXTURES - schema_names)}"
        )

    validators: dict[str, Draft202012Validator] = {}
    documents: dict[str, Any] = {}
    for fixture_name in sorted(EXPECTED_FIXTURES & fixture_names & schema_names):
        fixture_path = fixture_paths[fixture_name]
        try:
            document = _load_json(fixture_path)
            validator = _validator(schema_document, fixture_name)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            errors.append(f"{fixture_path.name}: {error}")
            continue

        validators[fixture_name] = validator
        documents[fixture_name] = document
        errors.extend(
            f"{fixture_path.name}{message}"
            for message in _errors(validator, document)
        )

    for fixture_name, nested_path in (
        ("public-match", ("players", 0)),
        ("score-event", ("payload", "players", 0)),
    ):
        if fixture_name not in validators or fixture_name not in documents:
            continue
        probe = copy.deepcopy(documents[fixture_name])
        nested: Any = probe
        for part in nested_path:
            nested = nested[part]
        nested["source"] = "synthetic private source must be rejected"
        if not _errors(validators[fixture_name], probe):
            errors.append(f"{fixture_name}.json: schema accepted a private source field")

    if errors:
        print("Contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(EXPECTED_FIXTURES)} v1 fixtures; public schemas reject private source fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
