from __future__ import annotations

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from backend.apps.platform_core.models.base import TimestampedModel


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
    account_type = models.CharField(max_length=64, choices=AccountType.choices)
    status = models.CharField(
        max_length=32,
        choices=AccountStatus.choices,
        default=AccountStatus.PENDING_KYC,
    )
    phone_number = models.CharField(max_length=32, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    marketing_consent = models.BooleanField(default=False)
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
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
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
    requested_ip = models.GenericIPAddressField(null=True, blank=True)
    requested_user_agent = models.TextField(blank=True)
    consumed_ip = models.GenericIPAddressField(null=True, blank=True)
    consumed_user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "used_at", "expires_at"]),
            models.Index(fields=["expires_at"]),
        ]

    @property
    def is_consumed(self) -> bool:
        return self.used_at is not None


class SensitiveAction(models.TextChoices):
    ADMIN_LOGIN = "admin_login", "Admin login"
    WITHDRAWAL = "withdrawal", "Withdrawal"
    BANK_ACCOUNT_CHANGE = "bank_account_change", "Bank account change"
    FX = "fx", "Currency exchange"
    PRIMARY_INVESTMENT = "primary_investment", "Primary investment"
    SECONDARY_MARKET_LISTING = "secondary_market_listing", "Secondary-market listing"
    SECONDARY_MARKET_PURCHASE = "secondary_market_purchase", "Secondary-market purchase"


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
    requested_ip = models.GenericIPAddressField(null=True, blank=True)
    requested_user_agent = models.TextField(blank=True)
    consumed_ip = models.GenericIPAddressField(null=True, blank=True)
    consumed_user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "action", "consumed_at", "expires_at"]),
            models.Index(fields=["expires_at"]),
        ]

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None
