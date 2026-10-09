"""Transactional, immutable persistence for normalized problem versions."""

from __future__ import annotations

from collections.abc import Mapping

from django.db import IntegrityError, transaction

from .bundle import (
    LanguageTemplate,
    PrivateArtifact,
    PrivateTestCase,
    ProblemBundleV1,
    ProblemExample,
    PublicAsset,
)
from .compilers import COMPILERS, CompilerSpec
from .errors import ProblemVersionConflict
from .models import ProblemPrivateArtifact, ProblemPrivateData, ProblemPublicAsset, ProblemPublicData, ProblemTestCase, ProblemVersion


def _compiler_registry_verified(bundle: ProblemBundleV1, registry: Mapping[str, CompilerSpec]) -> bool:
    language_ids = {language.id for language in bundle.languages}
    language_ids.update(
        artifact.language_id
        for artifact in bundle.private_artifacts
        if artifact.role == "checker" and artifact.language_id is not None
    )
    return bool(bundle.languages) and all(
        (compiler := registry.get(language_id)) is not None and compiler.verified
        for language_id in language_ids
    )


def store_bundle(
    bundle: ProblemBundleV1,
    *,
    compiler_registry: Mapping[str, CompilerSpec] = COMPILERS,
) -> ProblemVersion:
    """Insert a new version once; identical retries are idempotent."""
    ready = bundle.has_complete_judge_data and _compiler_registry_verified(bundle, compiler_registry)
    try:
        with transaction.atomic():
            existing = ProblemVersion.objects.filter(problem_id=bundle.problem_id, version=bundle.version).first()
            if existing is not None:
                if existing.checksum != bundle.checksum:
                    raise ProblemVersionConflict("problem version already exists with different content")
                if ready and existing.readiness == ProblemVersion.Readiness.NOT_READY:
                    has_active = ProblemVersion.objects.filter(problem_id=bundle.problem_id, is_active=True).exists()
                    updates = {"readiness": ProblemVersion.Readiness.READY}
                    if not has_active:
                        updates["is_active"] = True
                    ProblemVersion.objects.filter(
                        pk=existing.pk,
                        readiness=ProblemVersion.Readiness.NOT_READY,
                    ).update(**updates)
                    existing.refresh_from_db()
                return existing

            version = ProblemVersion.objects.create(
                problem_id=bundle.problem_id,
                version=bundle.version,
                checksum=bundle.checksum,
                readiness=ProblemVersion.Readiness.READY if ready else ProblemVersion.Readiness.NOT_READY,
                is_active=ready and not ProblemVersion.objects.filter(problem_id=bundle.problem_id, is_active=True).exists(),
            )
            public_data = ProblemPublicData.objects.create(
                version=version,
                label=bundle.label,
                title=bundle.title,
                statement_markdown=bundle.statement_markdown,
                examples=[{"input": item.input, "output": item.output} for item in bundle.examples],
                time_limit_ms=bundle.time_limit_ms,
                memory_limit_bytes=bundle.memory_limit_bytes,
                languages=[{"id": item.id, "name": item.name, "template": item.template} for item in bundle.languages],
            )
            ProblemPublicAsset.objects.bulk_create(
                [
                    ProblemPublicAsset(
                        public_data=public_data,
                        asset_id=asset.asset_id,
                        media_type=asset.media_type,
                        contents=asset.contents,
                    )
                    for asset in bundle.assets
                ]
            )

            if bundle.tests or bundle.private_artifacts:
                private_data = ProblemPrivateData.objects.create(version=version)
                ProblemTestCase.objects.bulk_create(
                    [
                        ProblemTestCase(
                            private_data=private_data,
                            ordinal=index,
                            input_data=test.input,
                            expected_output=test.expected_output,
                        )
                        for index, test in enumerate(bundle.tests)
                    ]
                )
                ProblemPrivateArtifact.objects.bulk_create(
                    [
                        ProblemPrivateArtifact(
                            private_data=private_data,
                            role=artifact.role,
                            source_path=artifact.source_path,
                            language_id=artifact.language_id,
                            contents=artifact.contents,
                        )
                        for artifact in bundle.private_artifacts
                    ]
                )
            return version
    except IntegrityError as error:
        # Concurrent import of the same key is resolved by re-reading the winning immutable row.
        existing = ProblemVersion.objects.filter(problem_id=bundle.problem_id, version=bundle.version).first()
        if existing is not None and existing.checksum == bundle.checksum:
            return existing
        if existing is not None:
            raise ProblemVersionConflict("problem version already exists with different content") from error
        raise


def load_stored_bundle(version: ProblemVersion) -> ProblemBundleV1:
    public_data = version.public_data
    try:
        private_data = version.private_data
    except ProblemPrivateData.DoesNotExist:
        private_data = None

    assets = tuple(
        PublicAsset(item.asset_id, item.media_type, bytes(item.contents))
        for item in public_data.assets.all().order_by("asset_id")
    )
    examples = tuple(ProblemExample(item["input"], item["output"]) for item in public_data.examples)
    languages = tuple(LanguageTemplate(item["id"], item["name"], item["template"]) for item in public_data.languages)
    tests = () if private_data is None else tuple(
        PrivateTestCase(bytes(item.input_data), None if item.expected_output is None else bytes(item.expected_output))
        for item in private_data.tests.all()
    )
    artifacts = () if private_data is None else tuple(
        PrivateArtifact(item.role, item.source_path, item.language_id, bytes(item.contents))
        for item in private_data.artifacts.all().order_by("role")
    )
    return ProblemBundleV1(
        problem_id=version.problem_id,
        version=version.version,
        checksum=version.checksum,
        label=public_data.label,
        title=public_data.title,
        statement_markdown=public_data.statement_markdown,
        assets=assets,
        examples=examples,
        time_limit_ms=public_data.time_limit_ms,
        memory_limit_bytes=public_data.memory_limit_bytes,
        languages=languages,
        tests=tests,
        private_artifacts=artifacts,
    )
