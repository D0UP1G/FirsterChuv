"""Anonymous public match snapshot endpoint."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.competition.match_api import MatchProjectionError, match_view_payload
from backend.apps.competition.models import Match
from backend.apps.common.throttles import RemoteAddressScopedRateThrottle
from backend.apps.events.access import DjangoPublicAccess, PublicAccessDenied
from backend.apps.events.public_payloads import PublicEventInputError
from backend.apps.events.services import read_snapshot


PUBLIC_MATCH_FIELDS = (
    "matchId",
    "runId",
    "status",
    "serverNow",
    "elapsedMs",
    "remainingMs",
    "allowedDurationMs",
    "leaderUserId",
    "winnerUserId",
    "lastEventId",
    "scoringRule",
    "players",
)
SCORING_RULE_FIELDS = (
    "order",
    "wrongAttemptPenaltySec",
    "penalizedVerdicts",
    "finalTiePolicy",
)
PLAYER_FIELDS = (
    "userId",
    "displayName",
    "solvedCount",
    "penaltyMs",
    "lastAcceptedElapsedMs",
    "tasks",
)
TASK_FIELDS = ("problemId", "label", "status", "attempts", "lastVerdict")


class PublicSnapshotUnavailable(APIException):
    status_code = 503
    default_detail = "Публичный снимок матча временно недоступен."
    default_code = "public_snapshot_unavailable"


class PublicSnapshotNotReady(APIException):
    status_code = 409
    default_detail = "Публичный снимок матча ещё не готов."
    default_code = "public_snapshot_not_ready"


class PublicMatchSnapshotView(APIView):
    """Read a public-safe snapshot without session auth or private DTO fields."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [RemoteAddressScopedRateThrottle]
    throttle_scope = "public_snapshot"

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    def get(self, request, match_id):
        with transaction.atomic():
            tournament_id = (
                Match.objects.filter(pk=match_id)
                .values_list("tournament_id", flat=True)
                .first()
            )
            if tournament_id is None:
                raise NotFound("Публичный матч не найден.")

            try:
                share_token = request.headers.get("X-Tournament-Share-Token")
                DjangoPublicAccess().assert_can_view(
                    tournament_id, share_token=share_token
                )
            except PublicAccessDenied as error:
                raise NotFound("Публичный матч не найден.") from error

            match = get_object_or_404(
                Match.objects.select_related("current_run", "winner__user"),
                pk=match_id,
            )
            try:
                internal = match_view_payload(
                    match,
                    actor=None,
                    now=timezone.now(),
                )
                snapshot = read_snapshot(match_id=match.pk)
            except MatchProjectionError as error:
                if error.code == "match_run_not_configured":
                    raise PublicSnapshotNotReady() from error
                raise PublicSnapshotUnavailable() from error
            except PublicEventInputError as error:
                raise PublicSnapshotUnavailable() from error

            if (
                snapshot is not None
                and snapshot["runId"] == internal["runId"]
                and snapshot["lastEventId"] == internal["lastEventId"]
            ):
                internal["leaderUserId"] = snapshot["payload"]["leaderUserId"]
                internal["players"] = snapshot["payload"]["players"]

            payload = {key: internal[key] for key in PUBLIC_MATCH_FIELDS if key != "players"}
            payload["scoringRule"] = self._scoring_rule(internal["scoringRule"])
            payload["players"] = [
                {
                    **{key: player[key] for key in PLAYER_FIELDS if key != "tasks"},
                    "tasks": [
                        {key: task[key] for key in TASK_FIELDS}
                        for task in player["tasks"]
                    ],
                }
                for player in internal["players"]
            ]

        return Response(payload)

    @staticmethod
    def _scoring_rule(value):
        if not isinstance(value, dict) or set(value) != set(SCORING_RULE_FIELDS):
            raise PublicSnapshotUnavailable()
        if (
            not isinstance(value["order"], list)
            or not value["order"]
            or any(not isinstance(item, str) for item in value["order"])
            or type(value["wrongAttemptPenaltySec"]) is not int
            or value["wrongAttemptPenaltySec"] < 0
            or not isinstance(value["penalizedVerdicts"], list)
            or any(not isinstance(item, str) for item in value["penalizedVerdicts"])
            or len(set(value["penalizedVerdicts"])) != len(value["penalizedVerdicts"])
            or any(
                item not in {"WA", "TL", "ML", "RE"}
                for item in value["penalizedVerdicts"]
            )
            or value["finalTiePolicy"] != "rematch"
        ):
            raise PublicSnapshotUnavailable()
        return {key: value[key] for key in SCORING_RULE_FIELDS}
