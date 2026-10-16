# IP of Webby-Soft SRL.
"""Swiss-borrower loans: at most 20 investors (owner decision 2026-10-16, MKT-DEC-028)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.marketplace_primary import services as marketplace_services
from backend.apps.marketplace_primary.investor_limit import (
    loan_investor_ids,
    loan_investor_limit,
    swiss_borrower_max_investors,
)
from backend.apps.marketplace_primary.models import (
    PrimaryInvestmentOrder,
    PrimaryInvestmentOrderStatus,
)
from backend.apps.marketplace_primary.services import (
    AllocatePrimaryInvestmentOrderCommand,
    CreatePrimaryInvestmentOrderCommand,
    MarketplacePrimarySwissInvestorLimitError,
    MarketplacePrimaryValidationError,
    PlacePrimaryOrderBatchCommand,
    PrimaryOrderBatchItemCommand,
    allocate_primary_order_from_balance,
    create_primary_investment_order,
    get_full_marketplace_loan,
    list_investor_marketplace_loans,
    place_primary_order_batch,
)
from backend.apps.marketplace_primary.tests.test_primary_marketplace import (
    _approve_financial_access,
    _create_and_allocate_order,
    _create_originator_batch_loan,
    _create_primary_acceptance,
    _create_published_loan,
    _declare_deposit,
    _sensitive_code_payload,
)
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.countries import is_switzerland
from backend.apps.platform_core.domain.investor_limit import (
    SWISS_BORROWER_MAX_INVESTORS_SETTING,
    SWISS_INVESTOR_LIMIT_CODE,
    InvestorLimit,
    new_investor_minimum_minor,
)
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.services.settings import (
    SetPlatformSettingCommand,
    set_platform_setting,
)
from backend.apps.platform_core.tests.factories import issue_sensitive_action_test_code

# Loan Originator claims are a peer module: reached at run time (import boundaries).
originator: Any = import_module("backend.apps.originator_claims.services")
originator_tests: Any = import_module("backend.apps.originator_claims.tests.test_originator_claims")

PROJECTS_URL = "/api/v1/marketplace/primary/public/projects/"
ORDERS_URL = "/api/v1/marketplace/primary/orders/"
FULL_MESSAGE = "This loan to a Swiss company already has the maximum of {} investors."


@pytest.fixture(autouse=True)
def _clear_public_site_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="swiss-limit-admin@example.test",
            password="AdminPass123!",
            full_name="Swiss Limit Admin",
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
            email=f"swiss-limit-{name}@example.test",
            full_name=f"Swiss Limit {name}",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )
    _approve_financial_access(lender)
    return lender


def _set_limit(value: int) -> None:
    set_platform_setting(
        SetPlatformSettingCommand(
            actor=ActorRef.system(),
            key=SWISS_BORROWER_MAX_INVESTORS_SETTING,
            value=value,
            value_type="integer",
            reason="Swiss-borrower investor limit test.",
        )
    )


def _invest(admin_user: Model, investor: Model, loan: Model, amount_minor: int, key: str) -> Any:
    _declare_deposit(admin_user, investor, amount_minor=amount_minor, idempotency_key=f"{key}-dep")
    return _create_and_allocate_order(
        investor=investor,
        loan=loan,
        amount_minor=amount_minor,
        idempotency_prefix=key,
    )


def _order(investor: Model, loan: Model, amount_minor: int, key: str) -> PrimaryInvestmentOrder:
    return create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=amount_minor,
            idempotency_key=key,
        )
    )


def _swiss_loan(admin_user: Model, *, principal_minor: int = 100_000_00) -> Any:
    return cast(Any, _create_published_loan(admin_user, principal_minor=principal_minor))


def _committed(loan: Model) -> int:
    loan.refresh_from_db()
    return int(cast(Any, loan).committed_principal_minor)


# The rule ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("minimum", "remaining", "places_left", "expected"),
    [
        # 100,000.00 over 20 places: 5,000.00 each.
        (1_000_00, 100_000_00, 20, 5_000_00),
        # 80,000.00 / 19 = 4,210.53, rounded up to whole francs.
        (1_000_00, 80_000_00, 19, 4_211_00),
        # The loan minimum stays when the share is lower.
        (1_000_00, 10_000_00, 20, 1_000_00),
        # 10,000.50 / 2 = 5,000.25, rounded up to 5,001.00.
        (1_000_00, 10_000_50, 2, 5_001_00),
        # The last place takes the rest, exactly, even when not whole francs.
        (1_000_00, 10_000_50, 1, 10_000_50),
        # Never above the remaining capacity, even below the loan minimum.
        (1_000_00, 400_00, 5, 400_00),
        # No place left: no new investor.
        (1_000_00, 50_000_00, 0, None),
    ],
)
def test_minimum_for_a_new_investor(
    minimum: int,
    remaining: int,
    places_left: int,
    expected: int | None,
) -> None:
    assert (
        new_investor_minimum_minor(
            minimum_minor=minimum,
            remaining_minor=remaining,
            places_left=places_left,
        )
        == expected
    )


def test_investor_limit_places_existing_investors_and_transfers() -> None:
    full = InvestorLimit(max_investors=2, investor_ids=frozenset({"a", "b"}))
    assert full.applies and full.investors_count == 2 and full.places_left == 0
    assert full.refuses_new_investor("c")
    assert not full.refuses_new_investor("a")
    # An existing investor keeps the normal minimum, capped by the remaining capacity.
    assert full.investor_minimum_minor(
        investor_user_id="a", minimum_minor=1_000_00, remaining_minor=40_000_00
    ) == (1_000_00)
    assert full.investor_minimum_minor(
        investor_user_id="a", minimum_minor=1_000_00, remaining_minor=400_00
    ) == (400_00)
    # A buyer takes the place of a seller who sells their last holding.
    assert not full.transfer_refused(buyer_user_id="c", seller_stays_investor=False)
    assert full.transfer_refused(buyer_user_id="c", seller_stays_investor=True)
    assert not full.transfer_refused(buyer_user_id="b", seller_stays_investor=True)
    # Over the limit (limit lowered later): never more, but a seller can still be replaced.
    over = InvestorLimit(max_investors=1, investor_ids=frozenset({"a", "b"}))
    assert over.places_left == 0
    assert not over.transfer_refused(buyer_user_id="c", seller_stays_investor=False)

    no_limit = InvestorLimit(max_investors=None, investor_ids=frozenset({"a"}))
    assert not no_limit.applies and no_limit.places_left is None
    assert not no_limit.refuses_new_investor("c")
    assert no_limit.investor_minimum_minor(
        investor_user_id=None, minimum_minor=1_000_00, remaining_minor=400_00
    ) == (1_000_00)


@pytest.mark.parametrize(
    ("country", "swiss"),
    [
        ("Switzerland", True),
        ("CH", True),
        (" ch ", True),
        ("Schweiz", True),
        ("Suisse", True),
        ("Svizzera", True),
        ("Germany", False),
        ("DE", False),
        ("", False),
        ("Swaziland", False),
    ],
)
def test_swiss_country_spellings(country: str, swiss: bool) -> None:
    assert is_switzerland(country) is swiss


# Which loans, which investors -------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("country", ["Switzerland", "CH", "Schweiz", "Suisse", "ch"])
def test_direct_loans_to_swiss_borrowers_get_the_limit(admin_user: Model, country: str) -> None:
    loan = cast(Any, _create_published_loan(admin_user, borrower_country=country))
    limit = loan_investor_limit(loan)
    assert limit.max_investors == 20
    assert limit.places_left == 20


@pytest.mark.django_db
def test_other_borrowers_and_setting_zero_have_no_limit(admin_user: Model) -> None:
    german = cast(Any, _create_published_loan(admin_user, borrower_country="Germany"))
    swiss = _swiss_loan(admin_user)
    assert swiss_borrower_max_investors() == 20
    assert loan_investor_limit(german).max_investors is None

    _set_limit(0)
    assert loan_investor_limit(swiss).max_investors is None
    investor = _lender("setting-off")
    # The launch minimum applies again: no raised minimum, no place to count.
    order = _order(investor, swiss, 1_000_00, "swiss-setting-off-order")
    assert order.status == PrimaryInvestmentOrderStatus.PENDING
    payload = get_full_marketplace_loan(actor=investor, loan_id=str(swiss.pk))
    assert payload["minimum_investment_minor"] == 1_000_00
    assert payload["max_investors"] is None
    assert payload["places_left"] is None
    assert payload["is_existing_investor"] is None


@pytest.mark.django_db
def test_investors_are_holders_and_investors_with_allocated_money(admin_user: Model) -> None:
    loan = _swiss_loan(admin_user)
    first, second, pending = _lender("set-1"), _lender("set-2"), _lender("set-3")
    _invest(admin_user, first, loan, 10_000_00, "swiss-set-1")
    _invest(admin_user, second, loan, 10_000_00, "swiss-set-2")
    # A pending order is an intent only: it does not count.
    _order(pending, loan, 10_000_00, "swiss-set-pending")

    assert loan_investor_ids([str(loan.pk)])[str(loan.pk)] == {str(first.pk), str(second.pk)}
    # The public investor count uses the same source.
    assert Client().get(f"{PROJECTS_URL}{loan.pk}/").json()["investors_count"] == 2

    # Once holdings exist they are the truth: a transferred holding no longer counts.
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holding_model.objects.create(
        loan=loan,
        investor_user_id=first.pk,
        source_type="manual_admin",
        source_id="swiss-set-transferred",
        status="transferred",
        original_principal_minor=10_000_00,
        current_principal_minor=10_000_00,
        currency=loan.currency,
        loan_share_ppm=100_000,
        assignment_effective_at=timezone.now(),
        created_by_admin_id=admin_user.pk,
        idempotency_key="swiss-set-transferred",
    )
    PrimaryInvestmentOrder.objects.filter(loan_id=loan.pk).exclude(
        investor_user_id=pending.pk
    ).update(status=PrimaryInvestmentOrderStatus.CLOSED_INVESTED)
    assert loan_investor_ids([str(loan.pk)])[str(loan.pk)] == frozenset()


# Primary orders ---------------------------------------------------------------------


@pytest.mark.django_db
def test_new_investor_minimum_on_a_swiss_loan_and_launch_minimum_elsewhere(
    client: Client,
    admin_user: Model,
) -> None:
    swiss = _swiss_loan(admin_user)
    german = cast(Any, _create_published_loan(admin_user, borrower_country="DE"))
    investor = _lender("minimum")

    with pytest.raises(
        MarketplacePrimaryValidationError,
        match="minimum for a new investor is now CHF 5'000.00",
    ):
        _order(investor, swiss, 4_999_00, "swiss-minimum-low")
    assert _order(investor, swiss, 5_000_00, "swiss-minimum-ok").requested_amount_minor == (
        5_000_00
    )
    assert _order(investor, german, 1_000_00, "swiss-minimum-german").requested_amount_minor == (
        1_000_00
    )

    # The investor marketplace reports the minimum and the places.
    client.force_login(cast(Any, investor))
    rows = {
        row["loan_id"]: row
        for row in client.get("/api/v1/marketplace/primary/opportunities/").json()
    }
    assert rows[str(swiss.pk)]["minimum_investment_minor"] == 5_000_00
    assert rows[str(swiss.pk)]["max_investors"] == 20
    assert rows[str(swiss.pk)]["places_left"] == 20
    assert rows[str(swiss.pk)]["is_existing_investor"] is False
    assert rows[str(german.pk)]["minimum_investment_minor"] == 1_000_00
    assert rows[str(german.pk)]["max_investors"] is None
    assert rows[str(german.pk)]["places_left"] is None
    detail = client.get(f"/api/v1/marketplace/primary/loans/{swiss.pk}/").json()
    assert detail["minimum_investment_minor"] == 5_000_00
    assert detail["places_left"] == 20


@pytest.mark.django_db
def test_minimum_rises_as_places_fill_so_the_last_place_fills_the_loan(
    admin_user: Model,
) -> None:
    _set_limit(3)
    loan = _swiss_loan(admin_user)
    first, second, third, late = (_lender(f"fill-{index}") for index in range(4))

    # 100,000.00 / 3 = 33,333.34, rounded up to 33,334.00.
    with pytest.raises(MarketplacePrimaryValidationError, match="CHF 33'334.00"):
        _order(first, loan, 33_333_00, "swiss-fill-1-low")
    _invest(admin_user, first, loan, 33_334_00, "swiss-fill-1")
    # 66,666.00 / 2 = 33,333.00.
    assert get_full_marketplace_loan(actor=second, loan_id=str(loan.pk))[
        "minimum_investment_minor"
    ] == (33_333_00)
    _invest(admin_user, second, loan, 40_000_00, "swiss-fill-2")
    # The last place takes the rest: 26,666.00.
    payload = get_full_marketplace_loan(actor=third, loan_id=str(loan.pk))
    assert payload["minimum_investment_minor"] == 26_666_00
    assert payload["places_left"] == 1
    with pytest.raises(MarketplacePrimaryValidationError, match="CHF 26'666.00"):
        _order(third, loan, 26_000_00, "swiss-fill-3-low")
    _invest(admin_user, third, loan, 26_666_00, "swiss-fill-3")

    assert _committed(loan) == 100_000_00
    # Fully funded: the capacity rule answers first.
    with pytest.raises(MarketplacePrimaryValidationError, match="no remaining investment capacity"):
        _order(late, loan, 1_000_00, "swiss-fill-late")


@pytest.mark.django_db
def test_full_loan_refuses_a_new_investor_and_keeps_existing_investors_in(
    client: Client,
    admin_user: Model,
) -> None:
    loan = _swiss_loan(admin_user)
    first, second, newcomer = _lender("full-1"), _lender("full-2"), _lender("full-new")
    _invest(admin_user, first, loan, 10_000_00, "swiss-full-1")
    _invest(admin_user, second, loan, 10_000_00, "swiss-full-2")
    # The platform limit is lowered to the investors the loan already has.
    _set_limit(2)

    with pytest.raises(MarketplacePrimarySwissInvestorLimitError) as refused:
        _order(newcomer, loan, 40_000_00, "swiss-full-new")
    assert str(refused.value) == FULL_MESSAGE.format(2)
    assert refused.value.code == SWISS_INVESTOR_LIMIT_CODE

    client.force_login(cast(Any, newcomer))
    response = client.post(
        ORDERS_URL,
        data={"loan_id": str(loan.pk), "amount_minor": 40_000_00, "idempotency_key": "swiss-api"},
        content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json() == {"detail": FULL_MESSAGE.format(2), "code": SWISS_INVESTOR_LIMIT_CODE}
    newcomer_view = client.get(f"/api/v1/marketplace/primary/loans/{loan.pk}/").json()
    assert newcomer_view["places_left"] == 0
    assert newcomer_view["is_existing_investor"] is False

    # An existing investor does not need a new place: the normal minimum applies.
    payload = get_full_marketplace_loan(actor=first, loan_id=str(loan.pk))
    assert payload["is_existing_investor"] is True
    assert payload["minimum_investment_minor"] == 1_000_00
    _invest(admin_user, first, loan, 1_000_00, "swiss-full-1-again")
    assert _committed(loan) == 21_000_00
    # ... capped by the remaining capacity.
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.filter(pk=loan.pk).update(committed_principal_minor=100_000_00 - 400_00)
    assert get_full_marketplace_loan(actor=second, loan_id=str(loan.pk))[
        "minimum_investment_minor"
    ] == (400_00)
    assert _order(second, loan, 400_00, "swiss-full-2-rest").requested_amount_minor == 400_00
    with pytest.raises(MarketplacePrimarySwissInvestorLimitError):
        _order(newcomer, loan, 400_00, "swiss-full-new-rest")


@pytest.mark.django_db
def test_allocation_refuses_a_new_investor_who_lost_the_last_place(admin_user: Model) -> None:
    loan = _swiss_loan(admin_user)
    first, second, late = _lender("alloc-1"), _lender("alloc-2"), _lender("alloc-late")
    _invest(admin_user, first, loan, 10_000_00, "swiss-alloc-1")
    _declare_deposit(admin_user, second, amount_minor=90_000_00, idempotency_key="swiss-alloc-2")
    _declare_deposit(admin_user, late, amount_minor=90_000_00, idempotency_key="swiss-alloc-3")
    # Two new investors place orders while one place is left (the minimum is the rest).
    _set_limit(2)
    second_order = _order(second, loan, 90_000_00, "swiss-alloc-2-order")
    late_order = _order(late, loan, 90_000_00, "swiss-alloc-3-order")
    second_acceptance = _create_primary_acceptance(
        second, order_id=str(second_order.id), idempotency_key="swiss-alloc-2-accept"
    )
    late_acceptance = _create_primary_acceptance(
        late, order_id=str(late_order.id), idempotency_key="swiss-alloc-3-accept"
    )
    # The first to confirm takes the last place.
    allocated = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=second,
            order_id=str(second_order.id),
            document_acceptance_id=str(second_acceptance.pk),
            idempotency_key="swiss-alloc-2-allocate",
            **_sensitive_code_payload(second, "primary_investment"),
        )
    )
    assert allocated.status == PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED
    # Capacity comes back (for example a released reservation), so only the place
    # decides: the second new investor is refused.
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.filter(pk=loan.pk).update(committed_principal_minor=20_000_00)
    late_code = issue_sensitive_action_test_code(late, "primary_investment")
    with pytest.raises(MarketplacePrimarySwissInvestorLimitError):
        allocate_primary_order_from_balance(
            AllocatePrimaryInvestmentOrderCommand(
                actor=late,
                order_id=str(late_order.id),
                document_acceptance_id=str(late_acceptance.pk),
                idempotency_key="swiss-alloc-3-allocate",
                sensitive_action_code_id=late_code.code_id,
                sensitive_action_code=late_code.raw_code,
                pin=late_code.pin,
            )
        )
    # The early check refused before the email code was used; the order stays pending.
    late_order.refresh_from_db()
    assert late_order.status == PrimaryInvestmentOrderStatus.PENDING
    assert late_order.allocated_amount_minor == 0
    code_model = apps.get_model("accounts_auth", "SensitiveActionCode")
    assert code_model.objects.get(id=late_code.code_id).consumed_at is None
    # The authoritative check under the loan lock refuses too.
    with pytest.raises(MarketplacePrimarySwissInvestorLimitError):
        marketplace_services._allocate_primary_order_from_balance_after_sensitive_code(
            AllocatePrimaryInvestmentOrderCommand(
                actor=late,
                order_id=str(late_order.id),
                document_acceptance_id=str(late_acceptance.pk),
                idempotency_key="swiss-alloc-3-allocate-locked",
            )
        )
    assert loan_investor_limit(loan).investors_count == 2


@pytest.mark.django_db
def test_allocation_applies_the_minimum_of_now_to_a_new_investor(admin_user: Model) -> None:
    _set_limit(3)
    loan = _swiss_loan(admin_user)
    first, second, third = _lender("now-1"), _lender("now-2"), _lender("now-3")
    _declare_deposit(admin_user, third, amount_minor=40_000_00, idempotency_key="swiss-now-3")
    # Minimum 33,334.00 while three places are left.
    third_order = _order(third, loan, 34_000_00, "swiss-now-3-order")
    _invest(admin_user, first, loan, 33_334_00, "swiss-now-1")
    _invest(admin_user, second, loan, 33_334_00, "swiss-now-2")
    # One place is left: the minimum is now the rest, 33,332.00, and 34,000.00 covers it.
    acceptance = _create_primary_acceptance(
        third, order_id=str(third_order.id), idempotency_key="swiss-now-3-accept"
    )
    allocated = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=third,
            order_id=str(third_order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="swiss-now-3-allocate",
            **_sensitive_code_payload(third, "primary_investment"),
        )
    )
    assert allocated.allocated_amount_minor == 33_332_00
    assert _committed(loan) == 100_000_00

    # An order below the minimum of now is refused at confirmation; nothing moves.
    other = _swiss_loan(admin_user)
    early, joiner = _lender("now-early"), _lender("now-joiner")
    _declare_deposit(admin_user, early, amount_minor=40_000_00, idempotency_key="swiss-now-e")
    early_order = _order(early, other, 34_000_00, "swiss-now-early-order")
    _invest(admin_user, joiner, other, 40_000_00, "swiss-now-joiner")
    _set_limit(2)
    early_acceptance = _create_primary_acceptance(
        early, order_id=str(early_order.id), idempotency_key="swiss-now-early-accept"
    )
    with pytest.raises(MarketplacePrimaryValidationError, match="CHF 60'000.00") as refused:
        allocate_primary_order_from_balance(
            AllocatePrimaryInvestmentOrderCommand(
                actor=early,
                order_id=str(early_order.id),
                document_acceptance_id=str(early_acceptance.pk),
                idempotency_key="swiss-now-early-allocate",
                **_sensitive_code_payload(early, "primary_investment"),
            )
        )
    assert "Nothing was invested" in str(refused.value)
    early_order.refresh_from_db()
    assert early_order.status == PrimaryInvestmentOrderStatus.PENDING
    assert _committed(other) == 40_000_00


# Smart-Invest batch -----------------------------------------------------------------


def _batch(investor: Model, items: list[tuple[Model, int]], key: str) -> Any:
    batch_items = [
        PrimaryOrderBatchItemCommand(loan_id=str(loan.pk), amount_minor=amount)
        for loan, amount in items
    ]
    acceptance = _create_primary_acceptance(
        investor,
        order_id="",
        idempotency_key=f"{key}-accept",
        context_type="primary_order_batch",
        context_id=key,
        data_snapshot={
            "currency": "CHF",
            "items": [
                {"loan_id": item.loan_id, "amount_minor": item.amount_minor} for item in batch_items
            ],
        },
    )
    return place_primary_order_batch(
        PlacePrimaryOrderBatchCommand(
            actor=investor,
            items=batch_items,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=key,
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )


@pytest.mark.django_db
def test_batch_lines_use_the_new_investor_minimum_and_a_full_loan_refuses_the_batch(
    client: Client,
    admin_user: Model,
) -> None:
    swiss = _swiss_loan(admin_user, principal_minor=40_000_00)
    german = cast(Any, _create_published_loan(admin_user, borrower_country="DE"))
    investor = _lender("batch")
    _declare_deposit(admin_user, investor, amount_minor=20_000_00, idempotency_key="swiss-batch")

    # 40,000.00 / 20 = 2,000.00 for a new investor.
    with pytest.raises(MarketplacePrimaryValidationError, match="CHF 2'000.00") as low:
        _batch(investor, [(swiss, 1_500_00), (german, 1_000_00)], "swiss-batch-low")
    assert "Real estate bridge loan: " in str(low.value)
    assert "Nothing was committed" in str(low.value)
    assert not PrimaryInvestmentOrder.objects.filter(investor_user_id=investor.pk).exists()

    first, second = _lender("batch-1"), _lender("batch-2")
    _invest(admin_user, first, swiss, 2_000_00, "swiss-batch-1")
    _invest(admin_user, second, swiss, 2_000_00, "swiss-batch-2")
    _set_limit(2)
    with pytest.raises(MarketplacePrimarySwissInvestorLimitError) as full:
        _batch(investor, [(swiss, 2_000_00), (german, 1_000_00)], "swiss-batch-full")
    assert str(full.value) == f"Real estate bridge loan: {FULL_MESSAGE.format(2)}"
    # Every line rolled back, also the one on the other loan.
    assert not PrimaryInvestmentOrder.objects.filter(investor_user_id=investor.pk).exists()
    assert _committed(german) == 0

    # An existing investor's batch line keeps the normal minimum.
    _declare_deposit(admin_user, first, amount_minor=1_000_00, idempotency_key="swiss-batch-1b")
    placed = _batch(first, [(swiss, 1_000_00)], "swiss-batch-existing")
    assert [order.allocated_amount_minor for order in placed.orders] == [1_000_00]


@pytest.mark.django_db
def test_batch_api_answers_409_for_a_full_swiss_loan(client: Client, admin_user: Model) -> None:
    swiss = _swiss_loan(admin_user, principal_minor=40_000_00)
    first, newcomer = _lender("batch-api-1"), _lender("batch-api-new")
    _invest(admin_user, first, swiss, 2_000_00, "swiss-batch-api-1")
    _set_limit(1)
    key = "swiss-batch-api"
    acceptance = _create_primary_acceptance(
        newcomer,
        order_id="",
        idempotency_key=f"{key}-accept",
        context_type="primary_order_batch",
        context_id=key,
        data_snapshot={
            "currency": "CHF",
            "items": [{"loan_id": str(swiss.pk), "amount_minor": 2_000_00}],
        },
    )
    client.force_login(cast(Any, newcomer))
    response = client.post(
        "/api/v1/marketplace/primary/orders/batch/",
        data={
            "items": [{"loan_id": str(swiss.pk), "amount_minor": 2_000_00}],
            "document_acceptance_id": str(acceptance.pk),
            "idempotency_key": key,
            **_sensitive_code_payload(newcomer, "primary_investment"),
        },
        content_type="application/json",
    )
    assert response.status_code == 409, response.content
    assert response.json()["code"] == SWISS_INVESTOR_LIMIT_CODE


# Loan Originator claims -------------------------------------------------------------


@pytest.mark.django_db
def test_loan_originator_subscription_to_a_swiss_borrower_gets_the_limit(
    admin_user: Model,
) -> None:
    today = business_date(timezone.now())
    result = originator_tests._create_par_subscription_loan(
        admin_user=admin_user, today=today, suffix="SWISS"
    )
    loan = result.loan
    profile_model = apps.get_model("originator_claims", "OriginatorLoanProfile")
    profile_model.objects.filter(loan_id=loan.pk).update(borrower_country="Schweiz")
    _set_limit(2)
    first, second, newcomer = _lender("lo-1"), _lender("lo-2"), _lender("lo-new")

    payload = get_full_marketplace_loan(actor=first, loan_id=str(loan.pk))
    remaining = int(payload["remaining_capacity_minor"])
    expected_minimum = new_investor_minimum_minor(
        minimum_minor=100_000, remaining_minor=remaining, places_left=2
    )
    assert expected_minimum is not None and expected_minimum > 100_000
    assert payload["minimum_investment_minor"] == expected_minimum
    assert payload["max_investors"] == 2
    assert payload["places_left"] == 2
    listed = {row["loan_id"]: row for row in list_investor_marketplace_loans(actor=first)}
    assert listed[str(loan.pk)]["minimum_investment_minor"] == expected_minimum

    with pytest.raises(MarketplacePrimaryValidationError, match="minimum for a new investor"):
        _order(first, loan, 100_000, "swiss-lo-1-low")
    allocated = _invest(admin_user, first, loan, expected_minimum, "swiss-lo-1")
    assert allocated.status == PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED
    # The last place takes the rest of the round.
    rest = int(
        get_full_marketplace_loan(actor=second, loan_id=str(loan.pk))["minimum_investment_minor"]
    )
    assert rest == remaining - expected_minimum
    with pytest.raises(MarketplacePrimaryValidationError, match="minimum for a new investor"):
        _order(second, loan, rest - 100, "swiss-lo-2-low")
    # With no place left the round is closed to new investors.
    _set_limit(1)
    with pytest.raises(MarketplacePrimarySwissInvestorLimitError):
        _order(newcomer, loan, rest, "swiss-lo-new")
    # The existing investor keeps the loan minimum.
    assert get_full_marketplace_loan(actor=first, loan_id=str(loan.pk))[
        "minimum_investment_minor"
    ] == (100_000)
    assert _order(first, loan, 100_000, "swiss-lo-1-more").requested_amount_minor == 100_000


@pytest.mark.django_db
def test_quoted_loan_originator_claim_applies_the_limit_at_quote_and_purchase(
    client: Client,
    admin_user: Model,
) -> None:
    loan = cast(Any, _create_originator_batch_loan(admin_user, suffix="SWISSQ"))
    profile_model = apps.get_model("originator_claims", "OriginatorLoanProfile")
    profile_model.objects.filter(loan_id=loan.pk).update(borrower_country="Suisse")
    first, second, newcomer = _lender("quote-1"), _lender("quote-2"), _lender("quote-new")
    for index, investor in enumerate((first, second, newcomer)):
        _declare_deposit(
            admin_user, investor, amount_minor=20_000_00, idempotency_key=f"swiss-quote-{index}"
        )
    _set_limit(3)

    payload = get_full_marketplace_loan(actor=first, loan_id=str(loan.pk))
    cash_capacity = int(payload["fillable_amount_minor"])
    minimum = new_investor_minimum_minor(
        minimum_minor=100_000, remaining_minor=cash_capacity, places_left=3
    )
    assert minimum is not None and minimum > 100_000
    assert payload["minimum_investment_minor"] == minimum
    with pytest.raises(
        originator.OriginatorClaimsValidationError, match="minimum for a new investor"
    ):
        originator.create_originator_claim_quote(
            originator.CreateOriginatorClaimQuoteCommand(
                actor=first, loan_id=str(loan.pk), requested_cash_minor=100_000
            )
        )

    acceptances: dict[str, Model] = {}

    def buy(investor: Model, requested_cash_minor: int, key: str) -> Any:
        quote = originator.create_originator_claim_quote(
            originator.CreateOriginatorClaimQuoteCommand(
                actor=investor, loan_id=str(loan.pk), requested_cash_minor=requested_cash_minor
            )
        )
        return quote, _purchase(investor, quote, key)

    def _purchase(investor: Model, quote: Any, key: str) -> Any:
        if str(quote.id) not in acceptances:
            acceptances[str(quote.id)] = originator_tests._primary_acceptance(
                investor, quote_id=str(quote.id)
            )
        acceptance = acceptances[str(quote.id)]
        code = issue_sensitive_action_test_code(investor, "primary_investment")
        return originator.purchase_originator_claim(
            originator.PurchaseOriginatorClaimCommand(
                actor=investor,
                quote_id=str(quote.id),
                document_acceptance_id=str(acceptance.pk),
                sensitive_action_code_id=code.code_id,
                sensitive_action_code=code.raw_code,
                pin=code.pin,
                idempotency_key=key,
            )
        )

    buy(first, minimum + 1_000, "swiss-quote-1")
    # The second investor gets a quote while two places are left ...
    second_payload = get_full_marketplace_loan(actor=second, loan_id=str(loan.pk))
    second_minimum = int(second_payload["minimum_investment_minor"])
    second_quote = originator.create_originator_claim_quote(
        originator.CreateOriginatorClaimQuoteCommand(
            actor=second, loan_id=str(loan.pk), requested_cash_minor=second_minimum + 1_000
        )
    )
    # ... then only one place is left, so the minimum is now the whole rest.
    _set_limit(2)
    with pytest.raises(originator.OriginatorClaimsValidationError, match="Request a new quote"):
        _purchase(second, second_quote, "swiss-quote-2")
    # No place left at all: 409 for the quote and the purchase.
    _set_limit(1)
    with pytest.raises(originator.OriginatorClaimsSwissInvestorLimitError):
        _purchase(second, second_quote, "swiss-quote-2-full")
    client.force_login(cast(Any, newcomer))
    response = client.post(
        f"/api/v1/originator-claims/loans/{loan.pk}/quote/",
        data={"requested_cash_minor": 500_000},
        content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json() == {"detail": FULL_MESSAGE.format(1), "code": SWISS_INVESTOR_LIMIT_CODE}
    # The existing investor can still buy at the loan minimum.
    buy(first, 150_000, "swiss-quote-1-more")


# Public site ------------------------------------------------------------------------


@pytest.mark.django_db
def test_public_project_reports_the_new_investor_minimum_and_places(
    client: Client,
    admin_user: Model,
) -> None:
    swiss = _swiss_loan(admin_user)
    first = _lender("public-1")
    _invest(admin_user, first, swiss, 20_000_00, "swiss-public-1")

    payload = client.get(f"{PROJECTS_URL}{swiss.pk}/").json()
    assert payload["investors_count"] == 1
    assert payload["max_investors"] == 20
    assert payload["places_left"] == 19
    # 80,000.00 / 19 = 4,210.53, rounded up.
    assert payload["minimum_investment_minor"] == 4_211_00

    _set_limit(1)
    cache.clear()
    payload = client.get(f"{PROJECTS_URL}{swiss.pk}/").json()
    assert payload["places_left"] == 0
    # No new investor can join: no minimum to show.
    assert payload["minimum_investment_minor"] is None
    assert payload["public_status"] == "open"

    _set_limit(0)
    cache.clear()
    payload = client.get(f"{PROJECTS_URL}{swiss.pk}/").json()
    assert payload["max_investors"] is None
    assert payload["places_left"] is None
    assert payload["minimum_investment_minor"] == 1_000_00


@pytest.mark.django_db
def test_funded_swiss_loan_reports_its_places_for_the_secondary_market(
    client: Client,
    admin_user: Model,
) -> None:
    loan = _swiss_loan(admin_user)
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.filter(pk=loan.pk).update(status="active", loan_start_date=date(2026, 1, 1))
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    for index in range(3):
        holder = _lender(f"funded-{index}")
        holding_model.objects.create(
            loan=loan,
            investor_user_id=holder.pk,
            source_type="manual_admin",
            source_id=f"swiss-funded-{index}",
            status="active",
            original_principal_minor=10_000_00,
            current_principal_minor=10_000_00,
            currency=loan.currency,
            loan_share_ppm=100_000,
            assignment_effective_at=timezone.now(),
            created_by_admin_id=admin_user.pk,
            idempotency_key=f"swiss-funded-{index}",
        )
    payload = client.get(f"{PROJECTS_URL}{loan.pk}/").json()
    assert payload["public_status"] == "repaying"
    assert payload["investors_count"] == 3
    assert payload["places_left"] == 17
    assert payload["minimum_investment_minor"] is None


def test_openapi_schema_describes_the_limit_fields() -> None:
    generators: Any = import_module("drf_spectacular.generators")
    schema = generators.SchemaGenerator().get_schema(request=None, public=True)
    components = schema["components"]["schemas"]
    assert {"max_investors", "places_left"} <= set(components["PublicProject"]["properties"])
    investor = components["MarketplaceLoanPreview"]["properties"]
    assert {"max_investors", "places_left", "is_existing_investor"} <= set(investor)
