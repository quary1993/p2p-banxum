from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.accounts_auth.models import User


class UserSummarySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    account_type = serializers.CharField()
    status = serializers.CharField()
    phone_verified = serializers.BooleanField(source="is_phone_verified")
    marketing_consent = serializers.BooleanField()


class NaturalPersonRegistrationRequestSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=255)
    phone_number = serializers.CharField(max_length=32)
    terms_version = serializers.CharField(max_length=64)
    terms_hash = serializers.CharField(max_length=128)
    marketing_consent = serializers.BooleanField(default=False)


class NaturalPersonRegistrationResponseSerializer(serializers.Serializer[Any]):
    user = UserSummarySerializer()


class MagicLinkRequestSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()


class MagicLinkConsumeSerializer(serializers.Serializer[Any]):
    token = serializers.CharField()


class AuthenticatedUserResponseSerializer(serializers.Serializer[Any]):
    user = UserSummarySerializer()


class AdminLoginStartRequestSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class AdminLoginStartResponseSerializer(serializers.Serializer[Any]):
    code_id = serializers.UUIDField()
    status = serializers.CharField()
    expires_at = serializers.DateTimeField()


class AdminLoginConfirmRequestSerializer(serializers.Serializer[Any]):
    code_id = serializers.UUIDField()
    code = serializers.RegexField(regex=r"^\d{6}$")


class AdminUserCreateRequestSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, min_length=1, write_only=True)
    full_name = serializers.CharField(max_length=255)


class PhoneVerificationRequestResponseSerializer(serializers.Serializer[Any]):
    challenge_id = serializers.UUIDField(allow_null=True)
    status = serializers.CharField()
    expires_at = serializers.DateTimeField(allow_null=True)
    phone_verified = serializers.BooleanField()


class PhoneVerificationConfirmRequestSerializer(serializers.Serializer[Any]):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(regex=r"^\d{6}$")


class PhoneVerificationConfirmResponseSerializer(serializers.Serializer[Any]):
    user = UserSummarySerializer()


def serialize_user(user: User) -> dict[str, Any]:
    return dict(UserSummarySerializer(user).data)
