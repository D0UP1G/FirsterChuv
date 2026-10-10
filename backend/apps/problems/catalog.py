"""ProblemCatalogV1 implementation over the app's immutable SQLite models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from django.db.models import Prefetch

from .bundle import LanguageTemplate, ProblemBundleV1, ProblemExample, PublicProblemVersion
from .compilers import COMPILERS, CompilerSpec
from .errors import ProblemNotReady
from .models import ProblemPrivateArtifact, ProblemPrivateData, ProblemPublicAsset, ProblemVersion
from .storage import _compiler_registry_verified, load_stored_bundle


class ProblemCatalogV1(Protocol):
    def describe_ready(self, problem_ids: Sequence[UUID]) -> tuple[PublicProblemVersion, ...]: ...

    def load_bundle(self, problem_id: UUID, version: str) -> ProblemBundleV1: ...


class DjangoProblemCatalog:
    def __init__(self, *, compiler_registry: dict[str, CompilerSpec] = COMPILERS) -> None:
        self._compiler_registry = compiler_registry

    def describe_ready(self, problem_ids: Sequence[UUID]) -> tuple[PublicProblemVersion, ...]:
        if len(set(problem_ids)) != len(problem_ids):
            raise ValueError("problem_ids must not contain duplicates")
        if not problem_ids:
            return ()
        versions = (
            ProblemVersion.objects.filter(
                problem_id__in=problem_ids,
                readiness=ProblemVersion.Readiness.READY,
                is_active=True,
            )
            .select_related("public_data", "private_data")
            .prefetch_related(
                Prefetch(
                    "public_data__assets",
                    queryset=ProblemPublicAsset.objects.only("id", "public_data_id", "asset_id").order_by("asset_id"),
                ),
                Prefetch(
                    "private_data__artifacts",
                    queryset=ProblemPrivateArtifact.objects.only("id", "private_data_id", "role", "language_id"),
                ),
            )
        )
        by_problem_id = {item.problem_id: item for item in versions}
        if len(by_problem_id) != len(problem_ids):
            raise ProblemNotReady("one or more problem versions are unknown or not ready")
        if any(not self._record_compilers_verified(item) for item in by_problem_id.values()):
            raise ProblemNotReady("one or more problem versions have no verified compiler")
        return tuple(self._public_projection(by_problem_id[problem_id]) for problem_id in problem_ids)

    def describe_pinned(self, problem_id: UUID, version: str, checksum: str) -> PublicProblemVersion:
        """Public projection of the exact version frozen into a run, never the latest active one.

        Statement display needs no compiler: the run was configured only from ready, verified
        versions. The stored checksum must equal the frozen one so a replaced bundle is never shown.
        """
        record = (
            ProblemVersion.objects.filter(
                problem_id=problem_id,
                version=version,
                checksum=checksum,
                readiness=ProblemVersion.Readiness.READY,
            )
            .select_related("public_data")
            .prefetch_related(
                Prefetch(
                    "public_data__assets",
                    queryset=ProblemPublicAsset.objects.only("id", "public_data_id", "asset_id").order_by("asset_id"),
                )
            )
            .first()
        )
        if record is None:
            raise ProblemNotReady("pinned problem version is unknown, changed or not ready")
        return self._public_projection(record)

    def _record_compilers_verified(self, record: ProblemVersion) -> bool:
        language_ids = {item["id"] for item in record.public_data.languages}
        try:
            artifacts = record.private_data.artifacts.all()
        except ProblemPrivateData.DoesNotExist:
            artifacts = ()
        checker = next(
            (item for item in artifacts if item.role == ProblemPrivateArtifact.Role.CHECKER),
            None,
        )
        if checker is not None:
            if checker.language_id is None:
                return False
            language_ids.add(checker.language_id)
        return bool(language_ids) and all(
            (compiler := self._compiler_registry.get(language_id)) is not None and compiler.verified
            for language_id in language_ids
        )

    @staticmethod
    def _public_projection(record: ProblemVersion) -> PublicProblemVersion:
        public_data = record.public_data
        return PublicProblemVersion(
            problem_id=record.problem_id,
            version=record.version,
            label=public_data.label,
            title=public_data.title,
            statement_markdown=public_data.statement_markdown,
            asset_ids=tuple(asset.asset_id for asset in public_data.assets.all()),
            examples=tuple(ProblemExample(item["input"], item["output"]) for item in public_data.examples),
            time_limit_ms=public_data.time_limit_ms,
            memory_limit_bytes=public_data.memory_limit_bytes,
            languages=tuple(
                LanguageTemplate(item["id"], item["name"], item["template"])
                for item in public_data.languages
            ),
        )

    def load_bundle(self, problem_id: UUID, version: str) -> ProblemBundleV1:
        record = (
            ProblemVersion.objects.filter(
                problem_id=problem_id,
                version=version,
                readiness=ProblemVersion.Readiness.READY,
            )
            .select_related("public_data", "private_data")
            .first()
        )
        if record is None:
            raise ProblemNotReady("problem version is unknown or not ready")
        bundle = load_stored_bundle(record)
        if not bundle.has_complete_judge_data or not _compiler_registry_verified(bundle, self._compiler_registry):
            raise ProblemNotReady("problem version no longer has a verified execution path")
        return bundle
