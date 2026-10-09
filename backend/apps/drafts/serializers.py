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


class DraftUpdateSerializer(StrictInputSerializer):
    run_id = serializers.UUIDField()
    source = serializers.CharField(trim_whitespace=False, allow_blank=True)
    expected_revision = serializers.IntegerField(min_value=0, max_value=2**31 - 1)
