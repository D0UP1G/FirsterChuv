"""Strict HTTP input for the participant-owned submission API."""

from collections.abc import Mapping

from rest_framework import serializers


class StrictInputSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            allowed = {field.field_name for field in self._writable_fields}
            unknown = set(data) - allowed
            if unknown:
                raise serializers.ValidationError(
                    {str(key): "Unknown field." for key in sorted(unknown, key=str)}
                )
        return super().to_internal_value(data)


class SubmissionCreateSerializer(StrictInputSerializer):
    run_id = serializers.UUIDField()
    problem_id = serializers.UUIDField()
    language_id = serializers.CharField(max_length=64, trim_whitespace=False)
    source = serializers.CharField(trim_whitespace=False, allow_blank=False)
