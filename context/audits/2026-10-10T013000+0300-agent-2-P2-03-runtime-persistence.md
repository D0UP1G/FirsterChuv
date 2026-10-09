# Agent 2 audit — P2-03 persisted run configuration/readiness

## Scope

Adds one persisted runtime slice on top of the bracket models: verified task and scoring snapshots, run configuration, durable participant ready signals, and manual/both-ready start transitions.

## Changes

- `MatchRun` stores start mode and immutable problem-version/checksum/runtime metadata.
- `MatchRunReady` records one readiness signal per frozen participant and run.
- `configure_match_run` requires an injected `ProblemCatalogV1`; it rejects non-ready/inconsistent catalog responses and pins bundle checksums. No default/mock production catalog is introduced.
- `mark_match_ready` persists participant readiness and starts only after both signals in `both_ready` mode; manual mode waits for the explicit server-time start transition.
- Optimistic revision updates acquire the SQLite write reservation before state reads and reject stale transitions.

## Verification

- Focused persisted runtime tests: 5 passed.
- Full backend suite: 242 passed, 2 skipped.
- Django system check and migration drift: clean.
- Compileall and `git diff --check`: clean.

## Boundary

HTTP endpoints, actor authentication/authorization, clock pause/resume/deadline worker, and CompetitionGatewayV1 remain separate follow-up slices. This PR depends on bracket persistence/API PR #50 and targets its feature branch.
