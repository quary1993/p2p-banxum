from __future__ import annotations

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone

from backend.apps.accounts_auth.references import (
    investor_reference_from_uuid,
    is_lender_account_type,
    next_investor_reference_candidate,
)
from backend.apps.platform_core.models.base import (
    AppendOnlyModel,
    PlatformDateTimeField,
    TimestampedModel,
)


class AccountType(models.TextChoices):
    NATURAL_PERSON_LENDER = "natural_person_lender", "Natural-person lender"
    LEGAL_ENTITY_LENDER_REPRESENTATIVE = (
        "legal_entity_lender_representative",
        "Legal-entity lender representative",
    )
    ADMIN = "admin", "Admin"
    SUPERADMIN = "superadmin", "Superadmin"


class AccountStatus(models.TextChoices):
    PENDING_KYC = "pending_kyc", "Pending KYC"
    ACTIVE = "active", "Active"
    RESTRICTED = "restricted", "Restricted"
    LOCKED = "locked", "Locked"
    CLOSED = "closed", "Closed"


class AccountAccessReason(models.TextChoices):
    KYC_AML_REVIEW = "kyc_aml_review", "KYC/AML review"
    COMPLIANCE_HOLD = "compliance_hold", "Compliance hold"
    EMAIL_RECOVERY = "email_recovery", "Email recovery"
    SUPPORT_REQUEST = "support_request", "Support request"
    ACCOUNT_CLOSURE = "account_closure", "Account closure"
    ADMIN_CORRECTION = "admin_correction", "Admin correction"
    OTHER = "other", "Other"


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> User:
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=self.normalize_email(email).strip().lower(), **extra_fields)
        if is_lender_account_type(str(user.account_type)) and not user.investor_reference:
            base_reference = investor_reference_from_uuid(user.id)
            for attempt in range(64):
                candidate = next_investor_reference_candidate(base_reference, attempt)
                if not self.model.objects.filter(investor_reference=candidate).exists():
                    user.investor_reference = candidate
                    break
            if not user.investor_reference:
                raise ValueError("Could not allocate a unique investor reference.")
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("account_type", AccountType.SUPERADMIN)
        extra_fields.setdefault("status", AccountStatus.ACTIVE)
        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    investor_reference = models.CharField(max_length=10, blank=True, default="")
    account_type = models.CharField(max_length=64, choices=AccountType.choices)
    status = models.CharField(
        max_length=32,
        choices=AccountStatus.choices,
        default=AccountStatus.PENDING_KYC,
    )
    phone_number = models.CharField(max_length=32, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    # 18.5: shown in Security ("Last changed"); set at registration and on every change/reset.
    password_changed_at = models.DateTimeField(null=True, blank=True)
    marketing_consent = models.BooleanField(default=False)
    # U33-DEC-32: "european" (1.234,56, the default) or "swiss" (1'234.56), for the interface,
    # notifications, emails and new personal reports.
    number_format = models.CharField(max_length=16, default="european")
    # U33-DEC-31: "en" (the default on the first visit) or "de-CH", for the investor platform,
    # notifications and emails. Contracts and source documents keep their own language.
    language = models.CharField(max_length=8, default="en")
    # 18.10: staff roles of an admin account (compliance, compliance deputy, security verifier,
    # security verifier deputy), granted by a superadmin.
    staff_roles = models.JSONField(default=list, blank=True)
    is_env_managed_superadmin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["email"]
        indexes = [
            models.Index(fields=["account_type", "status"]),
            models.Index(fields=["email"]),
            models.Index(fields=["investor_reference"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["investor_reference"],
                condition=~Q(investor_reference=""),
                name="unique_user_investor_reference",
            ),
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def can_login(self) -> bool:
        return self.is_active and self.status not in {
            AccountStatus.RESTRICTED,
            AccountStatus.LOCKED,
            AccountStatus.CLOSED,
        }

    @property
    def is_phone_verified(self) -> bool:
        return self.phone_verified_at is not None


class RegistrationTermsAcceptance(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="registration_terms")
    terms_version = models.CharField(max_length=64)
    terms_hash = models.CharField(max_length=128)
    accepted_at = PlatformDateTimeField(auto_now_add=True)
    # Audit S4-1 (Q06): never the IP itself, only its keyed hash (platform_core ip_privacy).
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-accepted_at", "-id"]
        indexes = [
            models.Index(fields=["user", "accepted_at"]),
            models.Index(fields=["terms_version"]),
        ]


class EmailLoginToken(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_login_tokens")
    email = models.EmailField()
    token_digest = models.CharField(max_length=64, unique=True)
    encrypted_token = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    # Set when a newer link for the same account is sent; a superseded link no longer
    # logs in. Real (wall) clock, like expires_at and used_at.
    superseded_at = models.DateTimeField(null=True, blank=True)
    requested_ip_hash = models.CharField(max_length=64, blank=True)
    requested_user_agent = models.TextField(blank=True)
    consumed_ip_hash = models.CharField(max_length=64, blank=True)
    consumed_user_agent = models.TextField(blank=True)
    # 18.5 (U33-DEC-01): no sign-in by email link. A link now only confirms the email of a
    # new account ("registration") and continues its registration in the browser, while the
    # account has no second factor yet; "login" and "existing_account" are older purposes.
    purpose = models.CharField(max_length=32, default="registration")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "used_at", "expires_at"]),
            models.Index(fields=["expires_at"]),
        ]

    @property
    def is_consumed(self) -> bool:
        return self.used_at is not None


class PhoneVerificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    VERIFIED = "verified", "Verified"
    FAILED = "failed", "Failed"
    SUPERSEDED = "superseded", "Superseded"
    EXPIRED = "expired", "Expired"


class PhoneVerificationPurpose(models.TextChoices):
    # Proves a new number during registration.
    PHONE_VERIFICATION = "phone_verification", "Phone verification"
    # Second factor of a forgotten-PIN reset, sent to the already verified number.
    PIN_RESET = "pin_reset", "PIN reset"
    # 18.5: the SMS second factor of a sign-in, a password reset or a security change.
    SIGN_IN = "sign_in", "Sign-in"
    SECURITY = "security", "Security confirmation"


class PhoneVerificationChallenge(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="phone_verification_challenges",
    )
    purpose = models.CharField(
        max_length=32,
        choices=PhoneVerificationPurpose.choices,
        default=PhoneVerificationPurpose.PHONE_VERIFICATION,
    )
    phone_number = models.CharField(max_length=32)
    provider = models.CharField(max_length=32)
    provider_reference = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=32,
        choices=PhoneVerificationStatus.choices,
        default=PhoneVerificationStatus.PENDING,
    )
    code_digest = models.CharField(max_length=64, blank=True)
    encrypted_code = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    requested_ip_hash = models.CharField(max_length=64, blank=True)
    requested_user_agent = models.TextField(blank=True)
    confirmed_ip_hash = models.CharField(max_length=64, blank=True)
    confirmed_user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "status", "expires_at"]),
            models.Index(fields=["expires_at"]),
        ]

    @property
    def is_verified(self) -> bool:
        return self.status == PhoneVerificationStatus.VERIFIED


class SensitiveAction(models.TextChoices):
    ADMIN_LOGIN = "admin_login", "Admin login"
    WITHDRAWAL = "withdrawal", "Withdrawal"
    BANK_ACCOUNT_CHANGE = "bank_account_change", "Bank account change"
    FX = "fx", "Currency exchange"
    PRIMARY_INVESTMENT = "primary_investment", "Primary investment"
    SECONDARY_MARKET_LISTING = "secondary_market_listing", "Secondary-market listing"
    SECONDARY_MARKET_PURCHASE = "secondary_market_purchase", "Secondary-market purchase"
    # PIN management (ACC-DEC-009). The registration PIN needs no email code.
    PIN_SETUP = "pin_setup", "PIN setup"
    PIN_CHANGE = "pin_change", "PIN change"
    PIN_RESET = "pin_reset", "PIN reset"


class SensitiveActionCode(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sensitive_action_codes")
    action = models.CharField(max_length=64, choices=SensitiveAction.choices)
    code_digest = models.CharField(max_length=64)
    encrypted_code = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    requested_ip_hash = models.CharField(max_length=64, blank=True)
    requested_user_agent = models.TextField(blank=True)
    consumed_ip_hash = models.CharField(max_length=64, blank=True)
    consumed_user_agent = models.TextField(blank=True)
    # 18.5: the operation the code was asked for (amount, currency, destination...), as a
    # keyed fingerprint; the operation that uses the code must have the same one. Empty for a
    # code asked without details (sign-in and other non-financial uses).
    operation_fingerprint = models.CharField(max_length=64, blank=True, default="")
    operation_summary = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "action", "consumed_at", "expires_at"]),
            models.Index(fields=["expires_at"]),
        ]

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None


class SensitiveActionPin(TimestampedModel):
    """The investor's 6-digit PIN for sensitive actions (ACC-DEC-009).

    Only a Django password hash is stored. Timestamps use the real clock, like code
    expiry, so the QA clock never shortens or extends a PIN lock.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="sensitive_action_pin",
    )
    pin_hash = models.CharField(max_length=256)
    set_at = models.DateTimeField()
    changed_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    last_failed_at = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["locked_until"])]

    def __str__(self) -> str:
        return f"PIN of {self.user_id}"


class AccountAccessEvent(AppendOnlyModel, TimestampedModel):
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="access_events",
    )
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    previous_status = models.CharField(max_length=32, choices=AccountStatus.choices)
    new_status = models.CharField(max_length=32, choices=AccountStatus.choices)
    previous_is_active = models.BooleanField()
    new_is_active = models.BooleanField()
    reason_code = models.CharField(
        max_length=64,
        choices=AccountAccessReason.choices,
        default=AccountAccessReason.OTHER,
    )
    note = models.TextField(blank=True)
    evidence_summary = models.TextField(blank=True)
    clean_account_confirmed = models.BooleanField(default=False)
    changed_at = models.DateTimeField()

    class Meta:
        ordering = ["-changed_at", "-id"]
        indexes = [
            models.Index(fields=["user", "changed_at"]),
            models.Index(fields=["actor_user_id", "changed_at"]),
            models.Index(fields=["new_status"]),
            models.Index(fields=["reason_code"]),
        ]


class SignInMethod(models.TextChoices):
    EMAIL_LINK = "email_link", "Email link"
    ADMIN_PASSWORD_CODE = "admin_password_code", "Password and email code"
    # 18.5 (U33-DEC-01, D-2): password and one second factor.
    PASSWORD_SMS = "password_sms", "Password and SMS code"
    PASSWORD_APP = "password_app", "Password and authenticator app"
    PASSWORD_RECOVERY_CODE = "password_recovery_code", "Password and recovery code"
    PASSWORD_TRUSTED_DEVICE = "password_trusted_device", "Password on a trusted device"
    PASSWORD_ONLY = "password_only", "Password (second factor not set up yet)"
    ADMIN_PASSWORD_APP = "admin_password_app", "Password and authenticator app (admin)"
    REGISTRATION_LINK = "registration_link", "Registration email link"


class SignInResult(models.TextChoices):
    SIGNED_IN = "signed_in", "Signed in"
    BLOCKED = "blocked", "Account blocked"
    FAILED = "failed", "Wrong password"
    FAILED_FACTOR = "failed_factor", "Wrong second-factor code"


class SessionEndReason(models.TextChoices):
    LOGOUT = "logout", "Signed out"
    REVOKED = "revoked", "Signed out from another device"
    REVOKED_OTHERS = "revoked_others", "Signed out with all other devices"
    REPLACED = "replaced", "Replaced by a new sign-in"
    # 18.5: a password or second-factor reset, or an assisted recovery, ends the other sessions.
    SECURITY_RESET = "security_reset", "Signed out after a security change"


class UserSession(TimestampedModel):
    """One signed-in browser (U33-DEC-25), linked to the server-side session by its id.

    The device is read from the browser's user agent; the place is the country a trusted
    proxy header gives (``SIGN_IN_COUNTRY_HEADER``), never GPS. Ending a session here ends
    the access: the session middleware signs that browser out on its next request.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tracked_sessions")
    method = models.CharField(max_length=32, choices=SignInMethod.choices, blank=True)
    device_label = models.CharField(max_length=120, blank=True)
    device_kind = models.CharField(max_length=16, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    # Q06: approximate city from the local IP database (never GPS); empty when unknown.
    city = models.CharField(max_length=120, blank=True, default="")
    ip_hash = models.CharField(max_length=64, blank=True)
    last_activity_at = PlatformDateTimeField(null=True, blank=True)
    ended_at = PlatformDateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=32, choices=SessionEndReason.choices, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "ended_at"]),
            models.Index(fields=["ended_at"]),
        ]


class SignInEvent(TimestampedModel):
    """One sign-in attempt of a known account (U33-DEC-25), kept after the session ends.

    Deleted after ``security.sign_in_history_retention_days`` by the scheduled job.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sign_in_events")
    method = models.CharField(max_length=32, choices=SignInMethod.choices)
    result = models.CharField(max_length=16, choices=SignInResult.choices)
    device_label = models.CharField(max_length=120, blank=True)
    device_kind = models.CharField(max_length=16, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=120, blank=True, default="")
    ip_hash = models.CharField(max_length=64, blank=True)
    # Keyed hash of the browser's random device cookie (audit G-03): tells two devices with
    # the same browser and system apart. Empty for sign-ins recorded before the cookie.
    device_hash = models.CharField(max_length=64, blank=True, default="")
    new_device = models.BooleanField(default=False)
    occurred_at = PlatformDateTimeField()

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["user", "occurred_at"]),
            models.Index(fields=["occurred_at"]),
            models.Index(fields=["user", "device_hash"]),
        ]


# --- 18.5: second factors, recovery and trusted devices (U33-DEC-01, Q05, D-1, D-2) ---------


class AuthenticatorApp(TimestampedModel):
    """An authenticator app (TOTP, RFC 6238) of an account.

    For an investor it is the sign-in second factor and replaces the PIN in operations (D-1);
    for an admin it is the only second factor. One active app per account; a new app replaces
    the old one. The secret is stored encrypted; ``last_used_step`` stops a code being used
    twice.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="authenticator_apps")
    encrypted_secret = models.TextField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_reason = models.CharField(max_length=64, blank=True)
    last_used_step = models.BigIntegerField(default=0)
    # Same lock as the PIN (AUTH_PIN_MAX_ATTEMPTS wrong codes -> AUTH_PIN_LOCK_SECONDS), for
    # sign-in and operation codes together; a right code resets the count.
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(confirmed_at__isnull=False, disabled_at__isnull=True),
                name="accounts_auth_one_active_authenticator",
            )
        ]


class RecoveryCode(TimestampedModel):
    """One of the 10 single-use recovery codes (stored as a keyed hash only)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_codes")
    batch_id = models.UUIDField()
    code_digest = models.CharField(max_length=64)
    used_at = models.DateTimeField(null=True, blank=True)
    replaced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["user", "used_at", "replaced_at"])]


class TrustedDevice(TimestampedModel):
    """A browser where the investor chose not to type the second factor for 30 days.

    Bound to its own random HTTP-only cookie (stored as a keyed hash); the password is still
    asked, and PIN or app confirmations of operations stay. Separate from the new-device alerts
    of the ``banxum_device`` cookie.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trusted_devices")
    token_digest = models.CharField(max_length=64, unique=True)
    device_label = models.CharField(max_length=120, blank=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "revoked_at", "expires_at"])]


class LoginChallenge(TimestampedModel):
    """A sign-in (or a reset) waiting for the second factor after the first step."""

    class Purpose(models.TextChoices):
        SIGN_IN = "sign_in", "Sign in"
        ADMIN_SIGN_IN = "admin_sign_in", "Admin sign in"
        PASSWORD_RESET = "password_reset", "Password reset"
        PIN_RESET = "pin_reset", "PIN reset"
        SECURITY_CHANGE = "security_change", "Security change"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_challenges")
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    method = models.CharField(max_length=16)
    phone_challenge_id = models.UUIDField(null=True, blank=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    requested_ip_hash = models.CharField(max_length=64, blank=True)
    requested_user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "purpose", "completed_at"])]


class PasswordResetToken(TimestampedModel):
    """A single-use email link to set a new password; the second factor is still needed."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token_digest = models.CharField(max_length=64, unique=True)
    # Encrypted for the email provider only; stored email copies show "[redacted]" (A-49).
    encrypted_token = models.TextField(blank=True)
    purpose = models.CharField(max_length=32, default="password_reset")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    requested_ip_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "used_at", "expires_at"])]


class AssistedRecoveryStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    IDENTITY_CONFIRMED = "identity_confirmed", "Identity confirmed"
    APPROVED = "approved", "Approved; waiting 24 hours"
    LINK_SENT = "link_sent", "Recovery link sent"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"
    DISPUTED = "disputed", "Stopped: the investor said it was not them"


class AssistedRecoveryCase(TimestampedModel):
    """A lost second factor without recovery codes (Q05, D4): support-led, two people.

    Support opens the case; a new Didit check is compared with the stored identity and
    recorded; another authorized person approves; unfinished authorizations and sessions end
    and the old factor is disabled; the investor gets a notice with a "This was not me" link and
    24 hours to stop it; then a single-use link lets the investor set a password and a new
    factor. At most 3 requests per account in 7 days.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="assisted_recoveries")
    status = models.CharField(
        max_length=32,
        choices=AssistedRecoveryStatus.choices,
        default=AssistedRecoveryStatus.REQUESTED,
    )
    requested_by_admin_id = models.UUIDField()
    request_note = models.TextField(blank=True)
    identity_confirmed_by_admin_id = models.UUIDField(null=True, blank=True)
    identity_confirmed_at = models.DateTimeField(null=True, blank=True)
    identity_evidence = models.TextField(blank=True)
    approved_by_admin_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    dispute_token_digest = models.CharField(max_length=64, blank=True)
    encrypted_dispute_token = models.TextField(blank=True)
    wait_until = models.DateTimeField(null=True, blank=True)
    link_sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "created_at"]), models.Index(fields=["status"])]


class SecurityRestriction(TimestampedModel):
    """72 hours after a completed recovery: no new bank account, no new default return account.

    Withdrawals to verified accounts and mandatory returns stay possible.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="security_restrictions")
    reason = models.CharField(max_length=64)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        ordering = ["-ends_at", "-id"]
        indexes = [models.Index(fields=["user", "ends_at"])]
