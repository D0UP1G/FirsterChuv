# Persisted competition ports

`gateway.DjangoCompetitionGateway` implements the common `CompetitionGatewayV1` and `RunProblemSnapshotProvider` boundaries over the persisted match/run, tournament-membership and accepted-result models. Factories for runtime wiring are `backend.apps.competition.gateway.get_competition_gateway` and `backend.apps.competition.gateway.get_run_problem_snapshot_provider`; this module does not install itself into A3-owned worker, queue or settings factories.

Submission access requires an active participant account, active tournament membership, inclusion in the requested run's frozen `participant_user_ids`, the current match run, a problem in that run's immutable `problem_versions`, RUNNING status and a server timestamp before the deadline. Elapsed time and scoring version come from that run. A replacement in mutable bracket slots cannot acquire access to an old run.

Workspace access is capability based. Metadata, statement, draft and history purposes return only their matching actions. Participant statements remain unavailable until `started_at`; draft/history scopes are bound to the participant and frozen run. Admins can read metadata/statements but never receive draft, source, submission or history actions. Closed/private identifiers use the same not-found response.

`resolve(run_id, problem_id)` reads version/checksum only from that run's persisted assignment, including a superseded run; it never queries the currently active catalog. Malformed assignments fail with typed `RunProblemSnapshotUnavailable` for trusted runtime consumers; workspace/submission access maps damaged snapshots to API 503. Worker and HTTP owners must wire the real provider through their own factory settings and preserve the typed permission/conflict failures in their API mapping. Until that CONNECT is merged, existing production factories remain fail-closed.

Focused tests: `DJANGO_DEBUG=true DJANGO_REQUIRE_SECRET_KEY=0 uv run --locked python manage.py test backend.apps.competition.tests.test_gateway`.
