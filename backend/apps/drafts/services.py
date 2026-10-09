"""Private draft storage; callers must supply an authorized workspace context."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .errors import DraftError, DraftRevisionConflict
from .models import Draft, DraftRevision
from .ports import WorkspaceAction, WorkspaceContext

MAX_DRAFT_BYTES = 32 * 1024
MAX_DRAFT_REVISION = 2**31 - 1
LANGUAGE_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")


@dataclass(frozen=True, slots=True)
class DraftSnapshot:
    run_id: UUID
    problem_id: UUID
    language_id: str
    source: str
    revision: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DraftHistoryEntry:
    revision: int
    source: str
    created_at: datetime


def _authorized_scope(context: WorkspaceContext, *, action: WorkspaceAction) -> tuple[UUID, UUID, UUID]:
    actor_id = getattr(context, "actor_id", None)
    run_id = getattr(context, "run_id", None)
    problem_id = getattr(context, "problem_id", None)
    allowed_actions = getattr(context, "allowed_actions", frozenset())
    if (
        not isinstance(actor_id, UUID)
        or not isinstance(run_id, UUID)
        or not isinstance(problem_id, UUID)
        or not isinstance(allowed_actions, (set, frozenset, tuple, list))
        or action not in allowed_actions
    ):
        raise DraftError("an authorized workspace context is required")
    return actor_id, run_id, problem_id


def _validate_language(language_id: str) -> str:
    if not isinstance(language_id, str) or not LANGUAGE_ID_RE.fullmatch(language_id):
        raise DraftError("language id is invalid")
    return language_id


def _validate_source(source: str) -> str:
    if not isinstance(source, str):
        raise DraftError("source must be text")
    try:
        source_bytes = source.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise DraftError("source is not valid UTF-8 text") from error
    if len(source_bytes) > MAX_DRAFT_BYTES:
        raise DraftError("source exceeds the configured draft limit")
    return source


def _snapshot(
    *, run_id: UUID, problem_id: UUID, language_id: str, source: str, revision: int, updated_at: datetime
) -> DraftSnapshot:
    return DraftSnapshot(run_id, problem_id, language_id, source, revision, updated_at)


def _from_record(record: Draft) -> DraftSnapshot:
    return _snapshot(
        run_id=record.run_id,
        problem_id=record.problem_id,
        language_id=record.language_id,
        source=record.source,
        revision=record.revision,
        updated_at=record.updated_at,
    )


class DraftService:
    @staticmethod
    def get_current(*, context: WorkspaceContext, language_id: str) -> DraftSnapshot | None:
        actor_id, run_id, problem_id = _authorized_scope(context, action="read_draft")
        language_id = _validate_language(language_id)
        record = Draft.objects.filter(
            actor_id=actor_id,
            run_id=run_id,
            problem_id=problem_id,
            language_id=language_id,
        ).first()
        if record is None:
            return None
        return _from_record(record)

    @staticmethod
    def save(
        *,
        context: WorkspaceContext,
        language_id: str,
        source: str,
        expected_revision: int,
    ) -> DraftSnapshot:
        actor_id, run_id, problem_id = _authorized_scope(context, action="write_draft")
        language_id = _validate_language(language_id)
        source = _validate_source(source)
        if (
            not isinstance(expected_revision, int)
            or isinstance(expected_revision, bool)
            or not 0 <= expected_revision <= MAX_DRAFT_REVISION
        ):
            raise DraftError("expected revision is invalid")

        now = timezone.now()
        try:
            with transaction.atomic():
                record = Draft.objects.filter(
                    actor_id=actor_id,
                    run_id=run_id,
                    problem_id=problem_id,
                    language_id=language_id,
                ).first()
                if record is None:
                    if expected_revision != 0:
                        raise DraftRevisionConflict(None)
                    record = Draft.objects.create(
                        actor_id=actor_id,
                        run_id=run_id,
                        problem_id=problem_id,
                        language_id=language_id,
                        source=source,
                        revision=1,
                        updated_at=now,
                    )
                    DraftRevision.objects.create(
                        draft=record,
                        revision=1,
                        source=source,
                        source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
                    )
                    return _from_record(record)

                if expected_revision != record.revision:
                    raise DraftRevisionConflict(_from_record(record))
                if record.source == source:
                    return _from_record(record)
                if expected_revision >= MAX_DRAFT_REVISION:
                    raise DraftError("draft revision limit has been reached")
                next_revision = expected_revision + 1
                updated = Draft.objects.filter(pk=record.pk, revision=expected_revision).update(
                    source=source,
                    revision=F("revision") + 1,
                    updated_at=now,
                )
                if updated != 1:
                    current = Draft.objects.filter(pk=record.pk).first()
                    if current is None:
                        raise DraftRevisionConflict(None)
                    raise DraftRevisionConflict(_from_record(current))
                DraftRevision.objects.create(
                    draft=record,
                    revision=next_revision,
                    source=source,
                    source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
                )
                record.source = source
                record.revision = next_revision
                record.updated_at = now
                return _from_record(record)
        except IntegrityError:
            current = Draft.objects.filter(
                actor_id=actor_id,
                run_id=run_id,
                problem_id=problem_id,
                language_id=language_id,
            ).first()
            if current is None:
                raise
            if current.revision == expected_revision:
                raise
            raise DraftRevisionConflict(_from_record(current)) from None

    @staticmethod
    def history(*, context: WorkspaceContext, language_id: str) -> list[DraftHistoryEntry]:
        actor_id, run_id, problem_id = _authorized_scope(context, action="read_history")
        language_id = _validate_language(language_id)
        draft = Draft.objects.filter(
            actor_id=actor_id,
            run_id=run_id,
            problem_id=problem_id,
            language_id=language_id,
        ).first()
        if draft is None:
            return []
        return [
            DraftHistoryEntry(item.revision, item.source, item.created_at)
            for item in DraftRevision.objects.filter(draft=draft).order_by("revision")
        ]
