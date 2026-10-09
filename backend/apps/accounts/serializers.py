"""Strict, allowlisted account input and public user representations."""

from collections.abc import Mapping

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from backend.apps.accounts.models import User


class StrictInputSerializer(serializers.Serializer):
    """Reject undeclared keys so sensitive model fields cannot be mass-assigned."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            allowed = {field.field_name for field in self._writable_fields}
            unknown = set(data) - allowed
            if unknown:
                raise serializers.ValidationError(
                    {str(key): "Unknown field." for key in sorted(unknown, key=str)}
                )
        return super().to_internal_value(data)


class RegisterSerializer(StrictInputSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=1024, trim_whitespace=False, write_only=True)
    display_name = serializers.CharField(max_length=80)

    def validate_email(self, value):
        normalized = value.strip().casefold()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("Аккаунт с таким email уже существует.")
        return normalized

    def validate(self, attrs):
        candidate = User(email=attrs["email"], display_name=attrs["display_name"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    email=validated_data["email"],
                    display_name=validated_data["display_name"],
                    password=validated_data["password"],
                )
        except IntegrityError as exc:
            # Covers concurrent registrations racing after the preflight query.
            raise serializers.ValidationError(
                {"email": "Аккаунт с таким email уже существует."}
            ) from exc


class LoginSerializer(StrictInputSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=1024, trim_whitespace=False, write_only=True)

    def validate_email(self, value):
        return value.strip().casefold()


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "display_name", "role")
        read_only_fields = fields
