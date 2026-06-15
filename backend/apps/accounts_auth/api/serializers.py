from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.accounts_auth.models import (
    AccountAccessEvent,
    AccountAccessReason,
    AccountStatus,
    SensitiveAction,
    User,
)


class UserSummarySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    investor_reference = serializers.CharField(allow_null=True)
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
    email_login_sent = serializers.BooleanField()


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


class SensitiveActionCodeRequestSerializer(serializers.Serializer[Any]):
    action = serializers.ChoiceField(
        choices=[
            SensitiveAction.WITHDRAWAL,
            SensitiveAction.BANK_ACCOUNT_CHANGE,
            SensitiveAction.FX,
            SensitiveAction.PRIMARY_INVESTMENT,
            SensitiveAction.SECONDARY_MARKET_LISTING,
            SensitiveAction.SECONDARY_MARKET_PURCHASE,
        ]
    )


class SensitiveActionCodeRequestResponseSerializer(serializers.Serializer[Any]):
    code_id = serializers.UUIDField()
    action = serializers.CharField()
    status = serializers.CharField()
    expires_at = serializers.DateTimeField()


class AdminUserCreateRequestSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, min_length=1, write_only=True)
    full_name = serializers.CharField(max_length=255)


class AccountAccessChangeRequestSerializer(serializers.Serializer[Any]):
    new_status = serializers.ChoiceField(
        choices=[
            AccountStatus.ACTIVE,
            AccountStatus.RESTRICTED,
            AccountStatus.LOCKED,
            AccountStatus.CLOSED,
        ]
    )
    reason_code = serializers.ChoiceField(choices=AccountAccessReason.choices)
    note = serializers.CharField(required=False, allow_blank=True)
    evidence_summary = serializers.CharField(required=False, allow_blank=True)
    clean_account_confirmed = serializers.BooleanField(default=False)


class AccountAccessEventSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    user_id = serializers.UUIDField(source="user.id")
    actor_user_id = serializers.UUIDField()
    actor_account_type = serializers.CharField()
    previous_status = serializers.CharField()
    new_status = serializers.CharField()
    previous_is_active = serializers.BooleanField()
    new_is_active = serializers.BooleanField()
    reason_code = serializers.CharField()
    note = serializers.CharField()
    evidence_summary = serializers.CharField()
    clean_account_confirmed = serializers.BooleanField()
    changed_at = serializers.DateTimeField()


class AccountAccessChangeResponseSerializer(serializers.Serializer[Any]):
    user = UserSummarySerializer()
    event = AccountAccessEventSerializer()


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


def serialize_account_access_event(event: AccountAccessEvent) -> dict[str, Any]:
    return dict(AccountAccessEventSerializer(event).data)
