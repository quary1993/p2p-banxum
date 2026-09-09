from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.cache import cache

from backend.apps.ledger.qa_seed import create_qa_opening_balance
from backend.apps.platform_core.services.qa_dev_mode import (
    AdvanceQaDevModeTimeCommand,
    EnableQaDevModeCommand,
    RevertQaDevModeCommand,
    advance_qa_dev_mode_time,
    enable_qa_dev_mode,
    revert_qa_dev_mode,
)
from backend.apps.platform_core.services.qa_regression import RegressionAccounts
from backend.apps.platform_core.services.qa_reset import (
    _reset_models,
    qa_reset_plan,
    reset_qa_dataset,
)
from backend.apps.platform_core.services.qa_snapshot import SnapshotJSONEncoder
from backend.apps.platform_core.tests.test_qa_reset import setup_reset  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def regression(setup_reset: Any, settings: Any, tmp_path: Path) -> Any:  # noqa: F811
    settings.QA_DEV_MODE_ALLOWED = True
    settings.QA_DEV_MODE_SNAPSHOT_DIR = str(tmp_path / "snapshots")
    get_user_model().objects.create_user(
        email="regression.admin@example.test",
        full_name="Regression admin",
        account_type="admin",
        status="active",
        is_staff=True,
    )
    return replace(
        setup_reset,
        regression_accounts=RegressionAccounts(
            admin="regression.admin@example.test",
            user1="regression+1@example.test",
            user2="regression+2@example.test",
            user3="regression+3@example.test",
        ),
        create_missing_investors=True,
    )


def test_regression_balances_identities_capacity_and_idempotence(regression: Any) -> None:
    before = list(get_user_model().objects.values())
    result = reset_qa_dataset(regression)
    assert result["investors_credited"] == 3  # original seed investor plus two regression investors
    for row in before:
        assert get_user_model().objects.filter(pk=row["id"]).values().get() == row
    loans = apps.get_model("loans", "Loan")
    # Five million per currency covers even the entire seeded catalogue at face value.
    for currency in ("CHF", "EUR"):
        assert (
            sum(
                loans.objects.filter(currency_id=currency).values_list("principal_minor", flat=True)
            )
            < 500_000_000
        )
    lots = apps.get_model("ledger", "InvestorBalanceLot")
    for role, email in regression.regression_accounts.emails().items():
        user = get_user_model().objects.get(email=email)
        balances = list(
            lots.objects.filter(investor_user_id=user.pk).values_list(
                "currency_id", "available_amount_minor"
            )
        )
        if role in {"user1", "user2"}:
            assert sorted(balances) == [("CHF", 500_000_000), ("EUR", 500_000_000)]
        else:
            assert balances == []
        if role != "admin":
            assert not user.has_usable_password()
            assert user.is_phone_verified and user.status == "active"
            assert (
                apps.get_model("kyc_compliance", "KycVerificationCase")
                .objects.get(user=user)
                .status
                == "approved"
            )
            assert (
                not apps.get_model("documents", "DocumentAcceptanceEvidence")
                .objects.filter(user_id=user.pk)
                .exists()
            )
    assert not apps.get_model("ledger", "InvestorPayoutInstruction").objects.exists()
    assert not apps.get_model("holdings", "InvestorLoanHolding").objects.exists()
    assert (
        not apps.get_model("platform_core", "OutboxMessage")
        .objects.exclude(status="processed")
        .exists()
    )
    assert reset_qa_dataset(regression)["already_completed"] is True
    with pytest.raises(ValueError, match="another account profile"):
        reset_qa_dataset(replace(regression, regression_accounts=None))


def test_profile_preview_is_read_only(regression: Any) -> None:
    before = get_user_model().objects.count()
    plan = qa_reset_plan(
        regression_accounts=regression.regression_accounts, create_missing_investors=True
    )
    assert get_user_model().objects.count() == before
    assert sum(row["create_synthetic_investor"] for row in plan["regression"]["accounts"]) == 3
    assert plan["regression"]["accounts"][-1]["opening_balance_minor"] == {"CHF": 0, "EUR": 0}


@pytest.mark.parametrize(
    "problem", ["production", "duplicate", "missing", "admin_role", "existing_unverified"]
)
def test_profile_rejects_unsafe_setup_before_backup(
    regression: Any, settings: Any, problem: str
) -> None:
    if problem == "production":
        settings.IS_PRODUCTION = True
        regression = replace(regression, allow_production=True)
    elif problem == "duplicate":
        regression = replace(
            regression,
            regression_accounts=replace(
                regression.regression_accounts, user3=regression.regression_accounts.user1
            ),
        )
    elif problem == "missing":
        regression = replace(regression, create_missing_investors=False)
    elif problem == "admin_role":
        get_user_model().objects.filter(email=regression.regression_accounts.admin).update(
            account_type="superadmin"
        )
    else:
        get_user_model().objects.create_user(
            email=regression.regression_accounts.user1,
            account_type="natural_person_lender",
            status="pending_kyc",
        )
    with pytest.raises(ValueError):
        reset_qa_dataset(regression)
    assert not regression.backup_directory.exists()


def test_failed_reset_does_not_leave_created_accounts(regression: Any, monkeypatch: Any) -> None:
    before = get_user_model().objects.count()

    def fail(**kwargs: Any) -> None:
        raise ValueError("Synthetic failure")

    monkeypatch.setattr("backend.apps.platform_core.services.qa_reset._seed_catalogue", fail)
    with pytest.raises(ValueError, match="Synthetic failure"):
        reset_qa_dataset(regression)
    assert get_user_model().objects.count() == before


def test_baseline_snapshot_restores_balances_and_empty_account(
    regression: Any, settings: Any, tmp_path: Path
) -> None:
    settings.QA_DEV_MODE_ALLOWED = True
    settings.QA_DEV_MODE_SNAPSHOT_DIR = str(tmp_path / "snapshots")
    reset_qa_dataset(regression)
    initial_data = {
        model._meta.label: serializers.serialize(
            "json", model._base_manager.order_by("pk"), cls=SnapshotJSONEncoder
        )
        for model in _reset_models()
    }
    enable_qa_dev_mode(
        EnableQaDevModeCommand(actor=regression.actor, note="Regression initial baseline")
    )
    empty = get_user_model().objects.get(email=regression.regression_accounts.user3)
    initial_time = apps.get_model("platform_core", "QaDevModeState").objects.get().current_time
    advance_qa_dev_mode_time(AdvanceQaDevModeTimeCommand(actor=regression.actor, days=1))
    create_qa_opening_balance(
        actor=regression.actor,
        investor_user_id=str(empty.pk),
        currency_code="CHF",
        reset_id=uuid4(),
        amount_minor=12345,
    )
    revert_qa_dev_mode(RevertQaDevModeCommand(actor=regression.actor, confirmation="REVERT QA DB"))
    assert (
        not apps.get_model("ledger", "InvestorBalanceLot")
        .objects.filter(investor_user_id=empty.pk)
        .exists()
    )
    assert apps.get_model("loans", "Loan").objects.count() == 20
    state = apps.get_model("platform_core", "QaDevModeState").objects.get()
    assert state.is_enabled
    seed_time = state.current_time
    assert seed_time == initial_time
    create_qa_opening_balance(
        actor=regression.actor,
        investor_user_id=str(empty.pk),
        currency_code="EUR",
        reset_id=uuid4(),
        amount_minor=9876,
    )
    revert_qa_dev_mode(RevertQaDevModeCommand(actor=regression.actor, confirmation="REVERT QA DB"))
    state.refresh_from_db()
    assert state.is_enabled and state.current_time == seed_time
    assert {
        model._meta.label: serializers.serialize(
            "json", model._base_manager.order_by("pk"), cls=SnapshotJSONEncoder
        )
        for model in _reset_models()
    } == initial_data
    assert (
        not apps.get_model("ledger", "InvestorBalanceLot")
        .objects.filter(investor_user_id=empty.pk)
        .exists()
    )
    cache.clear()


@pytest.mark.parametrize("amount", [0, -1, 1.5, True])
def test_opening_balance_rejects_invalid_amount(regression: Any, amount: Any) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        create_qa_opening_balance(
            actor=regression.actor,
            investor_user_id=str(regression.actor.pk),
            currency_code="CHF",
            reset_id=uuid4(),
            amount_minor=amount,
        )
