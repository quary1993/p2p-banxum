from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client
from django.test.utils import override_settings
from django.utils import timezone

from backend.apps.fx.models import FxEvent, FxEventType, FxExchange, FxQuote
from backend.apps.fx.services import (
    ExecuteFxQuoteCommand,
    FxAuthorizationError,
    FxValidationError,
    IssueFxQuoteCommand,
    ProviderRate,
    configured_mock_provider_rate,
    create_fx_delta_report,
    execute_fx_quote,
    issue_fx_quote,
)
from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.models import AuditEvent, DomainEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="fx-admin@example.test",
            password="AdminPass123!",
            full_name="FX Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def investor() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="fx-investor@example.test",
            full_name="FX Investor",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


def _as_of(
    value: date = date(2026, 1, 10),
    *,
    hour: int = 10,
) -> datetime:
    return datetime.combine(value, time(hour=hour), tzinfo=business_timezone())


def _received_at(value_date: date) -> datetime:
    return datetime.combine(value_date, time.min, tzinfo=business_timezone())


def _provider_rate(
    *,
    as_of: datetime,
    rate: str = "1.100000",
    previous_day_average_rate: str | None = "1.100000",
) -> ProviderRate:
    return ProviderRate(
        provider="yahoo_finance",
        rate=Decimal(rate),
        previous_day_average_rate=(
            Decimal(previous_day_average_rate)
            if previous_day_average_rate is not None
            else None
        ),
        observed_at=as_of,
        provider_quote_id=f"test-rate:{rate}:{as_of.isoformat()}",
        raw_payload_reference="test-provider-payload",
    )


def _approve_financial_access(investor: Model) -> None:
    now = timezone.now()
    cast(Any, investor).phone_verified_at = now
    investor.save(update_fields=["phone_verified_at"])
    kyc_case_model = apps.get_model("kyc_compliance", "KycVerificationCase")
    kyc_case_model.objects.update_or_create(
        user_id=investor.pk,
        defaults={
            "subject_reference": f"user:{investor.pk}",
            "provider_environment": "test",
            "workflow_id": "test-workflow",
            "vendor_data": f"user:{investor.pk}",
            "status": "approved",
            "decision_at": now,
        },
    )


def _deposit(
    admin_user: Model,
    investor: Model,
    *,
    amount_minor: int,
    currency: str = "CHF",
    value_date: date = date(2026, 1, 1),
    idempotency_key: str = "fx-deposit-1",
) -> Model:
    ledger = import_module("backend.apps.ledger.services")
    result = ledger.declare_lender_deposit(
        ledger.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=amount_minor,
            currency=currency,
            booking_date=value_date,
            value_date=value_date,
            collection_account_identifier=f"{currency}GARANTAFX",
            payer_name="FX Investor",
            payer_account_identifier="CH11INVESTOR",
            bank_reference=f"BANK-{idempotency_key}",
            payment_reference=f"INV-{investor.pk}",
            evidence_reference=f"statement:{idempotency_key}",
            notes="Matched manually for FX test.",
            idempotency_key=idempotency_key,
        )
    )
    return cast(Model, result.balance_lot)


def _reconciliation_snapshot(
    admin_user: Model,
    *,
    currency: str,
    bank_stated_balance_minor: int,
    as_of_date: date = date(2026, 1, 10),
) -> Any:
    ledger = import_module("backend.apps.ledger.services")
    return ledger.create_reconciliation_snapshot(
        ledger.CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency=currency,
            as_of_date=as_of_date,
            bank_stated_balance_minor=bank_stated_balance_minor,
        )
    )


def _quote_command(
    investor: Model,
    *,
    amount_minor: int = 10_000_00,
    source_currency: str = "CHF",
    target_currency: str = "EUR",
    rate: str = "1.100000",
    previous_day_average_rate: str | None = "1.100000",
    idempotency_key: str = "fx-quote-1",
    as_of: datetime | None = None,
) -> IssueFxQuoteCommand:
    timestamp = as_of or _as_of()
    return IssueFxQuoteCommand(
        actor=investor,
        source_currency=source_currency,
        target_currency=target_currency,
        source_amount_minor=amount_minor,
        provider_rate=_provider_rate(
            as_of=timestamp,
            rate=rate,
            previous_day_average_rate=previous_day_average_rate,
        ),
        idempotency_key=idempotency_key,
        as_of=timestamp,
    )


@pytest.mark.django_db
def test_issue_fx_quote_calculates_fee_and_records_evidence(investor: Model) -> None:
    _approve_financial_access(investor)
    quote = issue_fx_quote(_quote_command(investor))
    idempotent = issue_fx_quote(_quote_command(investor))

    assert quote.id == idempotent.id
    assert quote.source_currency_id == "CHF"
    assert quote.target_currency_id == "EUR"
    assert quote.rate == Decimal("1.100000")
    assert quote.platform_fee_bps == 150
    assert quote.gross_target_amount_minor == 11_000_00
    assert quote.fee_minor == 165_00
    assert quote.target_amount_minor == 10_835_00
    assert quote.limit_chf_equivalent_minor == 10_000_00
    assert quote.expires_at == quote.issued_at + timedelta(seconds=60)
    assert quote.sanity_metadata["checks"][0]["name"] == "freshness"
    assert FxEvent.objects.filter(quote=quote, event_type=FxEventType.QUOTE_ISSUED).exists()
    assert AuditEvent.objects.filter(action="fx.quote_issued", target_id=str(quote.id)).exists()
    assert DomainEvent.objects.filter(
        event_type="FxExecutableQuoteIssued",
        aggregate_id=str(quote.id),
    ).exists()


@pytest.mark.django_db
def test_issue_fx_quote_rejects_stale_out_of_bounds_and_deviating_provider_rates(
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    as_of = _as_of()

    with pytest.raises(FxValidationError, match="stale"):
        issue_fx_quote(
            IssueFxQuoteCommand(
                actor=investor,
                source_currency="CHF",
                target_currency="EUR",
                source_amount_minor=10_000_00,
                provider_rate=_provider_rate(
                    as_of=as_of - timedelta(minutes=10),
                    rate="1.100000",
                ),
                idempotency_key="fx-stale-rate",
                as_of=as_of,
            )
        )

    with pytest.raises(FxValidationError, match="outside configured"):
        issue_fx_quote(
            _quote_command(
                investor,
                rate="3.000000",
                previous_day_average_rate=None,
                idempotency_key="fx-out-of-bounds",
                as_of=as_of,
            )
        )

    with pytest.raises(FxValidationError, match="deviates"):
        issue_fx_quote(
            _quote_command(
                investor,
                rate="1.200000",
                previous_day_average_rate="1.000000",
                idempotency_key="fx-deviating-rate",
                as_of=as_of,
            )
        )


@pytest.mark.django_db
def test_execute_fx_quote_consumes_source_lots_and_inherits_earliest_deadlines(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    first_lot = _deposit(
        admin_user,
        investor,
        amount_minor=10_000_00,
        value_date=date(2026, 1, 1),
        idempotency_key="fx-deposit-first",
    )
    second_lot = _deposit(
        admin_user,
        investor,
        amount_minor=5_000_00,
        value_date=date(2026, 1, 5),
        idempotency_key="fx-deposit-second",
    )
    as_of = _as_of()
    quote = issue_fx_quote(
        _quote_command(
            investor,
            amount_minor=12_000_00,
            idempotency_key="fx-executable-quote",
            as_of=as_of,
        )
    )

    exchange = execute_fx_quote(
        ExecuteFxQuoteCommand(
            actor=investor,
            quote_id=str(quote.id),
            idempotency_key="fx-execute-quote",
            as_of=as_of,
        )
    )
    idempotent = execute_fx_quote(
        ExecuteFxQuoteCommand(
            actor=investor,
            quote_id=str(quote.id),
            idempotency_key="fx-execute-quote",
            as_of=as_of,
        )
    )
    first_lot.refresh_from_db()
    second_lot.refresh_from_db()
    first_lot_data = cast(Any, first_lot)
    second_lot_data = cast(Any, second_lot)
    target_lot = exchange.target_balance_lot
    target_lot.refresh_from_db()

    assert idempotent.id == exchange.id
    assert FxExchange.objects.count() == 1
    assert exchange.gross_target_amount_minor == 13_200_00
    assert exchange.fee_minor == 198_00
    assert exchange.target_amount_minor == 13_002_00
    assert first_lot_data.available_amount_minor == 0
    assert first_lot_data.converted_amount_minor == 10_000_00
    assert first_lot_data.status == "consumed"
    assert second_lot_data.available_amount_minor == 3_000_00
    assert second_lot_data.converted_amount_minor == 2_000_00
    assert target_lot.source_type == "fx_proceeds"
    assert target_lot.original_amount_minor == 13_002_00
    assert target_lot.available_amount_minor == 13_002_00
    assert target_lot.received_at == as_of
    assert target_lot.investment_deadline_at == _received_at(date(2026, 1, 1)) + timedelta(
        days=30
    )
    assert target_lot.withdrawal_deadline_at == _received_at(date(2026, 1, 1)) + timedelta(
        days=60
    )
    assert [allocation["amount_minor"] for allocation in exchange.source_lot_allocations] == [
        10_000_00,
        2_000_00,
    ]

    source_postings = list(exchange.source_journal_entry.postings.select_related("account"))
    assert {
        (posting.account.account_type, posting.side, posting.amount_minor)
        for posting in source_postings
    } == {
        ("investor_balance_liability", "debit", 12_000_00),
        ("fx_clearing", "credit", 12_000_00),
    }
    target_postings = list(exchange.target_journal_entry.postings.select_related("account"))
    assert {
        (posting.account.account_type, posting.side, posting.amount_minor)
        for posting in target_postings
    } == {
        ("fx_clearing", "debit", 13_200_00),
        ("fx_fee_revenue", "credit", 198_00),
        ("investor_balance_liability", "credit", 13_002_00),
    }
    assert FxEvent.objects.filter(
        exchange=exchange,
        event_type=FxEventType.EXCHANGE_COMPLETED,
    ).exists()
    assert DomainEvent.objects.filter(
        event_type="CurrencyExchangeCompleted",
        aggregate_id=str(exchange.id),
    ).exists()


@pytest.mark.django_db
def test_reconciliation_identity_includes_fx_clearing_and_fee_revenue(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    _deposit(
        admin_user,
        investor,
        amount_minor=12_000_00,
        idempotency_key="fx-reconciliation-deposit",
    )
    as_of = _as_of()
    quote = issue_fx_quote(
        _quote_command(
            investor,
            amount_minor=12_000_00,
            idempotency_key="fx-reconciliation-quote",
            as_of=as_of,
        )
    )
    execute_fx_quote(
        ExecuteFxQuoteCommand(
            actor=investor,
            quote_id=str(quote.id),
            idempotency_key="fx-reconciliation-execute",
            as_of=as_of,
        )
    )

    chf_snapshot = _reconciliation_snapshot(
        admin_user,
        currency="CHF",
        bank_stated_balance_minor=12_000_00,
        as_of_date=as_of.date(),
    )
    eur_snapshot = _reconciliation_snapshot(
        admin_user,
        currency="EUR",
        bank_stated_balance_minor=0,
        as_of_date=as_of.date(),
    )

    assert chf_snapshot.reconciliation_difference_minor == 0
    assert chf_snapshot.investor_balance_liability_minor == 0
    assert chf_snapshot.metadata["fx_clearing_signed_balance_minor"] == 12_000_00
    assert chf_snapshot.metadata["fx_fee_revenue_minor"] == 0
    assert eur_snapshot.reconciliation_difference_minor == 0
    assert eur_snapshot.investor_balance_liability_minor == 13_002_00
    assert eur_snapshot.garanta_accrued_revenue_minor == 198_00
    assert eur_snapshot.metadata["fx_clearing_signed_balance_minor"] == -13_200_00
    assert eur_snapshot.metadata["fx_fee_revenue_minor"] == 198_00
    assert eur_snapshot.metadata["account_sign_anomalies"] == []


@pytest.mark.django_db
def test_execute_fx_quote_rejects_expired_quote(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    _deposit(admin_user, investor, amount_minor=10_000_00)
    as_of = _as_of()
    quote = issue_fx_quote(_quote_command(investor, idempotency_key="fx-expiring", as_of=as_of))

    with pytest.raises(FxValidationError, match="expired"):
        execute_fx_quote(
            ExecuteFxQuoteCommand(
                actor=investor,
                quote_id=str(quote.id),
                idempotency_key="fx-expired-execute",
                as_of=as_of + timedelta(seconds=61),
            )
        )


@pytest.mark.django_db
def test_fx_daily_limit_is_per_investor_and_idempotent_replay_still_returns_existing_quote(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    _deposit(admin_user, investor, amount_minor=101_000_00, idempotency_key="fx-limit-deposit")
    as_of = _as_of()
    quote = issue_fx_quote(
        _quote_command(
            investor,
            amount_minor=100_000_00,
            rate="1.000000",
            previous_day_average_rate="1.000000",
            idempotency_key="fx-limit-quote",
            as_of=as_of,
        )
    )
    execute_fx_quote(
        ExecuteFxQuoteCommand(
            actor=investor,
            quote_id=str(quote.id),
            idempotency_key="fx-limit-execute",
            as_of=as_of,
        )
    )
    replay = issue_fx_quote(
        _quote_command(
            investor,
            amount_minor=100_000_00,
            rate="1.000000",
            previous_day_average_rate="1.000000",
            idempotency_key="fx-limit-quote",
            as_of=as_of,
        )
    )
    user_model: Any = get_user_model()
    other_investor = cast(
        Model,
        user_model.objects.create_user(
            email="fx-other-investor@example.test",
            full_name="FX Other Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    _approve_financial_access(other_investor)

    assert replay.id == quote.id
    with pytest.raises(FxValidationError, match="daily conversion limit"):
        issue_fx_quote(
            _quote_command(
                investor,
                amount_minor=1_00,
                rate="1.000000",
                previous_day_average_rate="1.000000",
                idempotency_key="fx-limit-exceeded",
                as_of=as_of,
            )
        )
    other_quote = issue_fx_quote(
        _quote_command(
            other_investor,
            amount_minor=1_00,
            rate="1.000000",
            previous_day_average_rate="1.000000",
            idempotency_key="fx-limit-other-investor",
            as_of=as_of,
        )
    )
    assert other_quote.investor_user_id == other_investor.pk


@pytest.mark.django_db
def test_fx_delta_report_aggregates_external_settlement_requirements(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    _deposit(admin_user, investor, amount_minor=12_000_00, idempotency_key="fx-delta-deposit")
    as_of = _as_of()
    quote = issue_fx_quote(
        _quote_command(
            investor,
            amount_minor=12_000_00,
            idempotency_key="fx-delta-quote",
            as_of=as_of,
        )
    )
    exchange = execute_fx_quote(
        ExecuteFxQuoteCommand(
            actor=investor,
            quote_id=str(quote.id),
            idempotency_key="fx-delta-execute",
            as_of=as_of,
        )
    )

    report = create_fx_delta_report(
        actor=admin_user,
        start_date=as_of.date(),
        end_date=as_of.date(),
    )

    assert report.exchange_count == 1
    assert report.source_sold_by_currency_minor == {"CHF": 12_000_00}
    assert report.gross_target_bought_by_currency_minor == {"EUR": 13_200_00}
    assert report.target_credited_by_currency_minor == {"EUR": 13_002_00}
    assert report.fees_by_currency_minor == {"EUR": 198_00}
    assert report.net_external_settlement_by_currency_minor == {
        "CHF": -12_000_00,
        "EUR": 13_200_00,
    }
    assert AuditEvent.objects.filter(
        action="fx.delta_report_generated",
        target_id=f"{as_of.date().isoformat()}:{as_of.date().isoformat()}",
    ).exists()
    assert exchange.id is not None

    with pytest.raises(FxAuthorizationError):
        create_fx_delta_report(actor=investor, start_date=as_of.date(), end_date=as_of.date())


@pytest.mark.django_db
def test_fx_api_quote_execute_and_admin_delta_report(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    today = timezone.localtime(timezone.now(), business_timezone()).date()
    _deposit(
        admin_user,
        investor,
        amount_minor=10_000_00,
        value_date=today,
        idempotency_key="fx-api-deposit",
    )
    client.force_login(cast(Any, investor))

    quote_response = client.post(
        "/api/v1/fx/quotes/",
        data={
            "source_currency": "CHF",
            "target_currency": "EUR",
            "source_amount_minor": 10_000_00,
            "idempotency_key": "fx-api-quote",
        },
        content_type="application/json",
    )
    quote_payload = quote_response.json()
    execute_response = client.post(
        f"/api/v1/fx/quotes/{quote_payload['id']}/execute/",
        data={"idempotency_key": "fx-api-execute"},
        content_type="application/json",
    )
    client.logout()
    client.force_login(cast(Any, admin_user))
    report_response = client.get(
        "/api/v1/fx/admin/delta-report/",
        data={"start_date": today.isoformat(), "end_date": today.isoformat()},
    )

    assert quote_response.status_code == 201
    assert quote_payload["gross_target_amount_minor"] == 10_500_00
    assert quote_payload["fee_minor"] == 157_50
    assert quote_payload["target_amount_minor"] == 10_342_50
    assert quote_payload["status"] == "issued"
    assert execute_response.status_code == 201
    assert execute_response.json()["status"] == "completed"
    assert report_response.status_code == 200
    assert report_response.json()["exchange_count"] == 1


@pytest.mark.django_db
def test_fx_append_only_records_have_app_and_db_guards(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    _deposit(admin_user, investor, amount_minor=10_000_00, idempotency_key="fx-append-deposit")
    as_of = _as_of()
    quote = issue_fx_quote(_quote_command(investor, idempotency_key="fx-append-quote", as_of=as_of))
    exchange = execute_fx_quote(
        ExecuteFxQuoteCommand(
            actor=investor,
            quote_id=str(quote.id),
            idempotency_key="fx-append-execute",
            as_of=as_of,
        )
    )
    event = FxEvent.objects.get(event_type=FxEventType.EXCHANGE_COMPLETED)
    guarded_records = [
        (quote, FxQuote, "fx_fxquote"),
        (exchange, FxExchange, "fx_fxexchange"),
        (event, FxEvent, "fx_fxevent"),
    ]

    for record, model, table in guarded_records:
        record_id = record.pk
        db_record_id = record_id.hex
        with pytest.raises(AppendOnlyViolation):
            record.save()
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).update(id=record_id)
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).delete()

        with pytest.raises(DatabaseError) as update_error, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {table} SET id = %s WHERE id = %s",
                    [db_record_id, db_record_id],
                )
        assert "append-only" in str(update_error.value)

        with pytest.raises(DatabaseError) as delete_error, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table} WHERE id = %s", [db_record_id])
        assert "append-only" in str(delete_error.value)


@pytest.mark.django_db
@override_settings(IS_PRODUCTION=True)
def test_mock_fx_provider_is_blocked_in_production() -> None:
    with pytest.raises(FxValidationError, match="Mock FX provider"):
        configured_mock_provider_rate(source_currency="CHF", target_currency="EUR")
