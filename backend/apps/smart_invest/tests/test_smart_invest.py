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
from backend.apps.platform_core.tests.swiss_uid import next_test_uid
from backend.apps.smart_invest.models import (
    SmartInvestMatchNotification,
    SmartInvestRule,
    SmartInvestRuleEvent,
)
from backend.apps.smart_invest.services import (
    SaveSmartInvestRuleCommand,
    SmartInvestValidationError,
    get_smart_invest,
    opportunity_matches_criteria,
    pause_smart_invest_rule,
    resume_smart_invest_rule,
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
            full_name="Smart-Investor",
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
            uid=next_test_uid(),
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
        investor_summary="A secured Smart-Invest test opportunity.",
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
def test_rule_can_be_resumed_only_once_set_up_and_pause_keeps_the_preferences(
    investor: Model,
) -> None:
    with pytest.raises(SmartInvestValidationError, match="Set up Smart Invest"):
        resume_smart_invest_rule(actor=investor)

    payload = save_smart_invest_rule(_rule_command(investor))
    assert payload["rule"]["is_active"] is True
    assert payload["rule"]["state"] == "active"
    assert payload["rule"]["minimum_yield_bps"] == 900

    # U33-DEC-19: pause keeps the preferences and shows no matches.
    paused = pause_smart_invest_rule(actor=investor)
    assert paused["rule"]["is_active"] is False
    assert paused["rule"]["state"] == "paused"
    assert paused["rule"]["minimum_yield_bps"] == 900
    assert paused["rule"]["currencies"] == ["CHF"]
    assert paused["matches"] == [] and paused["match_count"] == 0
    # Editing while paused saves the preferences and stays paused.
    edited = save_smart_invest_rule(replace(_rule_command(investor), minimum_yield_bps=1_000))
    assert edited["rule"]["state"] == "paused"
    assert edited["rule"]["minimum_yield_bps"] == 1_000

    resumed = resume_smart_invest_rule(actor=investor)
    assert resumed["rule"]["state"] == "active"
    assert resumed["rule"]["minimum_yield_bps"] == 1_000
    events = SmartInvestRuleEvent.objects.filter(investor_user_id=investor.pk)
    assert [event.event_type for event in events.order_by("revision")] == [
        "saved",
        "paused",
        "saved",
        "resumed",
    ]
    # Pausing twice changes nothing.
    pause_smart_invest_rule(actor=investor)
    pause_smart_invest_rule(actor=investor)
    assert events.count() == 5


def _criteria(**overrides: Any) -> dict[str, Any]:
    criteria: dict[str, Any] = {
        "minimum_yield_bps": None,
        "maximum_term_months": None,
        "maximum_ltv_bps": None,
        "preferred_amount_minor": None,
        "originators": [],
        "collateral": [],
        "currencies": [],
        "countries": [],
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
    "borrower_country": "CH",
    # U33-DEC-16: a rating in the payload never influences matching.
    "risk_rating": "BBB",
    # U33-DEC-19: purpose and refinancing never influence matching.
    "purpose": "bridge_financing",
    "is_refinancing": True,
}
_ORIGINATOR = {
    **_DIRECT,
    "product_type": "originator_claim",
    "originator_id": _ORIGINATOR_ID,
    "currency": "EUR",
    "borrower_country": "RO",
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
def test_matching_covers_direct_originator_currency_ltv_and_country() -> None:
    base = _criteria(
        minimum_yield_bps=900,
        maximum_term_months=18,
        maximum_ltv_bps=6_000,
        originators=["banxum"],
        collateral=["any_secured"],
        currencies=["CHF"],
        countries=["CH"],
        preferred_amount_minor=1_000_000_00,
    )
    assert opportunity_matches_criteria(_DIRECT, base) is True
    assert opportunity_matches_criteria(_ORIGINATOR, base) is False
    # A lower loan-to-value limit, or a loan without a loan-to-value figure, does not match.
    assert opportunity_matches_criteria(_DIRECT, {**base, "maximum_ltv_bps": 5_999}) is False
    assert opportunity_matches_criteria(_UNSECURED, _criteria(maximum_ltv_bps=8_000)) is False
    # Countries compare without letter case; another country does not match.
    assert opportunity_matches_criteria(_DIRECT, _criteria(countries=["ch", "RO"])) is True
    assert opportunity_matches_criteria(_DIRECT, _criteria(countries=["RO"])) is False
    originator_criteria = _criteria(originators=[_ORIGINATOR_ID], currencies=["EUR"])
    assert opportunity_matches_criteria(_ORIGINATOR, originator_criteria) is True
    assert opportunity_matches_criteria(_DIRECT, originator_criteria) is False
    # An empty list never restricts.
    assert opportunity_matches_criteria(_DIRECT, _criteria()) is True
    assert opportunity_matches_criteria(_UNSECURED, _criteria()) is True


@pytest.mark.django_db
def test_matching_accepts_any_of_several_ticked_values() -> None:
    def matches(opportunity: dict[str, Any], **criteria: Any) -> bool:
        return opportunity_matches_criteria(opportunity, _criteria(**criteria))

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
    # Two countries.
    assert matches(_DIRECT, countries=["CH", "RO"]) is True
    assert matches(_ORIGINATOR, countries=["CH", "RO"]) is True


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
            countries=[" CH ", "RO", "ch"],
            maximum_ltv_bps=7_000,
            preferred_amount_minor=2_500_00,
        )
    )
    rule = payload["rule"]
    assert rule["originators"] == ["banxum", str(originator.pk)]
    assert rule["collateral"] == ["real_estate", "equipment", "unsecured"]
    assert rule["currencies"] == ["CHF", "EUR"]
    assert rule["countries"] == ["CH", "RO"]
    assert rule["maximum_ltv_bps"] == 7_000
    assert rule["preferred_amount_minor"] == 2_500_00
    assert "risk_ratings" not in rule
    assert "purposes" not in rule and "loan_kinds" not in rule
    event = SmartInvestRuleEvent.objects.get(investor_user_id=investor.pk)
    assert "risk_ratings" not in event.criteria_snapshot

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
        ({"currencies": ["USD"]}, "Currency 'USD'"),
        ({"countries": [" "]}, "Country '' is not valid"),
        ({"maximum_ltv_bps": 0}, "Maximum loan-to-value"),
        ({"maximum_ltv_bps": 10_001}, "Maximum loan-to-value"),
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
        {"preferred_amount_minor": 1_000_00},
        {"collateral": ["any_secured", "unsecured"]},
        {"collateral": ["real_estate", "any_secured", "unsecured"]},
    ],
)
def test_ticking_every_option_is_not_a_criterion(
    investor: Model, overrides: dict[str, Any]
) -> None:
    # 18.3: saved as an active rule without a limit (it matches every open opportunity); paused,
    # it counts as not set up because nothing limits it.
    open_rule = save_smart_invest_rule(SaveSmartInvestRuleCommand(actor=investor, **overrides))
    assert open_rule["match_count"] == open_rule["open_opportunity_count"]
    assert pause_smart_invest_rule(actor=investor)["rule"]["state"] == "not_set_up"
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
    assert "does not reserve or invest funds" in message.payload["body_text"]
    # The match email must render; a payload the renderer cannot read ends as a dead letter.
    # Loaded by name: module boundaries forbid a static import of communications here.
    communications = import_module("backend.apps.communications.services")
    rendered = communications.render_email_for_outbox_message(message)
    assert rendered.recipient_email == cast(Any, investor).email
    assert "matches the Smart-Invest criteria you selected" in rendered.body_text
    assert "Review opportunity" in rendered.body_html

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
    # The test loan is CHF, real estate, a Swiss borrower.
    save_smart_invest_rule(
        SaveSmartInvestRuleCommand(
            actor=investor,
            currencies=["CHF", "EUR"],
            collateral=["equipment", "real_estate", "unsecured"],
            countries=["Switzerland"],
        )
    )
    save_smart_invest_rule(SaveSmartInvestRuleCommand(actor=other, currencies=["EUR"]))
    loan = loan_services.create_loan(
        _loan_command(admin_user, _borrower(admin_user, suffix="Multi"), title="Multi")
    )
    loan_services.publish_loan(
        loan_services.PublishLoanCommand(actor=admin_user, loan_id=str(loan.id))
    )

    notifications = SmartInvestMatchNotification.objects.filter(loan_id=loan.id)
    assert [str(item.investor_user_id) for item in notifications] == [str(investor.pk)]
    assert notifications.get().match_snapshot["criteria"]["currencies"] == ["CHF", "EUR"]
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
            "currencies": ["CHF", "EUR"],
            "collateral": ["real_estate", "equipment", "unsecured"],
            "maximum_ltv_bps": 6_500,
            "countries": ["CH"],
            "preferred_amount_minor": 1_000_00,
            # U33-DEC-19: no longer criteria; the API ignores them.
            "loan_kinds": ["new"],
            "purposes": ["working_capital"],
        },
        content_type="application/json",
    )
    assert response.status_code == 200, response.json()
    rule = response.json()["rule"]
    assert rule["currencies"] == ["CHF", "EUR"]
    assert rule["collateral"] == ["real_estate", "equipment", "unsecured"]
    assert rule["maximum_ltv_bps"] == 6_500
    assert rule["countries"] == ["CH"]
    assert rule["preferred_amount_minor"] == 1_000_00
    assert rule["originators"] == []
    assert "purposes" not in rule and "loan_kinds" not in rule
    assert "currency_scope" not in rule and "risk_rating" not in rule

    rejected = client.put(
        "/api/v1/investor/smart-invest/",
        data={"currencies": ["CHF", "USD"]},
        content_type="application/json",
    )
    assert rejected.status_code == 400
    assert "currencies" in rejected.json()
    # U33-DEC-16: a rating criterion is no longer part of the rule.
    ignored = client.put(
        "/api/v1/investor/smart-invest/",
        data={"currencies": ["CHF"], "risk_ratings": ["A"]},
        content_type="application/json",
    )
    assert ignored.status_code == 200
    assert "risk_ratings" not in ignored.json()["rule"]


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
_LATEST = ("smart_invest", "0009_remove_purpose_and_loan_kind_columns")


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

        after_apps = _migrate(_AFTER_LISTS)
        after_rule_model = after_apps.get_model("smart_invest", "SmartInvestRule")

        for key, user in users.items():
            rule = after_rule_model.objects.get(user_id=user.pk)
            converted = {field: getattr(rule, field) for field in list_fields}
            assert converted == {field: expected[key].get(field, []) for field in list_fields}, key
            # The storage shape changes, not the investor's rule: no new revision.
            assert rule.revision == 3 and rule.is_active is True
            assert rule.updated_at == updated_at[key]
        assert after_rule_model.objects.get(user_id=users["banxum"].pk).minimum_yield_bps == 700
    finally:
        # 0005 and 0008 record an append-only event per rule with a rating, purpose or loan
        # kind; empty them first so the flush after this transactional test can delete rows.
        state_apps = _migrate(_AFTER_LISTS)
        state_apps.get_model("smart_invest", "SmartInvestRule").objects.update(
            risk_ratings=[], purposes=[], loan_kinds=[]
        )
        _migrate(_LATEST)


def _old_rule(**fields: Any) -> Any:
    from types import SimpleNamespace

    values: dict[str, Any] = {
        "user_id": "5a1f0f43-7b0f-4a64-8a3c-6d1b0b2c0e11",
        "is_active": True,
        "revision": 4,
        "minimum_yield_bps": None,
        "maximum_term_months": None,
        "originators": [],
        "collateral": [],
        "currencies": [],
        "risk_ratings": ["A", "BBB"],
        "purposes": [],
        "loan_kinds": [],
    }
    values.update(fields)
    return SimpleNamespace(**values)


def test_rating_migration_empties_the_criterion_and_records_it() -> None:
    # U33-DEC-16: a saved rule must not keep filtering on ratings in a hidden way.
    migration = import_module(
        "backend.apps.smart_invest.migrations.0005_remove_rating_criterion_from_rules"
    )
    now = timezone.now()
    purposes = ["working_capital", "bridge_financing"]

    changes, event = migration.plan_rating_removal(_old_rule(currencies=["CHF"]), purposes, now)
    assert changes == {"risk_ratings": [], "revision": 5}
    assert event["event_type"] == "rating_criterion_removed"
    assert event["revision"] == 5
    assert event["criteria_snapshot"]["risk_ratings"] == ["A", "BBB"]
    assert event["metadata"] == {
        "decision": "U33-DEC-16",
        "removed_risk_ratings": ["A", "BBB"],
        "deactivated": False,
    }

    # Only the rating restricted the rule: it stops instead of alerting on everything.
    changes, event = migration.plan_rating_removal(_old_rule(), purposes, now)
    assert changes == {"risk_ratings": [], "revision": 5, "is_active": False, "deactivated_at": now}
    assert event["metadata"]["deactivated"] is True
    # Ticking every currency or every purpose is no restriction either.
    changes, _event = migration.plan_rating_removal(
        _old_rule(currencies=["CHF", "EUR"], purposes=purposes), purposes, now
    )
    assert changes["is_active"] is False
    # An inactive rule stays inactive and keeps its other values.
    changes, event = migration.plan_rating_removal(_old_rule(is_active=False), purposes, now)
    assert changes == {"risk_ratings": [], "revision": 5}
    assert event["metadata"]["deactivated"] is False


@pytest.mark.django_db
def test_a_fully_funded_loan_is_not_a_match(admin_user: Model, investor: Model) -> None:
    # Verify 2026-10-09: Smart-Invest listed a fully committed loan as a match.
    loan_services = _loan_services()
    loans = []
    for title in ("Open", "Full"):
        loan = loan_services.create_loan(
            _loan_command(admin_user, _borrower(admin_user, suffix=title), title=title)
        )
        loan_services.publish_loan(
            loan_services.PublishLoanCommand(actor=admin_user, loan_id=str(loan.id))
        )
        loans.append(loan)
    apps.get_model("loans", "Loan").objects.filter(pk=loans[1].id).update(
        committed_principal_minor=100_000_00
    )
    save_smart_invest_rule(_rule_command(investor))

    payload = get_smart_invest(actor=investor)

    assert [match["loan_id"] for match in payload["matches"]] == [str(loans[0].id)]


def test_retired_criteria_migration_empties_purpose_and_loan_kind_and_records_it() -> None:
    # U33-DEC-19: no hidden purpose or refinancing filter stays in a saved rule.
    migration = import_module(
        "backend.apps.smart_invest.migrations.0008_remove_purpose_and_loan_kind_criteria"
    )
    now = timezone.now()
    base: dict[str, Any] = {
        "risk_ratings": [],
        "maximum_ltv_bps": None,
        "preferred_amount_minor": None,
    }

    changes, event = migration.plan_retired_criteria_removal(
        _old_rule(**base, currencies=["CHF"], purposes=["working_capital"], countries=[]), now
    )
    assert changes == {"purposes": [], "loan_kinds": [], "revision": 5}
    assert event["event_type"] == "retired_criteria_removed"
    assert event["criteria_snapshot"]["purposes"] == ["working_capital"]
    assert event["metadata"] == {
        "decision": "U33-DEC-19",
        "removed_purposes": ["working_capital"],
        "removed_loan_kinds": [],
        "paused": False,
    }

    # Only the loan kind restricted the rule: it is paused, its preferences stay.
    changes, event = migration.plan_retired_criteria_removal(
        _old_rule(**base, loan_kinds=["new"], countries=[]), now
    )
    assert changes == {
        "purposes": [],
        "loan_kinds": [],
        "revision": 5,
        "is_active": False,
        "deactivated_at": now,
    }
    assert event["metadata"]["paused"] is True


@pytest.mark.django_db
def test_a_paused_rule_gets_no_alerts_and_resume_recalculates(
    admin_user: Model, investor: Model
) -> None:
    loan_services = _loan_services()
    save_smart_invest_rule(_rule_command(investor))
    pause_smart_invest_rule(actor=investor)
    loan = loan_services.create_loan(
        _loan_command(admin_user, _borrower(admin_user, suffix="Paused"), title="While paused")
    )
    loan_services.publish_loan(
        loan_services.PublishLoanCommand(actor=admin_user, loan_id=str(loan.id))
    )
    assert SmartInvestMatchNotification.objects.count() == 0
    assert get_smart_invest(actor=investor)["matches"] == []

    resumed = resume_smart_invest_rule(actor=investor)
    assert [match["loan_id"] for match in resumed["matches"]] == [str(loan.id)]


@pytest.mark.django_db
def test_api_pauses_and_resumes(investor: Model) -> None:
    client = Client()
    client.force_login(cast(Any, investor))
    assert client.post("/api/v1/investor/smart-invest/resume/").status_code == 400
    client.put(
        "/api/v1/investor/smart-invest/",
        data={"currencies": ["CHF"]},
        content_type="application/json",
    )
    paused = client.post("/api/v1/investor/smart-invest/pause/")
    assert paused.status_code == 200
    assert paused.json()["rule"]["state"] == "paused"
    assert paused.json()["rule"]["currencies"] == ["CHF"]
    resumed = client.post("/api/v1/investor/smart-invest/resume/")
    assert resumed.status_code == 200
    assert resumed.json()["rule"]["state"] == "active"
    assert client.post("/api/v1/investor/smart-invest/deactivate/").status_code == 404


@pytest.mark.django_db
def test_repayment_step_groups_todays_repayment_types(investor: Model) -> None:
    """18.3: Periodic repayments (interest only, principal and interest) and Payment at maturity."""

    def matches(opportunity: dict[str, Any], *options: str) -> bool:
        return opportunity_matches_criteria(opportunity, _criteria(repayment=list(options)))

    annuity = {**_DIRECT, "repayment_type": "equal_installments"}
    interest_only = {**_DIRECT, "repayment_type": "bullet_periodic_interest"}
    one_payment = {**_DIRECT, "repayment_type": "bullet_periodic_interest", "term_months": 1}
    assert matches(annuity, "principal_and_interest") is True
    assert matches(annuity, "interest_only") is False
    assert matches(interest_only, "interest_only", "at_maturity") is True
    assert matches(one_payment, "at_maturity") is True
    assert matches(one_payment, "interest_only") is False
    # No preference (empty) and every option ticked do not restrict.
    assert matches(annuity) is True
    assert matches(annuity, "interest_only", "principal_and_interest", "at_maturity") is True

    saved = save_smart_invest_rule(
        SaveSmartInvestRuleCommand(actor=investor, repayment=["at_maturity", "at_maturity"])
    )
    assert saved["rule"]["repayment"] == ["at_maturity"]
    with pytest.raises(SmartInvestValidationError, match="Repayment"):
        save_smart_invest_rule(SaveSmartInvestRuleCommand(actor=investor, repayment=["monthly"]))


@pytest.mark.django_db
def test_no_preference_everywhere_is_an_active_rule_that_matches_every_open_loan(
    investor: Model,
) -> None:
    """18.3: "No preference" is allowed; paused without any criterion it counts as not set up."""
    saved = save_smart_invest_rule(
        SaveSmartInvestRuleCommand(
            actor=investor,
            currencies=["CHF", "EUR"],
            repayment=["interest_only", "principal_and_interest", "at_maturity"],
            preferred_amount_minor=500_00,
        )
    )
    assert saved["rule"]["state"] == "active"
    assert saved["match_count"] == saved["open_opportunity_count"]
    assert opportunity_matches_criteria(_DIRECT, _criteria()) is True
    assert pause_smart_invest_rule(actor=investor)["rule"]["state"] == "not_set_up"
