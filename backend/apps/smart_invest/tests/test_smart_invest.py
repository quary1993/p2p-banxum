from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.platform_core.services.impersonation import (
    READONLY_IMPERSONATION_HEADER,
    issue_readonly_impersonation_token,
)
from backend.apps.smart_invest.models import (
    SmartInvestMatchNotification,
    SmartInvestRule,
    SmartInvestRuleEvent,
)
from backend.apps.smart_invest.services import (
    SaveSmartInvestRuleCommand,
    SmartInvestValidationError,
    deactivate_smart_invest_rule,
    opportunity_matches_criteria,
    save_smart_invest_rule,
)


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="smart-admin@example.test",
            password="AdminPass123!",
            full_name="Smart Admin",
            account_type="superadmin",
            status="active",
            is_staff=True,
            is_superuser=True,
        ),
    )


def _make_investor(email: str) -> Model:
    user_model: Any = get_user_model()
    user = cast(
        Model,
        user_model.objects.create_user(
            email=email,
            full_name="Smart Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    cast(Any, user).phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])
    case_model = apps.get_model("kyc_compliance", "KycVerificationCase")
    case_model.objects.create(
        user_id=user.pk,
        subject_reference=f"user:{user.pk}",
        provider_environment="test",
        workflow_id="smart-test",
        vendor_data=f"user:{user.pk}",
        status="approved",
        decision_at=timezone.now(),
    )
    return user


@pytest.fixture
def investor() -> Model:
    return _make_investor("smart-investor@example.test")


def _borrower(admin_user: Model, *, suffix: str = "") -> Model:
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    return cast(
        Model,
        borrower_model.objects.create(
            legal_name=f"Smart Borrower {suffix} AG",
            year_founded=2018,
            kyb_status="approved",
            country="Switzerland",
            created_by_admin_id=admin_user.pk,
        ),
    )


def _loan_services() -> Any:
    return import_module("backend.apps.loans.services")


def _loan_command(admin_user: Model, borrower: Model, *, title: str) -> Any:
    loan_services = _loan_services()
    return loan_services.CreateLoanCommand(
        actor=admin_user,
        borrower_id=str(borrower.pk),
        title=title,
        investor_summary="A secured Smart Invest test opportunity.",
        purpose="bridge_financing",
        principal_minor=100_000_00,
        currency="CHF",
        interest_rate_bps=950,
        term_months=18,
        repayment_type="equal_installments",
        funding_deadline=timezone.localdate() + timedelta(days=20),
        collateral_type="real_estate",
        collateral_value_minor=180_000_00,
        risk_rating="BBB",
    )


def _loan_originator(admin_user: Model, *, name: str) -> Model:
    originator_model = apps.get_model("originator_claims", "LoanOriginator")
    return cast(
        Model,
        originator_model.objects.create(
            legal_name=f"{name} AG",
            public_name=name,
            registration_number=f"CHE-{name}",
            jurisdiction="CH",
            registered_address="Bahnhofstrasse 1, Zurich",
            settlement_account_name=f"{name} AG",
            settlement_iban="CH9300762011623852957",
            created_by_admin_id=admin_user.pk,
        ),
    )


def _rule_command(investor: Model, **overrides: Any) -> SaveSmartInvestRuleCommand:
    values: dict[str, Any] = {
        "actor": investor,
        "minimum_yield_bps": 900,
        "maximum_term_months": 24,
        "currencies": ["CHF"],
        "collateral": ["any_secured"],
    }
    values.update(overrides)
    return SaveSmartInvestRuleCommand(**values)


@pytest.mark.django_db
def test_rule_requires_a_real_criterion_and_deactivation_clears_current_state(
    investor: Model,
) -> None:
    with pytest.raises(SmartInvestValidationError, match="at least one"):
        save_smart_invest_rule(SaveSmartInvestRuleCommand(actor=investor))
    with pytest.raises(SmartInvestValidationError, match="at least one"):
        save_smart_invest_rule(
            SaveSmartInvestRuleCommand(actor=investor, minimum_yield_bps=0)
        )

    payload = save_smart_invest_rule(_rule_command(investor))
    assert payload["rule"]["is_active"] is True
    assert payload["rule"]["minimum_yield_bps"] == 900

    deactivated = deactivate_smart_invest_rule(actor=investor)
    assert deactivated["rule"]["is_active"] is False
    assert deactivated["rule"]["minimum_yield_bps"] is None
    for field in ("originators", "collateral", "currencies", "risk_ratings", "purposes"):
        assert deactivated["rule"][field] == []
    assert deactivated["rule"]["loan_kinds"] == []
    assert SmartInvestRuleEvent.objects.filter(investor_user_id=investor.pk).count() == 2


def _criteria(**overrides: Any) -> dict[str, Any]:
    criteria: dict[str, Any] = {
        "minimum_yield_bps": None,
        "maximum_term_months": None,
        "originators": [],
        "collateral": [],
        "currencies": [],
        "risk_ratings": [],
        "purposes": [],
        "loan_kinds": [],
    }
    criteria.update(overrides)
    return criteria


_ORIGINATOR_ID = "96a74f48-0663-4976-bc92-ddf0c9d319fe"
_DIRECT = {
    "yield_bps": 1_000,
    "term_months": 12,
    "product_type": "direct",
    "originator_id": None,
    "collateral_type": "real_estate",
    "ltv_bps": 6_000,
    "currency": "CHF",
    "risk_rating": "BBB",
    "purpose": "bridge_financing",
    "is_refinancing": True,
}
_ORIGINATOR = {
    **_DIRECT,
    "product_type": "originator_claim",
    "originator_id": _ORIGINATOR_ID,
    "currency": "EUR",
    "collateral_type": "equipment",
    "risk_rating": "A-",
    "purpose": "working_capital",
    "is_refinancing": False,
}
_UNSECURED = {
    **_DIRECT,
    "collateral_type": "unsecured_exception",
    "ltv_bps": None,
    "risk_rating": "A",
}


@pytest.mark.django_db
def test_matching_covers_direct_originator_currency_and_loan_type() -> None:
    base = _criteria(
        minimum_yield_bps=900,
        maximum_term_months=18,
        originators=["banxum"],
        collateral=["any_secured"],
        currencies=["CHF"],
        risk_ratings=["BBB"],
        purposes=["bridge_financing"],
        loan_kinds=["refinancing"],
    )
    assert opportunity_matches_criteria(_DIRECT, base) is True
    assert opportunity_matches_criteria(_ORIGINATOR, base) is False
    originator_criteria = _criteria(
        originators=[_ORIGINATOR_ID], currencies=["EUR"], loan_kinds=["new"]
    )
    assert opportunity_matches_criteria(_ORIGINATOR, originator_criteria) is True
    assert opportunity_matches_criteria(_DIRECT, originator_criteria) is False
    # An empty list never restricts.
    assert opportunity_matches_criteria(_DIRECT, _criteria()) is True
    assert opportunity_matches_criteria(_UNSECURED, _criteria()) is True


@pytest.mark.django_db
def test_matching_accepts_any_of_several_ticked_values() -> None:
    def matches(opportunity: dict[str, Any], **criteria: Any) -> bool:
        return opportunity_matches_criteria(opportunity, _criteria(**criteria))

    # Risk rating A together with A-.
    assert matches(_ORIGINATOR, risk_ratings=["A", "A-"]) is True
    assert matches(_UNSECURED, risk_ratings=["A", "A-"]) is True
    assert matches(_DIRECT, risk_ratings=["A", "A-"]) is False
    # CHF together with EUR.
    assert matches(_DIRECT, currencies=["CHF", "EUR"]) is True
    assert matches(_ORIGINATOR, currencies=["CHF", "EUR"]) is True
    assert matches(_ORIGINATOR, currencies=["CHF"]) is False
    # Two collateral types plus unsecured lending.
    two_types_and_unsecured = ["real_estate", "equipment", "unsecured"]
    assert matches(_DIRECT, collateral=two_types_and_unsecured) is True
    assert matches(_ORIGINATOR, collateral=two_types_and_unsecured) is True
    assert matches(_UNSECURED, collateral=two_types_and_unsecured) is True
    invoices = {**_DIRECT, "collateral_type": "invoices"}
    assert matches(invoices, collateral=two_types_and_unsecured) is False
    assert matches(_UNSECURED, collateral=["real_estate", "equipment"]) is False
    # "Any collateral" covers every secured loan, including collateral types added later.
    future_type = {**_DIRECT, "collateral_type": "future_type"}
    assert matches(future_type, collateral=["any_secured"]) is True
    assert matches(_UNSECURED, collateral=["any_secured"]) is False
    # A secured type with no collateral value is unsecured, as before.
    assert matches({**_DIRECT, "ltv_bps": None}, collateral=["real_estate"]) is False
    # BANXUM direct loans together with one Loan Originator.
    assert matches(_DIRECT, originators=["banxum", _ORIGINATOR_ID]) is True
    assert matches(_ORIGINATOR, originators=["banxum", _ORIGINATOR_ID]) is True
    other_originator = {**_ORIGINATOR, "originator_id": "00000000-0000-4000-8000-000000000001"}
    assert matches(other_originator, originators=["banxum", _ORIGINATOR_ID]) is False
    # New lending together with refinancing; several purposes.
    assert matches(_DIRECT, loan_kinds=["new", "refinancing"]) is True
    assert matches(_DIRECT, purposes=["working_capital", "bridge_financing"]) is True
    assert matches(_DIRECT, purposes=["working_capital"]) is False


@pytest.mark.django_db
def test_rule_lists_are_validated_deduplicated_and_ordered(
    admin_user: Model, investor: Model
) -> None:
    originator = _loan_originator(admin_user, name="Alpine")
    payload = save_smart_invest_rule(
        SaveSmartInvestRuleCommand(
            actor=investor,
            originators=[str(originator.pk).upper(), "banxum", str(originator.pk)],
            collateral=["unsecured", "equipment", "real_estate", "equipment"],
            currencies=["EUR", "CHF", "EUR"],
            risk_ratings=["A-", "A", "A-"],
            purposes=["working_capital", "acquisition"],
            loan_kinds=["refinancing"],
        )
    )
    rule = payload["rule"]
    assert rule["originators"] == ["banxum", str(originator.pk)]
    assert rule["collateral"] == ["real_estate", "equipment", "unsecured"]
    assert rule["currencies"] == ["CHF", "EUR"]
    assert rule["risk_ratings"] == ["A", "A-"]
    assert rule["purposes"] == ["working_capital", "acquisition"]
    assert rule["loan_kinds"] == ["refinancing"]
    event = SmartInvestRuleEvent.objects.get(investor_user_id=investor.pk)
    assert event.criteria_snapshot["risk_ratings"] == ["A", "A-"]

    # "Any collateral" already implies every collateral type.
    implied = save_smart_invest_rule(
        SaveSmartInvestRuleCommand(
            actor=investor, collateral=["real_estate", "any_secured", "equipment"]
        )
    )
    assert implied["rule"]["collateral"] == ["any_secured"]
    assert implied["rule"]["revision"] == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"risk_ratings": ["A", "Z"]}, "Risk rating 'Z'"),
        ({"currencies": ["USD"]}, "Currency 'USD'"),
        ({"purposes": ["holiday"]}, "Purpose 'holiday'"),
        ({"loan_kinds": ["all"]}, "Loan type 'all'"),
        ({"collateral": ["unsecured_exception"]}, "Collateral 'unsecured_exception'"),
        ({"collateral": ["secured"]}, "Collateral 'secured'"),
        ({"originators": ["specific"]}, "Loan Originator 'specific' is not valid"),
        (
            {"originators": ["96a74f48-0663-4976-bc92-ddf0c9d319fe"]},
            "Loan Originator '96a74f48-0663-4976-bc92-ddf0c9d319fe' does not exist",
        ),
    ],
)
def test_rule_rejects_values_outside_the_catalog(
    investor: Model, overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(SmartInvestValidationError, match=message):
        save_smart_invest_rule(SaveSmartInvestRuleCommand(actor=investor, **overrides))
    assert not SmartInvestRule.objects.filter(user_id=investor.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"currencies": ["CHF", "EUR"]},
        {"loan_kinds": ["new", "refinancing"]},
        {"collateral": ["any_secured", "unsecured"]},
        {"collateral": ["real_estate", "any_secured", "unsecured"]},
    ],
)
def test_ticking_every_option_is_not_a_criterion(
    investor: Model, overrides: dict[str, Any]
) -> None:
    with pytest.raises(SmartInvestValidationError, match="at least one"):
        save_smart_invest_rule(SaveSmartInvestRuleCommand(actor=investor, **overrides))
    # Combined with a real condition the full selection is stored as ticked.
    payload = save_smart_invest_rule(
        SaveSmartInvestRuleCommand(actor=investor, minimum_yield_bps=800, **overrides)
    )
    assert payload["rule"]["is_active"] is True


@pytest.mark.django_db
def test_publishing_matching_loan_enqueues_one_alert_without_backfill(
    admin_user: Model,
    investor: Model,
) -> None:
    loan_services = _loan_services()
    first = loan_services.create_loan(
        _loan_command(admin_user, _borrower(admin_user, suffix="One"), title="First")
    )
    loan_services.publish_loan(
        loan_services.PublishLoanCommand(actor=admin_user, loan_id=str(first.id))
    )
    save_smart_invest_rule(_rule_command(investor))
    assert SmartInvestMatchNotification.objects.count() == 0

    second = loan_services.create_loan(
        _loan_command(admin_user, _borrower(admin_user, suffix="Two"), title="Second")
    )
    loan_services.publish_loan(
        loan_services.PublishLoanCommand(actor=admin_user, loan_id=str(second.id))
    )

    assert (
        SmartInvestMatchNotification.objects.filter(
            investor_user_id=investor.pk, loan_id=second.id
        ).count()
        == 1
    )
    message = OutboxMessage.objects.get(topic="email.smart_invest_opportunity_match")
    assert message.payload["user_id"] == str(investor.pk)
    assert message.payload["loan_id"] == str(second.id)
    assert "does not reserve or invest funds" in message.payload["body"]

    # A repeated publication hook cannot send the same opportunity twice.
    from backend.apps.smart_invest.services import notify_smart_invest_matches_for_published_loan

    notify_smart_invest_matches_for_published_loan(loan_id=str(second.id), product_type="direct")
    assert SmartInvestMatchNotification.objects.count() == 1
    assert OutboxMessage.objects.filter(topic="email.smart_invest_opportunity_match").count() == 1


@pytest.mark.django_db
def test_publication_alerts_use_the_same_multi_select_matching(
    admin_user: Model,
    investor: Model,
) -> None:
    loan_services = _loan_services()
    other = _make_investor("smart-investor-two@example.test")
    # The test loan is CHF, BBB, real estate, bridge financing, new lending.
    save_smart_invest_rule(
        SaveSmartInvestRuleCommand(
            actor=investor,
            risk_ratings=["A", "BBB"],
            currencies=["CHF", "EUR"],
            collateral=["equipment", "real_estate", "unsecured"],
            purposes=["working_capital", "bridge_financing"],
        )
    )
    save_smart_invest_rule(SaveSmartInvestRuleCommand(actor=other, risk_ratings=["A", "A-"]))
    loan = loan_services.create_loan(
        _loan_command(admin_user, _borrower(admin_user, suffix="Multi"), title="Multi")
    )
    loan_services.publish_loan(
        loan_services.PublishLoanCommand(actor=admin_user, loan_id=str(loan.id))
    )

    notifications = SmartInvestMatchNotification.objects.filter(loan_id=loan.id)
    assert [str(item.investor_user_id) for item in notifications] == [str(investor.pk)]
    assert notifications.get().match_snapshot["criteria"]["risk_ratings"] == ["A", "BBB"]
    # The matches list applies the identical rule.
    from backend.apps.smart_invest.services import get_smart_invest

    def match_ids(actor: Model) -> set[str]:
        return {str(item["loan_id"]) for item in get_smart_invest(actor=actor)["matches"]}

    assert str(loan.id) in match_ids(investor)
    assert str(loan.id) not in match_ids(other)


@pytest.mark.django_db
def test_restricted_investor_is_not_alerted(
    admin_user: Model,
    investor: Model,
) -> None:
    loan_services = _loan_services()
    save_smart_invest_rule(_rule_command(investor))
    cast(Any, investor).status = "restricted"
    investor.save(update_fields=["status"])
    loan = loan_services.create_loan(
        _loan_command(admin_user, _borrower(admin_user, suffix="Restricted"), title="No alert")
    )
    loan_services.publish_loan(
        loan_services.PublishLoanCommand(actor=admin_user, loan_id=str(loan.id))
    )
    assert SmartInvestMatchNotification.objects.count() == 0


@pytest.mark.django_db
def test_api_is_self_scoped_and_readonly_impersonation_can_read(
    admin_user: Model,
    investor: Model,
) -> None:
    save_smart_invest_rule(_rule_command(investor))
    client = Client()
    client.force_login(cast(Any, admin_user))
    assert (
        client.put(
            "/api/v1/investor/smart-invest/",
            data={"minimum_yield_bps": 1_000},
            content_type="application/json",
        ).status_code
        == 403
    )

    token = issue_readonly_impersonation_token(actor=admin_user, target_user_id=str(investor.pk))[
        "token"
    ]
    response = client.get(
        "/api/v1/investor/smart-invest/",
        **{f"HTTP_{READONLY_IMPERSONATION_HEADER.upper().replace('-', '_')}": token},
    )
    assert response.status_code == 200
    assert response.json()["rule"]["minimum_yield_bps"] == 900


@pytest.mark.django_db
def test_api_saves_multi_select_lists_and_rejects_unknown_values(investor: Model) -> None:
    client = Client()
    client.force_login(cast(Any, investor))
    response = client.put(
        "/api/v1/investor/smart-invest/",
        data={
            "risk_ratings": ["A-", "A"],
            "currencies": ["CHF", "EUR"],
            "collateral": ["real_estate", "equipment", "unsecured"],
            "loan_kinds": ["new"],
        },
        content_type="application/json",
    )
    assert response.status_code == 200, response.json()
    rule = response.json()["rule"]
    assert rule["risk_ratings"] == ["A", "A-"]
    assert rule["currencies"] == ["CHF", "EUR"]
    assert rule["collateral"] == ["real_estate", "equipment", "unsecured"]
    assert rule["loan_kinds"] == ["new"]
    assert rule["originators"] == [] and rule["purposes"] == []
    assert "currency_scope" not in rule and "risk_rating" not in rule

    rejected = client.put(
        "/api/v1/investor/smart-invest/",
        data={"risk_ratings": ["A", "not-a-rating"]},
        content_type="application/json",
    )
    assert rejected.status_code == 400
    assert "risk_ratings" in rejected.json()


@pytest.mark.django_db
def test_rule_events_have_app_and_database_append_only_guards(investor: Model) -> None:
    save_smart_invest_rule(_rule_command(investor))
    event = SmartInvestRuleEvent.objects.get()
    event.metadata = {"tampered": True}
    with pytest.raises(AppendOnlyViolation):
        event.save()

    table = SmartInvestRuleEvent._meta.db_table
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {connection.ops.quote_name(table)} SET metadata = %s WHERE id = %s",
            ["{}", event.id.hex],
        )


@pytest.mark.django_db
def test_rule_update_replaces_the_single_current_rule(investor: Model) -> None:
    first = save_smart_invest_rule(_rule_command(investor))
    second = save_smart_invest_rule(
        replace(
            _rule_command(investor),
            minimum_yield_bps=1_100,
            currencies=["EUR"],
        )
    )
    assert first["rule"]["id"] == second["rule"]["id"]
    assert second["rule"]["revision"] == 2
    assert SmartInvestRule.objects.filter(user_id=investor.pk).count() == 1


_BEFORE_LISTS = ("smart_invest", "0002_smart_invest_append_only_guards")
_AFTER_LISTS = ("smart_invest", "0004_remove_single_value_criteria")


def _migrate(target: tuple[str, str]) -> Any:
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([target])
    return executor.loader.project_state([target]).apps


# Transactional because SQLite cannot alter tables inside the per-test transaction.
# The test creates no append-only rows, so the flush after it succeeds.
@pytest.mark.django_db(transaction=True)
def test_migration_converts_single_value_rules_exactly() -> None:
    originator_id = "96a74f48-0663-4976-bc92-ddf0c9d319fe"
    old_criteria: dict[str, dict[str, Any]] = {
        "everything": {},
        "chf-secured": {"currency_scope": "CHF", "collateral_scope": "secured"},
        "eur-unsecured-new": {
            "currency_scope": "EUR",
            "collateral_scope": "unsecured",
            "loan_kind": "new",
        },
        "specific-collateral": {
            "collateral_scope": "specific",
            "collateral_type": "real_estate",
            "risk_rating": "A-",
            "purpose": "working_capital",
            "loan_kind": "refinancing",
        },
        "unsecured-exception": {
            "collateral_scope": "specific",
            "collateral_type": "unsecured_exception",
        },
        "banxum": {"originator_scope": "banxum", "minimum_yield_bps": 700},
        "specific-originator": {"originator_scope": "specific", "originator_id": originator_id},
    }
    expected: dict[str, dict[str, list[str]]] = {
        "everything": {},
        "chf-secured": {"currencies": ["CHF"], "collateral": ["any_secured"]},
        "eur-unsecured-new": {
            "currencies": ["EUR"],
            "collateral": ["unsecured"],
            "loan_kinds": ["new"],
        },
        "specific-collateral": {
            "collateral": ["real_estate"],
            "risk_ratings": ["A-"],
            "purposes": ["working_capital"],
            "loan_kinds": ["refinancing"],
        },
        "unsecured-exception": {"collateral": ["unsecured"]},
        "banxum": {"originators": ["banxum"]},
        "specific-originator": {"originators": [originator_id]},
    }
    list_fields = (
        "originators",
        "collateral",
        "currencies",
        "risk_ratings",
        "purposes",
        "loan_kinds",
    )
    try:
        old_apps = _migrate(_BEFORE_LISTS)
        old_rule_model = old_apps.get_model("smart_invest", "SmartInvestRule")
        users: dict[str, Model] = {}
        updated_at: dict[str, Any] = {}
        for index, (key, criteria) in enumerate(old_criteria.items()):
            user = _make_investor(f"smart-migration-{index}@example.test")
            users[key] = user
            rule = old_rule_model.objects.create(
                user_id=user.pk, is_active=True, revision=3, **criteria
            )
            updated_at[key] = rule.updated_at

        _migrate(_AFTER_LISTS)

        for key, user in users.items():
            rule = SmartInvestRule.objects.get(user_id=user.pk)
            converted = {field: getattr(rule, field) for field in list_fields}
            assert converted == {field: expected[key].get(field, []) for field in list_fields}, key
            # The storage shape changes, not the investor's rule: no new revision.
            assert rule.revision == 3 and rule.is_active is True
            assert rule.updated_at == updated_at[key]
        assert SmartInvestRule.objects.get(user_id=users["banxum"].pk).minimum_yield_bps == 700
    finally:
        _migrate(_AFTER_LISTS)
