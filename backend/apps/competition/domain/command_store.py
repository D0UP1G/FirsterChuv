"""Pure idempotency receipts for persisted administrator command effects.

This immutable core is not a durable store. A persistence adapter must look up
the receipt before replanning and save the plan/effect/receipt atomically.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.apps.competition.domain.admin_actions import (
    AdminAction,
    AdminActionPlan,
    AdminCommand,
)


class AdminCommandStoreError(ValueError):
    """Raised when a command key or stored plan conflicts with its intent."""


_PARAMETER_KEYS: dict[AdminAction, tuple[str, ...]] = {
    AdminAction.PAUSE: (),
    AdminAction.RESUME: (),
    AdminAction.EXTEND: ("extension_seconds",),
    AdminAction.TECHNICAL_RESULT: ("winner_user_id",),
    AdminAction.REMATCH: (),
    AdminAction.REPLACE_PARTICIPANT: ("replaced_user_id", "replacement_user_id"),
}


def _uuid(value: UUID | str, *, field_name: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(value)
    except (TypeError, ValueError, AttributeError) as error:
        raise AdminCommandStoreError(f"{field_name} must be a UUID") from error


def _normalize_parameter(value: object) -> str | int | bool | None:
    if isinstance(value, UUID):
        return str(value)
    if value is None or type(value) in (str, int, bool):
        return value
    raise AdminCommandStoreError("command parameters must be scalar values")


def _same_parameters(
    left: tuple[tuple[str, str | int | bool | None], ...],
    right: tuple[tuple[str, str | int | bool | None], ...],
) -> bool:
    return len(left) == len(right) and all(
        left_name == right_name
        and type(left_value) is type(right_value)
        and left_value == right_value
        for (left_name, left_value), (right_name, right_value) in zip(left, right)
    )


@dataclass(frozen=True, slots=True)
class AdminCommandIntent:
    """Normalized trusted request identity used for idempotency comparison."""

    match_id: UUID | str
    command: AdminCommand
    action: AdminAction | str
    parameters: tuple[tuple[str, str | int | bool | UUID | None], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "match_id", _uuid(self.match_id, field_name="match_id"))
        if not isinstance(self.command, AdminCommand):
            raise AdminCommandStoreError("command must be a trusted AdminCommand")
        try:
            action = AdminAction(self.action)
        except (TypeError, ValueError) as error:
            raise AdminCommandStoreError("unknown administrator action") from error
        object.__setattr__(self, "action", action)

        if not isinstance(self.parameters, tuple):
            raise AdminCommandStoreError("parameters must be an immutable tuple")
        normalized: list[tuple[str, str | int | bool | None]] = []
        for parameter in self.parameters:
            if not isinstance(parameter, tuple) or len(parameter) != 2:
                raise AdminCommandStoreError("each command parameter must be a key/value pair")
            name, value = parameter
            if not isinstance(name, str) or not name.strip():
                raise AdminCommandStoreError("parameter names must be non-empty strings")
            normalized.append((name, _normalize_parameter(value)))
        normalized.sort(key=lambda item: item[0])
        names = tuple(name for name, _ in normalized)
        if len(set(names)) != len(names):
            raise AdminCommandStoreError("parameter names must be unique")
        if names != tuple(sorted(_PARAMETER_KEYS[action])):
            raise AdminCommandStoreError("parameters do not match the administrator action")
        object.__setattr__(self, "parameters", tuple(normalized))

    @property
    def key(self) -> tuple[UUID, str]:
        """Idempotency key scope: one command ID per match."""
        return self.match_id, self.command.command_id


def _same_intent(left: AdminCommandIntent, right: AdminCommandIntent) -> bool:
    return (
        left.key == right.key
        and left.action is right.action
        and left.command.actor.user_id == right.command.actor.user_id
        and left.command.reason == right.command.reason
        and _same_parameters(left.parameters, right.parameters)
    )


@dataclass(frozen=True, slots=True)
class AdminCommandReceipt:
    """Original plan recorded for one normalized administrator request."""

    intent: AdminCommandIntent
    plan: AdminActionPlan


@dataclass(frozen=True, slots=True)
class AdminCommandStore:
    """Immutable in-memory receipt set; the production adapter persists it."""

    receipts: tuple[AdminCommandReceipt, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.receipts, tuple):
            raise AdminCommandStoreError("receipts must be an immutable tuple")
        keys: set[tuple[UUID, str]] = set()
        for receipt in self.receipts:
            if not isinstance(receipt, AdminCommandReceipt):
                raise AdminCommandStoreError("receipts must contain AdminCommandReceipt values")
            if not isinstance(receipt.intent, AdminCommandIntent):
                raise AdminCommandStoreError("receipt intent must be an AdminCommandIntent")
            _validate_plan(receipt.intent, receipt.plan)
            if receipt.intent.key in keys:
                raise AdminCommandStoreError("command receipt keys must be unique")
            keys.add(receipt.intent.key)


def _plan_parameters(plan: AdminActionPlan) -> tuple[tuple[str, str | int | bool | None], ...]:
    try:
        action = AdminAction(plan.action)
    except (TypeError, ValueError) as error:
        raise AdminCommandStoreError("plan contains an unknown administrator action") from error
    values: dict[str, object] = {
        AdminAction.PAUSE: {},
        AdminAction.RESUME: {},
        AdminAction.EXTEND: {"extension_seconds": plan.extension_seconds},
        AdminAction.TECHNICAL_RESULT: {"winner_user_id": plan.winner_user_id},
        AdminAction.REMATCH: {},
        AdminAction.REPLACE_PARTICIPANT: {
            "replaced_user_id": plan.replaced_user_id,
            "replacement_user_id": plan.replacement_user_id,
        },
    }[action]
    return tuple(
        (name, _normalize_parameter(value))
        for name, value in sorted(values.items())
    )


def _validate_plan(intent: AdminCommandIntent, plan: AdminActionPlan) -> None:
    if not isinstance(plan, AdminActionPlan):
        raise AdminCommandStoreError("plan must be an AdminActionPlan")
    command = intent.command
    try:
        action = AdminAction(plan.action)
    except (TypeError, ValueError) as error:
        raise AdminCommandStoreError("plan contains an unknown administrator action") from error
    if (
        plan.match_id != intent.match_id
        or plan.command_id != command.command_id
        or plan.actor_user_id != command.actor.user_id
        or action is not intent.action
        or plan.reason != command.reason
        or not _same_parameters(_plan_parameters(plan), intent.parameters)
    ):
        raise AdminCommandStoreError("action plan does not match command intent")


def lookup_command(
    store: AdminCommandStore,
    intent: AdminCommandIntent,
) -> AdminActionPlan | None:
    """Return the original plan on exact retry, before state is re-evaluated."""
    if not isinstance(store, AdminCommandStore):
        raise AdminCommandStoreError("store must be an AdminCommandStore")
    if not isinstance(intent, AdminCommandIntent):
        raise AdminCommandStoreError("intent must be an AdminCommandIntent")
    for receipt in store.receipts:
        if receipt.intent.key == intent.key:
            if not _same_intent(receipt.intent, intent):
                raise AdminCommandStoreError("idempotency key was reused with different intent")
            return receipt.plan
    return None


def record_command(
    store: AdminCommandStore,
    intent: AdminCommandIntent,
    plan: AdminActionPlan,
) -> AdminCommandStore:
    """Record a first command result; identical persistence retries are no-ops."""
    if not isinstance(store, AdminCommandStore):
        raise AdminCommandStoreError("store must be an AdminCommandStore")
    if not isinstance(intent, AdminCommandIntent):
        raise AdminCommandStoreError("intent must be an AdminCommandIntent")
    _validate_plan(intent, plan)
    previous = next(
        (receipt for receipt in store.receipts if receipt.intent.key == intent.key),
        None,
    )
    if previous is not None:
        if not _same_intent(previous.intent, intent):
            raise AdminCommandStoreError("idempotency key was reused with different intent")
        if previous.plan != plan:
            raise AdminCommandStoreError("command already has a different recorded plan")
        return store
    receipt = AdminCommandReceipt(intent=intent, plan=plan)
    return AdminCommandStore(receipts=(*store.receipts, receipt))
