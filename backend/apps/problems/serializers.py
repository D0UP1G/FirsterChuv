from rest_framework import serializers

from .models import ProblemVersion


class AdminProblemVersionSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="public_data.label", read_only=True)
    title = serializers.CharField(source="public_data.title", read_only=True)
    time_limit_ms = serializers.IntegerField(source="public_data.time_limit_ms", read_only=True)
    memory_limit_bytes = serializers.IntegerField(source="public_data.memory_limit_bytes", read_only=True)
    languages = serializers.SerializerMethodField()

    class Meta:
        model = ProblemVersion
        fields = (
            "problem_id",
            "version",
            "readiness",
            "is_active",
            "label",
            "title",
            "time_limit_ms",
            "memory_limit_bytes",
            "languages",
            "created_at",
        )
        read_only_fields = fields

    def get_languages(self, instance: ProblemVersion) -> list[dict[str, str]]:
        return [
            {"id": item["id"], "name": item["name"], "template": item["template"]}
            for item in instance.public_data.languages
        ]
