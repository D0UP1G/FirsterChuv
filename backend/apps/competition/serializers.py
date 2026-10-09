"""Allowlisted bracket DTOs; private account and submission fields stay hidden."""

from rest_framework import serializers

from backend.apps.competition.models import Match, MatchSlot


class MatchSlotSerializer(serializers.ModelSerializer):
    index = serializers.IntegerField(source="slot_index")
    participant = serializers.SerializerMethodField()
    source_match_id = serializers.UUIDField(source="upstream_match_id", allow_null=True)

    class Meta:
        model = MatchSlot
        fields = ("index", "resolution", "participant", "source_match_id")

    def get_participant(self, slot):
        if slot.participant_id is None:
            return None
        participant = slot.participant
        return {
            "id": str(participant.pk),
            "userId": str(participant.user_id),
            "displayName": participant.user.display_name,
            "seed": participant.seed,
        }


class MatchBracketSerializer(serializers.ModelSerializer):
    key = serializers.CharField(source="bracket_key")
    round_index = serializers.IntegerField()
    next_match_id = serializers.UUIDField(allow_null=True)
    next_slot = serializers.IntegerField(allow_null=True)
    slots = MatchSlotSerializer(many=True, read_only=True)
    winner = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = (
            "id",
            "key",
            "round_index",
            "position",
            "kind",
            "status",
            "winner",
            "next_match_id",
            "next_slot",
            "slots",
        )

    def get_winner(self, match):
        if match.winner_id is None:
            return None
        participant = match.winner
        return {
            "id": str(participant.pk),
            "userId": str(participant.user_id),
            "displayName": participant.user.display_name,
            "seed": participant.seed,
        }


class TournamentBracketSerializer(serializers.Serializer):
    tournament_id = serializers.UUIDField()
    roster_frozen_at = serializers.DateTimeField()
    bracket_size = serializers.IntegerField(min_value=2)
    matches = MatchBracketSerializer(many=True)
