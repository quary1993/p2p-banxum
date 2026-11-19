"""IP of Webby-Soft SRL. 18.5 sign-in, recovery and Security tab request and response bodies."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.accounts_auth.api.serializers import UserSummarySerializer
from backend.apps.accounts_auth.passwords import MAX_LENGTH

_CODE = r"^\d{6}$"


def _password(**kwargs: Any) -> serializers.CharField:
    return serializers.CharField(
        trim_whitespace=False, write_only=True, max_length=MAX_LENGTH, **kwargs
    )


class SignInRequestSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()
    password = _password()


class SignInResponseSerializer(serializers.Serializer[Any]):
    # signed_in | factor_required | enrollment_required
    status = serializers.CharField()
    # app | sms (factor_required)
    method = serializers.CharField(allow_blank=True)
    challenge_id = serializers.CharField(allow_blank=True)
    phone_last_digits = serializers.CharField(allow_blank=True)
    user = UserSummarySerializer(required=False, allow_null=True)


class FactorCodeRequestSerializer(serializers.Serializer[Any]):
    """The second factor of a pending step: a 6-digit code, or one recovery code."""

    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(regex=_CODE, required=False, allow_blank=True)
    recovery_code = serializers.CharField(required=False, allow_blank=True, max_length=16)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if (
            not str(attrs.get("code") or "").strip()
            and not str(attrs.get("recovery_code") or "").strip()
        ):
            raise serializers.ValidationError("Type the code, or a recovery code.")
        return attrs


class SignInVerifyRequestSerializer(FactorCodeRequestSerializer):
    # Remember this browser for 30 days (the password is still asked).
    trust_device = serializers.BooleanField(required=False, default=False)


class AuthenticatedUserSerializer(serializers.Serializer[Any]):
    user = UserSummarySerializer()


class ChallengeRequestSerializer(serializers.Serializer[Any]):
    challenge_id = serializers.UUIDField()


class StatusResponseSerializer(serializers.Serializer[Any]):
    status = serializers.CharField()


class PasswordForgotRequestSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()


class TokenRequestSerializer(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=128)


class FactorStepResponseSerializer(serializers.Serializer[Any]):
    # factor_required | enrollment_required
    status = serializers.CharField()
    method = serializers.CharField(allow_blank=True)
    challenge_id = serializers.CharField(allow_blank=True)
    phone_last_digits = serializers.CharField(allow_blank=True)


class PasswordResetCompleteRequestSerializer(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=128)
    new_password = _password()
    challenge_id = serializers.CharField(required=False, allow_blank=True, max_length=64)
    code = serializers.RegexField(regex=_CODE, required=False, allow_blank=True)
    recovery_code = serializers.CharField(required=False, allow_blank=True, max_length=16)


class AssistedRecoveryCompleteRequestSerializer(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=128)
    new_password = _password()


class SecurityConfirmStartRequestSerializer(serializers.Serializer[Any]):
    password = _password()


class SecurityConfirmResponseSerializer(serializers.Serializer[Any]):
    confirmation_id = serializers.CharField()


class PasswordChangeRequestSerializer(serializers.Serializer[Any]):
    new_password = _password()
    confirmation_id = serializers.UUIDField()


class AuthenticatorEnrollmentResponseSerializer(serializers.Serializer[Any]):
    enrollment_id = serializers.CharField()
    secret = serializers.CharField()
    otpauth_uri = serializers.CharField()


class AuthenticatorConfirmRequestSerializer(serializers.Serializer[Any]):
    enrollment_id = serializers.UUIDField()
    code = serializers.RegexField(regex=_CODE)
    # Needed when the account already has a second factor (replace, or SMS -> app).
    confirmation_id = serializers.UUIDField(required=False, allow_null=True)


class RecoveryCodesRequestSerializer(serializers.Serializer[Any]):
    # Needed for a new set (the first set after the factor set-up needs none).
    confirmation_id = serializers.UUIDField(required=False, allow_null=True)


class RecoveryCodesResponseSerializer(serializers.Serializer[Any]):
    codes = serializers.ListField(child=serializers.CharField())


class TrustedDeviceSerializer(serializers.Serializer[Any]):
    id = serializers.CharField()
    device_label = serializers.CharField()
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    last_used_at = serializers.DateTimeField(allow_null=True)


class SecurityRestrictionSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()
    ends_at = serializers.DateTimeField()


class SecurityOverviewSerializer(serializers.Serializer[Any]):
    # app | sms | "" (no factor yet)
    second_factor = serializers.CharField(allow_blank=True)
    phone_last_digits = serializers.CharField(allow_blank=True)
    authenticator_added_at = serializers.DateTimeField(allow_null=True)
    recovery_codes_remaining = serializers.IntegerField()
    recovery_codes_issued = serializers.BooleanField()
    password_set = serializers.BooleanField()
    password_changed_at = serializers.DateTimeField(allow_null=True)
    trusted_devices = TrustedDeviceSerializer(many=True)
    restriction = SecurityRestrictionSerializer(allow_null=True)


class AdminSignInStartResponseSerializer(serializers.Serializer[Any]):
    # factor_required (app code next) | enrollment_required (email code + new app)
    status = serializers.CharField()
    challenge_id = serializers.CharField(allow_blank=True)
    code_id = serializers.CharField(allow_blank=True)
    expires_at = serializers.DateTimeField(allow_null=True)
    enrollment_id = serializers.CharField(allow_blank=True)
    secret = serializers.CharField(allow_blank=True)
    otpauth_uri = serializers.CharField(allow_blank=True)


class AdminSignInConfirmRequestSerializer(serializers.Serializer[Any]):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(regex=_CODE)


class AdminEnrollmentRequestSerializer(serializers.Serializer[Any]):
    code_id = serializers.UUIDField()
    email_code = serializers.RegexField(regex=_CODE)
    enrollment_id = serializers.UUIDField()
    code = serializers.RegexField(regex=_CODE)


class AssistedRecoveryOpenRequestSerializer(serializers.Serializer[Any]):
    user_id = serializers.UUIDField()
    note = serializers.CharField(max_length=2000)


class AssistedRecoveryEvidenceRequestSerializer(serializers.Serializer[Any]):
    evidence = serializers.CharField(max_length=2000)


class AssistedRecoveryCaseSerializer(serializers.Serializer[Any]):
    id = serializers.CharField()
    user_id = serializers.CharField()
    user_email = serializers.CharField()
    status = serializers.CharField()
    request_note = serializers.CharField(allow_blank=True)
    identity_evidence = serializers.CharField(allow_blank=True)
    requested_by_admin_id = serializers.CharField(allow_blank=True)
    identity_confirmed_by_admin_id = serializers.CharField(allow_blank=True)
    approved_by_admin_id = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    wait_until = serializers.DateTimeField(allow_null=True)
    link_sent_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    cancelled_at = serializers.DateTimeField(allow_null=True)


class AssistedRecoveryListSerializer(serializers.Serializer[Any]):
    results = AssistedRecoveryCaseSerializer(many=True)


class TwoFactorErrorSerializer(serializers.Serializer[Any]):
    detail = serializers.CharField()
    code = serializers.CharField()
    attempts_left = serializers.IntegerField(required=False)
    locked_until = serializers.DateTimeField(required=False)
