from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.utils import timezone

from backend.apps.ledger.models import BankOperation, InvestorBalanceLot
from backend.apps.ledger.services import (
    DeclareLenderDepositCommand,
    declare_lender_deposit,
)
from backend.apps.platform_core.models import Currency
from backend.apps.platform_core.models.audit import AuditEvent

pytestmark = pytest.mark.django_db(transaction=True)


def _require_postgres() -> None:
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL-only production hardening test.")


def _admin_user(email: str = "postgres-admin@example.test") -> Any:
    user_model = get_user_model()
    return user_model.objects.create_user(
        email=email,
        full_name="Postgres Admin",
        account_type="superadmin",
        status="active",
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )


def _investor_user(email: str = "postgres-investor@example.test") -> Any:
    user_model = get_user_model()
    return user_model.objects.create_user(
        email=email,
        full_name="Postgres Investor",
        account_type="natural_person_lender",
        status="active",
        is_staff=False,
        is_superuser=False,
        is_active=True,
        phone_verified_at=timezone.now(),
    )


def test_postgres_append_only_trigger_blocks_raw_audit_update() -> None:
    _require_postgres()
    event = AuditEvent.objects.create(
        actor_type="system",
        actor_id="postgres-hardening",
        action="postgres.append_only.created",
        target_type="PostgresHardening",
        target_id="raw-update",
        metadata={"source": "postgres_hardening_test"},
    )

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE platform_core_auditevent SET action = %s WHERE id = %s",
                ["postgres.append_only.tampered", str(event.id)],
            )

    event.refresh_from_db()
    assert event.action == "postgres.append_only.created"


def test_postgres_lender_deposit_idempotency_survives_concurrent_same_key() -> None:
    _require_postgres()
    Currency.objects.update_or_create(
        code="CHF",
        defaults={"name": "Swiss franc", "minor_units": 2, "is_enabled": True},
    )
    admin = _admin_user()
    investor = _investor_user()
    idempotency_key = "postgres-hardening-lender-deposit-race"
    barrier = threading.Barrier(2)

    def declare_once() -> tuple[str, str, str]:
        close_old_connections()
        try:
            actor = get_user_model().objects.get(pk=admin.pk)
            barrier.wait(timeout=10)
            result = declare_lender_deposit(
                DeclareLenderDepositCommand(
                    actor=actor,
                    investor_user_id=str(investor.pk),
                    amount_minor=25_000,
                    currency="CHF",
                    booking_date=date(2026, 1, 5),
                    value_date=date(2026, 1, 5),
                    collection_account_identifier="CH00POSTGRESHARDENING",
                    payer_name="Postgres Investor",
                    payer_account_identifier="CH00INVESTOR",
                    bank_reference="POSTGRES-RACE",
                    payment_reference="BANXUM-RACE",
                    evidence_reference="postgres-hardening",
                    idempotency_key=idempotency_key,
                )
            )
            return (
                str(result.bank_operation.id),
                str(result.journal_entry.id),
                str(result.balance_lot.id),
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: declare_once(), range(2)))

    assert results[0] == results[1]
    assert BankOperation.objects.filter(idempotency_key=idempotency_key).count() == 1
    assert InvestorBalanceLot.objects.filter(source_id=results[0][0]).count() == 1
