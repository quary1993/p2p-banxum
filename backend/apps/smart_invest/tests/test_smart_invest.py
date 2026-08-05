from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
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


@pytest.fixture
def investor() -> Model:
    user_model: Any = get_user_model()
    user = cast(
        Model,
        user_model.objects.create_user(
            email="smart-investor@example.test",
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


def _rule_command(investor: Model, **overrides: Any) -> SaveSmartInvestRuleCommand:
    values: dict[str, Any] = {
        "actor": investor,
        "minimum_yield_bps": 900,
        "maximum_term_months": 24,
        "currency_scope": "CHF",
        "collateral_scope": "secured",
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
    assert deactivated["rule"]["currency_scope"] == "all"
    assert SmartInvestRuleEvent.objects.filter(investor_user_id=investor.pk).count() == 2


@pytest.mark.django_db
def test_matching_covers_direct_originator_currency_and_loan_type() -> None:
    originator_id = "96a74f48-0663-4976-bc92-ddf0c9d319fe"
    direct = {
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
    originator = {
        **direct,
        "product_type": "originator_claim",
        "originator_id": originator_id,
        "currency": "EUR",
        "is_refinancing": False,
    }
    base = {
        "minimum_yield_bps": 900,
        "maximum_term_months": 18,
        "originator_scope": "banxum",
        "originator_id": None,
        "collateral_scope": "secured",
        "collateral_type": "",
        "currency_scope": "CHF",
        "risk_rating": "BBB",
        "purpose": "bridge_financing",
        "loan_kind": "refinancing",
    }
    assert opportunity_matches_criteria(direct, base) is True
    assert opportunity_matches_criteria(originator, base) is False
    originator_criteria = {
        **base,
        "originator_scope": "specific",
        "originator_id": originator_id,
        "currency_scope": "EUR",
        "loan_kind": "new",
    }
    assert opportunity_matches_criteria(originator, originator_criteria) is True


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
            currency_scope="EUR",
        )
    )
    assert first["rule"]["id"] == second["rule"]["id"]
    assert second["rule"]["revision"] == 2
    assert SmartInvestRule.objects.filter(user_id=investor.pk).count() == 1
