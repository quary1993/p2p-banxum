"""IP of Webby-Soft SRL. Opt-in manual regression account setup for staging/local only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from importlib import import_module
from typing import Any

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from backend.apps.platform_core.domain.access import is_superadmin_actor
from backend.apps.platform_core.domain.time import now_utc

REGRESSION_PROFILE = "manual-regression-v1"
REGRESSION_BALANCES = {"user1": 500_000_000, "user2": 500_000_000, "user3": 0}


@dataclass(frozen=True)
class RegressionAccounts:
    admin: str
    user1: str
    user2: str
    user3: str

    def fingerprint(self) -> str:
        content = json.dumps(
            {
                "profile": REGRESSION_PROFILE,
                "accounts": self.emails(),
                "balances": REGRESSION_BALANCES,
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def emails(self) -> dict[str, str]:
        return {role: email.strip().lower() for role, email in asdict(self).items()}


def regression_accounts_plan(
    accounts: RegressionAccounts, *, create_missing: bool
) -> dict[str, Any]:
    if settings.IS_PRODUCTION or settings.ENVIRONMENT not in {"local", "staging", "test"}:
        raise ValueError("The manual regression profile is only allowed in staging/local tests.")
    if not settings.QA_DEV_MODE_ALLOWED:
        raise ValueError("Enable QA_DEV_MODE_ALLOWED before preparing the regression baseline.")
    emails = accounts.emails()
    if len(set(emails.values())) != 4:
        raise ValueError("Admin and the three investors must have four distinct emails.")
    for email in emails.values():
        try:
            validate_email(email)
        except ValidationError as exc:
            raise ValueError("Every regression role requires a valid email.") from exc
    rows = []
    for role, email in emails.items():
        user = get_user_model().objects.filter(email__iexact=email).first()
        if user is None:
            if role == "admin" or not create_missing:
                raise ValueError(
                    f"Missing {role} account. Create it first or allow missing investors."
                )
        elif role == "admin":
            if user.account_type != "admin" or not user.is_active or user.status != "active":
                raise ValueError("The regression admin must be an existing active regular admin.")
        else:
            approved = (
                apps.get_model("kyc_compliance", "KycVerificationCase")
                .objects.filter(user_id=user.pk, status="approved")
                .exists()
            )
            if (
                user.account_type != "natural_person_lender"
                or user.is_staff
                or user.is_superuser
                or not user.is_active
                or user.status != "active"
                or not user.is_phone_verified
                or not approved
            ):
                raise ValueError(
                    f"Existing {role} must be an active, phone-verified, KYC-approved investor. "
                    "The reset will not change existing identity or verification decisions."
                )
        amount = REGRESSION_BALANCES.get(role, 0)
        rows.append(
            {
                "role": role,
                "account_id": str(user.pk) if user else None,
                "create_synthetic_investor": user is None,
                "opening_balance_minor": {"CHF": amount, "EUR": amount},
            }
        )
    return {
        "profile": REGRESSION_PROFILE,
        "accounts_fingerprint": accounts.fingerprint(),
        "accounts": rows,
    }


def create_missing_regression_investors(*, actor: Any, accounts: RegressionAccounts) -> None:
    # Called inside the guarded offline reset transaction, after a pre-reset backup.
    if not settings.QA_DATA_RESET_ALLOWED or not is_superadmin_actor(actor):
        raise ValueError("Regression accounts require the offline reset and a superadmin.")
    regression_accounts_plan(accounts, create_missing=True)
    kyc = import_module("backend.apps.kyc_compliance.services")
    for role, email in accounts.emails().items():
        if role == "admin" or get_user_model().objects.filter(email__iexact=email).exists():
            continue
        investor = get_user_model().objects.create_user(
            email=email,
            full_name=f"QA Regression User {role[-1]}",
            password=None,
            account_type="natural_person_lender",
            status="active",
            phone_verified_at=now_utc(),
        )
        case = kyc.get_or_create_user_kyc_case(investor)
        for decision in ("reopen", "approve"):
            kyc.record_manual_review_decision(
                kyc.ManualReviewDecisionCommand(
                    actor=actor,
                    case_id=str(case.pk),
                    decision=decision,
                    reason_code="other",
                    note="Synthetic staging regression identity; not a real KYC or SMS check.",
                    evidence_summary=REGRESSION_PROFILE,
                )
            )
