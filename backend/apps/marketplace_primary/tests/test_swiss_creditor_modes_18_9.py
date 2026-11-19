"""IP of Webby-Soft SRL. 18.9 (Q03, F06-F09, E-02, E-03): Swiss creditor modes.

Replaces the 20-investor rule of MKT-DEC-028. One mode per borrower UID, pre-selected sandbox:
sandbox = total below CHF 500,000 and no creditor limit; 10/20 = at most 10 creditors per
financing and 20 per borrower. Dynamic minimum where a limit applies:
min(R, max(minimum, round up to whole units of max(0, P - F) / N)).
"""

from __future__ import annotations

from datetime import timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.marketplace_primary import creditor_regime as regimes
from backend.apps.marketplace_primary.investor_limit import loan_investor_limit
from backend.apps.marketplace_primary.services import (
    AllocatePrimaryInvestmentOrderCommand,
    CreatePrimaryInvestmentOrderCommand,
    MarketplacePrimarySwissInvestorLimitError,
    MarketplacePrimaryValidationError,
    allocate_primary_order_from_balance,
    create_primary_investment_order,
)
from backend.apps.marketplace_primary.tests.test_primary_marketplace import (
    _approve_financial_access,
    _create_and_allocate_order,
    _create_primary_acceptance,
    _create_published_loan,
    _declare_deposit,
    _sandbox_ack,
    _sensitive_code_payload,
)
from backend.apps.platform_core.domain import creditor_regime as rules
from backend.apps.platform_core.domain.investor_limit import InvestorLimit
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.tests.creditor_mode_helpers import (  # noqa: F401
    restore_limits,
    set_swiss_creditor_mode,
)

# The admin services of the modes live in the entities app (no static import between domain apps).
_entities_regimes: Any = import_module("backend.apps.entities.creditor_regime")
RecordExternalDebtCommand = _entities_regimes.RecordExternalDebtCommand
SetCreditorModeCommand = _entities_regimes.SetCreditorModeCommand
record_external_debt = _entities_regimes.record_external_debt
record_snb_rate = _entities_regimes.record_snb_rate
set_creditor_mode = _entities_regimes.set_creditor_mode
BorrowerValidationError = import_module("backend.apps.entities.services").BorrowerValidationError


@pytest.fixture
def admin_user(db: None) -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="creditor-admin@example.test",
            password="AdminPass123!",
            full_name="Creditor Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


def _lender(name: str) -> Model:
    user_model: Any = get_user_model()
    lender = cast(
        Model,
        user_model.objects.create_user(
            email=f"creditor-{name}@example.test",
            full_name=f"Creditor {name}",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    _approve_financial_access(lender)
    return lender


def _uid(loan: Model) -> str:
    return str(
        apps.get_model("entities", "BorrowerEntity").objects.get(pk=cast(Any, loan).borrower_id).uid
    )


def _invest(admin_user: Model, investor: Model, loan: Model, amount_minor: int, key: str) -> Any:
    _declare_deposit(admin_user, investor, amount_minor=amount_minor, idempotency_key=f"{key}-d")
    return _create_and_allocate_order(
        investor=investor, loan=loan, amount_minor=amount_minor, idempotency_prefix=key
    )


# The rules --------------------------------------------------------------------------------


def test_uid_normalization_and_check_digit() -> None:
    assert rules.normalize_uid("CHE-302.757.239") == "CHE-302.757.239"
    assert rules.normalize_uid("che302757239 MWST") == "CHE-302.757.239"
    with pytest.raises(rules.CreditorRegimeError, match="check digit"):
        rules.normalize_uid("CHE-302.757.238")
    with pytest.raises(rules.CreditorRegimeError, match="Swiss UID"):
        rules.normalize_uid("DE123456789")


@pytest.mark.parametrize(
    ("remaining", "threshold", "allocated", "places", "expected"),
    [
        # 50,000.00 still missing to the threshold over 10 places: 5,000.00 each.
        (100_000_00, 50_000_00, 0, 10, 5_000_00),
        # Threshold reached: the usual minimum.
        (100_000_00, 50_000_00, 50_000_00, 10, 1_000_00),
        # 10,000.50 / 2 = 5,000.25, rounded up to whole francs.
        (100_000_00, 10_000_50, 0, 2, 5_001_00),
        # Never above what is still open.
        (3_000_00, 50_000_00, 0, 1, 3_000_00),
        # No place left: no new creditor.
        (100_000_00, 50_000_00, 0, 0, None),
    ],
)
def test_dynamic_minimum(
    remaining: int, threshold: int, allocated: int, places: int, expected: int | None
) -> None:
    assert (
        rules.dynamic_minimum_minor(
            usual_minimum_minor=1_000_00,
            remaining_minor=remaining,
            threshold_minor=threshold,
            allocated_minor=allocated,
            places_left=places,
        )
        == expected
    )


def test_a_resale_checks_the_financing_and_the_borrower_counts_separately() -> None:
    # Financing 2/2 full, borrower 3/3 full; the seller s1 leaves this financing.
    limit = InvestorLimit(
        max_investors=2,
        investor_ids=frozenset({"s1", "s2"}),
        borrower_creditor_ids=frozenset({"s1", "s2", "x"}),
        borrower_max_creditors=3,
    )
    # The seller keeps a holding in another financing: the buyer would be a 4th creditor.
    assert limit.transfer_refused(
        buyer_user_id="new", seller_stays_investor=False, seller_stays_borrower_creditor=True
    )
    # The seller leaves the borrower too: the buyer takes the place in both counts.
    assert not limit.transfer_refused(
        buyer_user_id="new", seller_stays_investor=False, seller_stays_borrower_creditor=False
    )
    # A buyer already a creditor of the borrower (x) needs only the financing place.
    assert not limit.transfer_refused(
        buyer_user_id="x", seller_stays_investor=False, seller_stays_borrower_creditor=True
    )
    # The seller keeps a holding in this financing: no free place for a new creditor.
    assert limit.transfer_refused(buyer_user_id="x", seller_stays_investor=True)


# Publication, totals and modes ---------------------------------------------------------------


@pytest.mark.django_db
def test_publication_needs_a_uid_and_confirms_the_pre_selected_sandbox_mode(
    admin_user: Model,
) -> None:
    loan = _create_published_loan(admin_user, principal_minor=200_000_00)
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    borrower_model.objects.filter(pk=cast(Any, loan).borrower_id).update(uid="")
    with pytest.raises(regimes.CreditorRegimeViolation, match="UID"):
        regimes.check_publication(loan, actor=admin_user, on=business_date(timezone.now()))

    borrower_model.objects.filter(pk=cast(Any, loan).borrower_id).update(uid="CHE-123.456.788")
    regimes.check_publication(loan, actor=admin_user, on=business_date(timezone.now()))
    regime = apps.get_model("entities", "SwissCreditorRegime").objects.get(uid="CHE-123.456.788")
    assert regime.mode == "sandbox"
    assert regime.confirmed_by_admin_id == cast(Any, admin_user).pk


@pytest.mark.django_db
def test_production_refuses_a_sandbox_publication_until_the_notice_is_approved(
    admin_user: Model, settings: Any
) -> None:
    loan = _create_published_loan(admin_user, principal_minor=100_000_00)
    today = business_date(timezone.now())
    settings.IS_PRODUCTION = True
    with pytest.raises(regimes.CreditorRegimeViolation, match="not approved"):
        regimes.check_publication(loan, actor=admin_user, on=today)
    import_module("backend.apps.platform_core.models").PlatformSetting.objects.update_or_create(
        key=rules.SANDBOX_NOTICE_APPROVED_SETTING, defaults={"value": True, "value_type": "json"}
    )
    regimes.check_publication(loan, actor=admin_user, on=today)


@pytest.mark.django_db
def test_sandbox_total_stays_below_chf_500000_with_loans_debts_and_eur_at_the_snb_rate(
    admin_user: Model,
) -> None:
    today = business_date(timezone.now())
    first = _create_published_loan(admin_user, principal_minor=300_000_00)
    uid = _uid(first)
    second = _create_published_loan(admin_user, principal_minor=150_000_00, currency_code="EUR")
    apps.get_model("entities", "BorrowerEntity").objects.filter(
        pk=cast(Any, second).borrower_id
    ).update(uid=uid)

    with pytest.raises(regimes.CreditorRegimeViolation, match="SNB reference rate"):
        regimes.borrower_total_chf_minor(uid, on=today)
    record_snb_rate(
        actor=admin_user, currency="EUR", rate_date=today, chf_per_unit="0.95", source="SNB"
    )
    # 300,000 CHF + 150,000 EUR x 0.95 = 442,500 CHF.
    assert regimes.borrower_total_chf_minor(uid, on=today) == 442_500_00
    regimes.check_before_close(second, on=today)

    # A bank debt counts in the total (not in the creditor counts): 442,500 + 60,000 >= 500,000.
    record_external_debt(
        RecordExternalDebtCommand(
            actor=admin_user,
            uid=uid,
            creditor_name="Cantonal Bank",
            creditor_identification="CHE-116.281.710",
            creditor_is_bank=True,
            financing_id="KB-2026-1",
            principal_minor=60_000_00,
            currency="CHF",
            start_date=today,
            declaration_reference="Signed declaration 2026-11",
        )
    )
    with pytest.raises(regimes.CreditorRegimeViolation, match="below CHF 500,000"):
        regimes.check_before_close(second, on=today)


@pytest.mark.django_db
def test_switching_modes_follows_the_limits_and_never_during_funding(admin_user: Model) -> None:
    loan = _create_published_loan(admin_user, principal_minor=100_000_00)
    uid = _uid(loan)
    with pytest.raises(BorrowerValidationError, match="in funding"):
        set_creditor_mode(SetCreditorModeCommand(actor=admin_user, uid=uid, mode="ten_twenty"))
    cast(Any, loan).status = "active"
    cast(Any, loan).save(update_fields=["status"])
    regime = set_creditor_mode(
        SetCreditorModeCommand(actor=admin_user, uid=uid, mode="ten_twenty", note="WW memo 12")
    )
    assert regime.mode == "ten_twenty" and regime.confirmation_note == "WW memo 12"
    events = apps.get_model("entities", "BorrowerEntityEvent").objects.filter(
        borrower_id=cast(Any, loan).borrower_id, event_type="creditor_mode_changed"
    )
    assert events.count() == 1


# 10/20 mode: places, minimum, refusals -------------------------------------------------------


@pytest.mark.django_db
def test_ten_twenty_places_and_the_dynamic_minimum_from_the_threshold(admin_user: Model) -> None:
    loan = _create_published_loan(admin_user, principal_minor=100_000_00)
    set_swiss_creditor_mode(financing_limit=3)
    limit = loan_investor_limit(loan)
    assert (limit.max_investors, limit.places_left) == (3, 3)
    # P = 50% of 100,000 = 50,000 missing over 3 places: 16,667.00 (whole francs, rounded up).
    assert (
        limit.investor_minimum_minor(
            investor_user_id=None, minimum_minor=1_000_00, remaining_minor=100_000_00
        )
        == 16_667_00
    )

    first = _lender("first")
    _invest(admin_user, first, loan, 20_000_00, "tt-first")
    limit = loan_investor_limit(loan)
    # 30,000 still missing over 2 places; the investor already in adds with the usual minimum.
    assert (
        limit.investor_minimum_minor(
            investor_user_id=None, minimum_minor=1_000_00, remaining_minor=80_000_00
        )
        == 15_000_00
    )
    assert (
        limit.investor_minimum_minor(
            investor_user_id=str(cast(Any, first).pk),
            minimum_minor=1_000_00,
            remaining_minor=80_000_00,
        )
        == 1_000_00
    )


@pytest.mark.django_db
def test_a_full_financing_refuses_a_new_creditor_and_the_borrower_limit_counts_once(
    admin_user: Model,
) -> None:
    loan = _create_published_loan(admin_user, principal_minor=100_000_00)
    other = _create_published_loan(admin_user, principal_minor=100_000_00)
    uid = _uid(loan)
    apps.get_model("entities", "BorrowerEntity").objects.filter(
        pk=cast(Any, other).borrower_id
    ).update(uid=uid)
    set_swiss_creditor_mode(financing_limit=2)
    rules.BORROWER_CREDITOR_LIMIT = 3
    a, b, c = _lender("a"), _lender("b"), _lender("c")
    _invest(admin_user, a, loan, 30_000_00, "full-a")
    _invest(admin_user, b, loan, 30_000_00, "full-b")
    # The financing is full: a new creditor is refused already when ordering (409 code path).
    with pytest.raises(MarketplacePrimarySwissInvestorLimitError, match="no place left"):
        create_primary_investment_order(
            CreatePrimaryInvestmentOrderCommand(
                actor=c,
                loan_id=str(cast(Any, loan).pk),
                amount_minor=30_000_00,
                idempotency_key="c",
            )
        )
    # In the borrower's other financing, a and b are already creditors of the UID (counted once);
    # c would be the 3rd creditor of the borrower: still allowed (limit lowered to 3).
    limit = loan_investor_limit(other)
    assert limit.places_left_for(str(cast(Any, c).pk)) == 1
    assert limit.places_left_for(str(cast(Any, a).pk)) == 2


# Sandbox notice -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_sandbox_borrower_needs_the_notice_confirmation_with_its_version(
    admin_user: Model,
) -> None:
    loan = _create_published_loan(admin_user, principal_minor=100_000_00)
    investor = _lender("notice")
    _declare_deposit(admin_user, investor, amount_minor=5_000_00, idempotency_key="notice-d")
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(cast(Any, loan).pk),
            amount_minor=5_000_00,
            idempotency_key="notice-order",
        )
    )
    acceptance = _create_primary_acceptance(
        investor, order_id=str(order.id), idempotency_key="notice-acc"
    )
    with pytest.raises(MarketplacePrimaryValidationError, match="sandbox notice"):
        allocate_primary_order_from_balance(
            AllocatePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(order.id),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="notice-alloc-1",
                sandbox_notice_confirmed=True,
                sandbox_notice_version="stale-version",
                **_sensitive_code_payload(investor, "primary_investment"),
            )
        )
    allocated = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="notice-alloc-2",
            **_sandbox_ack(order),
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )
    assert (
        allocated.metadata["sandbox_notice_version"]
        == _sandbox_ack(order)["sandbox_notice_version"]
    )

    client = Client()
    client.force_login(cast(Any, investor))
    payload = client.get(f"/api/v1/marketplace/primary/loans/{cast(Any, loan).pk}/").json()
    assert payload["creditor_mode"] == "sandbox"
    assert "not supervised by FINMA" in payload["sandbox_notice"]["text"]


@pytest.mark.django_db
def test_admin_api_shows_and_changes_the_mode_and_records_debts_and_rates(
    admin_user: Model,
) -> None:
    loan = _create_published_loan(admin_user, principal_minor=100_000_00)
    cast(Any, loan).status = "active"
    cast(Any, loan).save(update_fields=["status"])
    uid = _uid(loan)
    client = Client()
    client.force_login(cast(Any, admin_user))
    overview = client.get(f"/api/v1/entities/admin/creditor-modes/{uid}/")
    assert overview.status_code == 200, overview.content
    assert overview.json()["mode"] == "sandbox"
    changed = client.post(
        f"/api/v1/entities/admin/creditor-modes/{uid}/",
        {"mode": "ten_twenty", "note": "Confirmed with the borrower"},
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content
    assert changed.json()["mode"] == "ten_twenty" and changed.json()["confirmed"] is True
    debt = client.post(
        f"/api/v1/entities/admin/creditor-modes/{uid}/external-debts/",
        {
            "creditor_name": "Private lender",
            "creditor_identification": "CHE-109.322.551",
            "financing_id": "PL-1",
            "principal_minor": 20_000_00,
            "currency": "CHF",
            "start_date": str(business_date(timezone.now()) - timedelta(days=30)),
            "declaration_reference": "Declaration 7",
        },
        content_type="application/json",
    )
    assert debt.status_code == 201, debt.content
    # A non-bank external creditor counts as a creditor of the borrower.
    assert debt.json()["borrower_creditors"] == 1
    rate = client.post(
        "/api/v1/entities/admin/snb-rates/",
        {
            "currency": "EUR",
            "rate_date": str(business_date(timezone.now())),
            "chf_per_unit": "0.9412",
            "source": "SNB",
        },
        content_type="application/json",
    )
    assert rate.status_code == 201, rate.content
    import_module("backend.apps.platform_core.models").SnbReferenceRate.objects.get(currency="EUR")
