from __future__ import annotations

from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from backend.apps.accounts_auth.factors import factor_kind
from backend.apps.accounts_auth.models import (
    AccountAccessEvent,
    AccountAccessReason,
    AccountStatus,
    SensitiveAction,
    SignInMethod,
    SignInResult,
    User,
)
from backend.apps.accounts_auth.phone_numbers import (
    InvalidPhoneNumberError,
    normalize_e164_phone_number,
)
from backend.apps.accounts_auth.pin_services import PinStatus, pin_locked_until, user_has_pin
from backend.apps.platform_core.api.sensitive_actions import sensitive_action_pin_field


def _validated_phone_number(value: str) -> str:
    try:
        return normalize_e164_phone_number(value)
    except InvalidPhoneNumberError as exc:
        raise serializers.ValidationError(str(exc)) from exc


pin_field = sensitive_action_pin_field


def mask_phone_number(value: str) -> str:
    """'+41791234567' -> '+41 ••• ••• •• 67'; empty when no number is stored."""
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) < 6:
        return ""
    country = digits[:2] if value.strip().startswith("+") else ""
    prefix = f"+{country} " if country else ""
    return f"{prefix}••• ••• •• {digits[-2:]}"


class UserSummarySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    investor_reference = serializers.CharField(allow_null=True)
    account_type = serializers.CharField()
    status = serializers.CharField()
    phone_verified = serializers.BooleanField(source="is_phone_verified")
    marketing_consent = serializers.BooleanField()
    # U33-DEC-32: "european" (default) or "swiss".
    number_format = serializers.CharField()
    # U33-DEC-31: "en" (default) or "de-CH".
    language = serializers.CharField()
    # ACC-DEC-009: the portal asks for a PIN before anything else while this is false.
    pin_set = serializers.SerializerMethodField()
    # Only while the PIN is locked after too many wrong attempts.
    pin_locked_until = serializers.SerializerMethodField()
    # 18.5 / D-1: "app" (authenticator code; no PIN), "sms" (SMS code; PIN for operations) or
    # "" (no second factor yet: the portal shows the factor set-up before anything else).
    second_factor = serializers.SerializerMethodField()
    # Re-audit R8-1: the registered mobile number, masked (country code and last two digits), so
    # a new tab of the registration can send the SMS code to it without the full number.
    phone_number_masked = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_second_factor(self, user: User) -> str:
        return factor_kind(user)

    @extend_schema_field(OpenApiTypes.STR)
    def get_phone_number_masked(self, user: User) -> str:
        return mask_phone_number(str(getattr(user, "phone_number", "") or ""))

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_pin_set(self, user: User) -> bool:
        return user_has_pin(user)

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_pin_locked_until(self, user: User) -> str | None:
        locked_until = pin_locked_until(user)
        return locked_until.isoformat() if locked_until is not None else None


class NaturalPersonRegistrationRequestSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()
    # 18.5: 12-128 characters, not a common or leaked password (checked by the service).
    password = serializers.CharField(trim_whitespace=False, write_only=True, max_length=128)
    full_name = serializers.CharField(max_length=255)
    phone_number = serializers.CharField(max_length=32)
    terms_version = serializers.CharField(max_length=64)
    terms_hash = serializers.CharField(max_length=128)
    registration_document_template_version_id = serializers.UUIDField(required=False)
    risk_document_template_version_id = serializers.UUIDField(required=False)
    accepted_checkbox_labels = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=False,
    )
    accepted_risk_checkbox_labels = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=False,
    )
    document_idempotency_key = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=160,
    )
    risk_document_idempotency_key = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=160,
    )
    marketing_consent = serializers.BooleanField(default=False)

    def validate_phone_number(self, value: str) -> str:
        return _validated_phone_number(value)


class NaturalPersonRegistrationResponseSerializer(serializers.Serializer[Any]):
    """The same answer for a new address and an address that already has an account."""

    status = serializers.CharField()
    email_login_sent = serializers.BooleanField()


class PhoneVerificationRequestSerializer(serializers.Serializer[Any]):
    phone_number = serializers.CharField(max_length=32, required=False, allow_blank=True)

    def validate_phone_number(self, value: str) -> str:
        if not value.strip():
            return ""
        return _validated_phone_number(value)


class MagicLinkRequestSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()


class MagicLinkConsumeSerializer(serializers.Serializer[Any]):
    token = serializers.CharField()


class AuthenticatedUserResponseSerializer(serializers.Serializer[Any]):
    user = UserSummarySerializer()


class CurrentUserResponseSerializer(AuthenticatedUserResponseSerializer):
    qa_controls_available = serializers.BooleanField()
    platform_business_date = serializers.DateField()


class MarketingConsentUpdateRequestSerializer(serializers.Serializer[Any]):
    marketing_consent = serializers.BooleanField()


class DisplayPreferencesUpdateRequestSerializer(serializers.Serializer[Any]):
    number_format = serializers.ChoiceField(choices=["european", "swiss"], required=False)
    language = serializers.ChoiceField(choices=["en", "de-CH"], required=False)


class OperationDetailsSerializer(serializers.Serializer[Any]):
    """18.5: the details the email code confirms. Each action takes one fixed set of fields:
    withdrawal (amount_minor, currency, iban); bank_account_change (currency, iban) or
    (instruction_id); fx (amount_minor, source_currency, target_currency); primary_investment
    (amount_minor, currency, loan_id); secondary_market_listing (holding_id, price_bps) or
    (listing_id, price_bps); secondary_market_purchase (amount_minor, currency, listing_id)."""

    amount_minor = serializers.IntegerField(required=False, min_value=1)
    currency = serializers.CharField(required=False, max_length=3)
    iban = serializers.CharField(required=False, max_length=64)
    source_currency = serializers.CharField(required=False, max_length=3)
    target_currency = serializers.CharField(required=False, max_length=3)
    loan_id = serializers.CharField(required=False, max_length=64)
    listing_id = serializers.CharField(required=False, max_length=64)
    holding_id = serializers.CharField(required=False, max_length=64)
    instruction_id = serializers.CharField(required=False, max_length=64)
    price_bps = serializers.IntegerField(required=False, min_value=0)


class SensitiveActionCodeRequestSerializer(serializers.Serializer[Any]):
    operation = OperationDetailsSerializer(required=False)
    action = serializers.ChoiceField(
        choices=[
            SensitiveAction.WITHDRAWAL,
            SensitiveAction.BANK_ACCOUNT_CHANGE,
            SensitiveAction.FX,
            SensitiveAction.PRIMARY_INVESTMENT,
            SensitiveAction.SECONDARY_MARKET_LISTING,
            SensitiveAction.SECONDARY_MARKET_PURCHASE,
            SensitiveAction.PIN_SETUP,
            SensitiveAction.PIN_CHANGE,
        ]
    )


class SensitiveActionCodeRequestResponseSerializer(serializers.Serializer[Any]):
    code_id = serializers.UUIDField()
    action = serializers.CharField()
    status = serializers.CharField()
    expires_at = serializers.DateTimeField()
    operation_summary = serializers.CharField(allow_blank=True)


class AdminUserCreateRequestSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()
    # Audit S4-5: the length bounds of the one password policy; the service checks the rest.
    password = serializers.CharField(
        trim_whitespace=False, min_length=12, max_length=128, write_only=True
    )
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


class PinStatusSerializer(serializers.Serializer[Any]):
    pin_set = serializers.BooleanField()
    locked_until = serializers.DateTimeField(allow_null=True)
    attempts_left = serializers.IntegerField()
    max_attempts = serializers.IntegerField()
    # False only at the registration step (pending KYC, phone just verified).
    setup_requires_email_code = serializers.BooleanField()
    # Forgot PIN sends an SMS code to the verified phone number ending in these digits.
    reset_available = serializers.BooleanField()
    phone_last_digits = serializers.CharField(allow_blank=True)
    # D-1: "app" means the authenticator code replaces the PIN (no PIN boxes).
    second_factor = serializers.CharField(allow_blank=True)


class PinStatusResponseSerializer(serializers.Serializer[Any]):
    pin = PinStatusSerializer()


class PinSetRequestSerializer(serializers.Serializer[Any]):
    new_pin = pin_field()
    new_pin_confirmation = pin_field()
    # Not needed at the registration step; required for every other first PIN.
    sensitive_action_code_id = serializers.UUIDField(required=False, allow_null=True)
    sensitive_action_code = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )


class PinChangeRequestSerializer(serializers.Serializer[Any]):
    pin = pin_field()
    new_pin = pin_field()
    new_pin_confirmation = pin_field()
    sensitive_action_code_id = serializers.UUIDField()
    sensitive_action_code = serializers.CharField(max_length=32, trim_whitespace=True)


class PinResetStartResponseSerializer(serializers.Serializer[Any]):
    phone_challenge_id = serializers.UUIDField()
    expires_at = serializers.DateTimeField()
    phone_last_digits = serializers.CharField(allow_blank=True)


class PinResetStartRequestSerializer(serializers.Serializer[Any]):
    password = serializers.CharField(trim_whitespace=False, write_only=True, max_length=128)


class PinResetConfirmRequestSerializer(serializers.Serializer[Any]):
    phone_challenge_id = serializers.UUIDField()
    phone_code = serializers.RegexField(regex=r"^\d{6}$")
    new_pin = pin_field()
    new_pin_confirmation = pin_field()


class PinErrorResponseSerializer(serializers.Serializer[Any]):
    """Error body of the PIN checks; ``code`` names the case (ACC-DEC-009)."""

    detail = serializers.CharField()
    code = serializers.CharField()
    attempts_left = serializers.IntegerField(required=False)
    locked_until = serializers.DateTimeField(required=False)


def serialize_pin_status(status: PinStatus) -> dict[str, Any]:
    return dict(
        PinStatusSerializer(
            {
                "pin_set": status.pin_set,
                "locked_until": status.locked_until,
                "attempts_left": status.attempts_left,
                "max_attempts": status.max_attempts,
                "setup_requires_email_code": status.setup_requires_email_code,
                "reset_available": status.reset_available,
                "phone_last_digits": status.phone_last_digits,
                "second_factor": status.second_factor,
            }
        ).data
    )


def serialize_user(user: User) -> dict[str, Any]:
    return dict(UserSummarySerializer(user).data)


def serialize_account_access_event(event: AccountAccessEvent) -> dict[str, Any]:
    return dict(AccountAccessEventSerializer(event).data)


class UserSessionSerializer(serializers.Serializer[Any]):
    """U33-DEC-25: one signed-in browser. The place is a country code, never GPS."""

    id = serializers.UUIDField()
    device_label = serializers.CharField()
    device_kind = serializers.CharField(allow_blank=True)
    country_code = serializers.CharField(allow_blank=True)
    city = serializers.CharField(allow_blank=True, required=False, default="")
    place = serializers.CharField(
        allow_blank=True,
        required=False,
        default="",
        help_text="Q06: 'City, CC (approximate)', the country alone, or empty.",
    )
    method = serializers.ChoiceField(choices=SignInMethod.choices, allow_blank=True)
    started_at = serializers.DateTimeField()
    last_activity_at = serializers.DateTimeField()
    current = serializers.BooleanField()


class UserSessionsResponseSerializer(serializers.Serializer[Any]):
    sessions = UserSessionSerializer(many=True)


class SignInEventSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    occurred_at = serializers.DateTimeField()
    device_label = serializers.CharField()
    device_kind = serializers.CharField(allow_blank=True)
    country_code = serializers.CharField(allow_blank=True)
    city = serializers.CharField(allow_blank=True, required=False, default="")
    place = serializers.CharField(allow_blank=True, required=False, default="")
    # Audit S4-8: both are enums in the API, so the screen has one label for every value.
    method = serializers.ChoiceField(choices=SignInMethod.choices)
    result = serializers.ChoiceField(choices=SignInResult.choices)


class SignInHistoryResponseSerializer(serializers.Serializer[Any]):
    events = SignInEventSerializer(many=True)
    retention_days = serializers.IntegerField()


class RevokeOtherSessionsResponseSerializer(serializers.Serializer[Any]):
    sessions_ended = serializers.IntegerField()
