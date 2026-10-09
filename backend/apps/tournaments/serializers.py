"""Strict public serializers for tournament management."""

from collections.abc import Mapping

from rest_framework import serializers

from backend.apps.tournaments.models import Tournament, default_match_config


class StrictInputSerializer(serializers.Serializer):
    """Reject undeclared keys instead of silently ignoring mass assignment."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            allowed = {field.field_name for field in self._writable_fields}
            unknown = set(data) - allowed
            if unknown:
                raise serializers.ValidationError(
                    {str(key): "Unknown field." for key in sorted(unknown, key=str)}
                )
        return super().to_internal_value(data)


class ScoringRuleSerializer(StrictInputSerializer):
    order = serializers.ListField(
        child=serializers.ChoiceField(
            choices=("solved_desc", "penalty_asc", "last_accepted_asc")
        ),
        min_length=3,
        max_length=3,
        required=False,
    )
    wrong_attempt_penalty_sec = serializers.IntegerField(
        min_value=0,
        max_value=7200,
        required=False,
    )
    penalized_verdicts = serializers.ListField(
        child=serializers.ChoiceField(choices=("WA", "TL", "ML", "RE")),
        allow_empty=True,
        required=False,
    )
    final_tie_policy = serializers.ChoiceField(choices=("rematch",), required=False)

    def validate_order(self, value):
        expected = ["solved_desc", "penalty_asc", "last_accepted_asc"]
        if value != expected:
            raise serializers.ValidationError(
                "Порядок MVP: solved_desc, penalty_asc, last_accepted_asc."
            )
        return value

    def validate_penalized_verdicts(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Вердикты не должны повторяться.")
        return value


class TournamentSerializer(StrictInputSerializer, serializers.ModelSerializer):
    match_duration_sec = serializers.IntegerField(
        min_value=60,
        max_value=7200,
        required=False,
    )
    start_mode = serializers.ChoiceField(
        choices=("manual", "both_ready"),
        required=False,
    )
    scoring_rule = ScoringRuleSerializer(required=False)

    class Meta:
        model = Tournament
        fields = (
            "id",
            "slug",
            "title",
            "description",
            "starts_at",
            "ends_at",
            "format",
            "participant_limit",
            "visibility",
            "status",
            "active_participant_count",
            "roster_frozen_at",
            "created_by",
            "created_at",
            "updated_at",
            "match_duration_sec",
            "start_mode",
            "scoring_rule",
        )
        read_only_fields = (
            "id",
            "slug",
            "status",
            "active_participant_count",
            "roster_frozen_at",
            "created_by",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "title": {"max_length": 160},
            "description": {"max_length": 10000, "allow_blank": True},
            "participant_limit": {"min_value": 2},
        }

    def validate(self, attrs):
        instance = self.instance
        starts_at = attrs.get("starts_at", getattr(instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(instance, "ends_at", None))
        if starts_at is not None and ends_at is not None and ends_at <= starts_at:
            raise serializers.ValidationError(
                {"ends_at": "Дата окончания должна быть позже даты начала."}
            )

        limit = attrs.get("participant_limit", getattr(instance, "participant_limit", None))
        if instance is not None and limit is not None:
            if limit < instance.active_participant_count:
                raise serializers.ValidationError(
                    {"participant_limit": "Лимит не может быть меньше активного состава."}
                )

        if instance is not None:
            if instance.status in {
                Tournament.Status.RUNNING,
                Tournament.Status.COMPLETED,
                Tournament.Status.ARCHIVED,
            }:
                raise serializers.ValidationError(
                    {"detail": "Изменения запрещены для текущего статуса турнира."}
                )
            if instance.roster_frozen_at:
                frozen_fields = {
                    "starts_at",
                    "ends_at",
                    "format",
                    "participant_limit",
                    "match_duration_sec",
                    "start_mode",
                    "scoring_rule",
                }
                changed = frozen_fields.intersection(attrs)
                if changed:
                    raise serializers.ValidationError(
                        {
                            field: "Поле нельзя изменить после заморозки состава."
                            for field in sorted(changed)
                        }
                    )
        return attrs

    def _merged_match_config(self, validated_data, *, instance=None):
        config = (
            dict(instance.default_match_config)
            if instance is not None
            else default_match_config()
        )
        duration = validated_data.pop("match_duration_sec", None)
        start_mode = validated_data.pop("start_mode", None)
        scoring_rule = validated_data.pop("scoring_rule", None)
        if duration is not None:
            config["match_duration_sec"] = duration
        if start_mode is not None:
            config["start_mode"] = start_mode
        if scoring_rule is not None:
            merged_rule = dict(config["scoring_rule"])
            merged_rule.update(scoring_rule)
            config["scoring_rule"] = merged_rule
        return config

    def create(self, validated_data):
        validated_data["default_match_config"] = self._merged_match_config(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance.default_match_config = self._merged_match_config(
            validated_data,
            instance=instance,
        )
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        config = instance.default_match_config
        data.update(
            {
                "match_duration_sec": config["match_duration_sec"],
                "start_mode": config["start_mode"],
                "scoring_rule": config["scoring_rule"],
            }
        )
        return data
