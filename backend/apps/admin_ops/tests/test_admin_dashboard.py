from __future__ import annotations

from datetime import date, timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.admin_ops import services as admin_ops_services
from backend.apps.admin_ops.models import (
    AdminTask,
    AdminTaskPriority,
    AdminTaskStatus,
    AdminTaskType,
)
from backend.apps.admin_ops.services import (
    CreateAdminTaskCommand,
    GetAdminDashboardCommand,
    SyncReconciliationBreakTasksCommand,
    create_admin_task,
    get_admin_operations_dashboard,
    sync_reconciliation_break_tasks,
)
from backend.apps.admin_ops.tests.factories import create_user
from backend.apps.platform_core.models import (
    AuditEvent,
    Currency,
    DomainEvent,
    OutboxMessage,
)


@pytest.fixture
def admin_user() -> Model:
    return create_user(email="dashboard-admin@example.test")


@pytest.fixture
def investor() -> Model:
    return create_user(
        email="dashboard-investor@example.test",
        account_type="natural_person_lender",
        status="active",
        is_staff=False,
    )


def _borrower(admin_user: Model, *, legal_name: str = "Dashboard Borrower AG") -> Model:
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    return cast(
        Model,
        borrower_model.objects.create(
            legal_name=legal_name,
            year_founded=2018,
            entity_type="swiss_company",
            kyb_status="approved",
            compliance_hold=False,
            country="Switzerland",
            created_by_admin_id=admin_user.pk,
        ),
    )


def _loan(
    admin_user: Model,
    borrower: Model,
    *,
    title: str,
    status: str = "funded",
    first_payment_date: date | None = None,
) -> Model:
    loan_model = apps.get_model("loans", "Loan")
    chf = Currency.objects.get(code="CHF")
    first_payment = first_payment_date or (timezone.localdate() + timedelta(days=3))
    return cast(
        Model,
        loan_model.objects.create(
            borrower=borrower,
            status=status,
            title=title,
            investor_summary="Dashboard test loan.",
            purpose="bridge_financing",
            principal_minor=10_000_00,
            currency=chf,
            interest_rate_bps=1000,
            term_months=12,
            repayment_type="equal_installments",
            funding_deadline=timezone.localdate() + timedelta(days=20),
            first_payment_date=first_payment,
            collateral_type="real_estate",
            collateral_value_minor=20_000_00,
            risk_rating="BBB",
            borrower_success_fee_bps=200,
            committed_principal_minor=10_000_00 if status != "published" else 5_000_00,
            total_scheduled_principal_minor=10_000_00,
            total_scheduled_interest_minor=1_000_00,
            created_by_admin_id=admin_user.pk,
            published_at=timezone.now(),
        ),
    )


def _installment(loan: Model, *, due_date: date, amount_minor: int = 1_100_00) -> Model:
    installment_model = apps.get_model("loans", "LoanInstallment")
    loan_ref = cast(Any, loan)
    return cast(
        Model,
        installment_model.objects.create(
            loan=loan,
            schedule_version=loan_ref.schedule_version,
            installment_number=1,
            due_date=due_date,
            principal_minor=amount_minor - 100_00,
            interest_minor=100_00,
            total_minor=amount_minor,
        ),
    )


def _declare_old_deposit(admin_user: Model, investor: Model, *, value_date: date) -> None:
    ledger_services = import_module("backend.apps.ledger.services")
    ledger_services.declare_lender_deposit(
        ledger_services.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=1_000_00,
            currency="CHF",
            booking_date=value_date,
            value_date=value_date,
            collection_account_identifier="CHF-COLLECTION",
            payer_name=str(cast(Any, investor).full_name),
            payer_account_identifier="INVESTOR-IBAN",
            bank_reference="OLD-DEPOSIT",
            payment_reference=f"INV-{investor.pk}",
            evidence_reference="statement:old-deposit",
            idempotency_key="admin-dashboard-old-deposit",
        )
    )


def _pending_bank_operation(admin_user: Model) -> None:
    bank_operation_model = apps.get_model("ledger", "BankOperation")
    chf = Currency.objects.get(code="CHF")
    bank_operation_model.objects.create(
        operation_type="lender_deposit",
        status="pending_review",
        amount_minor=250_00,
        currency=chf,
        booking_date=timezone.localdate(),
        value_date=timezone.localdate(),
        collection_account_identifier="CHF-COLLECTION",
        payer_name="Unknown Payer",
        payer_account_identifier="UNKNOWN-IBAN",
        payee_name="Garanta Finanzgruppe AG",
        payee_account_identifier="CHF-COLLECTION",
        bank_reference="PENDING-BANK-REF",
        payment_reference="UNKNOWN",
        linked_object_type="investor",
        linked_object_id="unknown",
        evidence_reference="statement:pending",
        confirmed_by_admin_id=admin_user.pk,
        confirmed_at=timezone.now(),
        notes="Needs manual review.",
        metadata={},
        idempotency_key="admin-dashboard-pending-bank-operation",
    )


def _forced_withdrawal_request(admin_user: Model, investor: Model) -> None:
    withdrawal_model = apps.get_model("ledger", "InvestorWithdrawalRequest")
    chf = Currency.objects.get(code="CHF")
    withdrawal_model.objects.create(
        investor_user_id=investor.pk,
        status="requested",
        amount_minor=500_00,
        currency=chf,
        destination_iban="CH9300762011623852957",
        destination_account_name="Dashboard Investor",
        requested_by_user_id=admin_user.pk,
        requested_at=timezone.now(),
        is_forced=True,
        lot_allocations=[],
        notes="Forced withdrawal test.",
        metadata={},
        idempotency_key="admin-dashboard-forced-withdrawal",
    )


def _reconciliation_snapshot(
    admin_user: Model,
    *,
    difference_minor: int = 0,
    metadata: dict[str, Any] | None = None,
) -> Model:
    reconciliation_model = apps.get_model("ledger", "ReconciliationSnapshot")
    return cast(
        Model,
        reconciliation_model.objects.create(
            currency=Currency.objects.get(code="CHF"),
            as_of_date=timezone.localdate(),
            bank_stated_balance_minor=999_00,
            investor_balance_liability_minor=1_000_00,
            reconciliation_difference_minor=difference_minor,
            created_by_admin_id=admin_user.pk,
            metadata=metadata or {},
        ),
    )


@pytest.mark.django_db
def test_admin_dashboard_aggregates_daily_operations(
    admin_user: Model,
    investor: Model,
) -> None:
    now = timezone.now()
    today = timezone.localdate()
    create_admin_task(
        CreateAdminTaskCommand(
            actor=admin_user,
            task_type=AdminTaskType.PAYMENT_RECONCILIATION,
            title="Review unmatched bank inflow",
            priority=AdminTaskPriority.URGENT,
            due_at=now - timedelta(hours=1),
            related_object_type="BankOperation",
            related_object_id="pending-bank-op",
        )
    )
    kyc_case_model = apps.get_model("kyc_compliance", "KycVerificationCase")
    kyc_case_model.objects.create(
        subject_type="user",
        user=investor,
        subject_reference=f"user:{investor.pk}",
        provider_environment="test",
        workflow_id="workflow",
        vendor_data=f"user:{investor.pk}",
        status="pep_hit",
        manual_review_required=True,
        detected_flags=["pep"],
    )
    _pending_bank_operation(admin_user)
    _forced_withdrawal_request(admin_user, investor)
    _declare_old_deposit(admin_user, investor, value_date=today - timedelta(days=70))

    borrower = _borrower(admin_user)
    due_loan = _loan(admin_user, borrower, title="Repayment due loan", status="funded")
    _installment(due_loan, due_date=today + timedelta(days=3))
    _loan(admin_user, borrower, title="Funding campaign", status="published")
    _loan(admin_user, borrower, title="Risk loan", status="defaulted")

    reconciliation_model = apps.get_model("ledger", "ReconciliationSnapshot")
    reconciliation_model.objects.create(
        currency=Currency.objects.get(code="CHF"),
        as_of_date=today,
        bank_stated_balance_minor=999_00,
        investor_balance_liability_minor=1_000_00,
        reconciliation_difference_minor=-1_00,
        created_by_admin_id=admin_user.pk,
        metadata={},
    )
    reconciliation_model.objects.create(
        currency=Currency.objects.get(code="CHF"),
        as_of_date=today,
        bank_stated_balance_minor=1_000_00,
        investor_balance_liability_minor=1_000_00,
        reconciliation_difference_minor=0,
        created_by_admin_id=admin_user.pk,
        metadata={
            "account_sign_anomalies": [
                {"account_type": "withdrawal_payable", "credit_balance_minor": -10_00}
            ],
            "investor_balance_integrity_breaks": [
                {
                    "investor_user_id": str(investor.pk),
                    "currency": "CHF",
                    "lot_available_minor": 1_000_00,
                    "liability_posting_minor": 990_00,
                    "difference_minor": 10_00,
                }
            ],
        },
    )
    OutboxMessage.objects.create(
        idempotency_key="admin-dashboard-dead-email",
        topic="email.transactional.test",
        payload={},
        status="dead_letter",
        attempts=8,
        last_error="SMTP rejected message.",
    )

    dashboard = get_admin_operations_dashboard(
        GetAdminDashboardCommand(actor=admin_user, as_of=now, due_window_days=7, queue_limit=5)
    )

    assert dashboard["summary"] == {
        "admin_tasks_open": 1,
        "admin_tasks_overdue": 1,
        "kyc_review_required": 1,
        "bank_operations_pending": 1,
        "withdrawals_requested": 1,
        "forced_withdrawals_requested": 1,
        "published_loans": 1,
        "late_loans": 0,
        "defaulted_loans": 1,
        "written_off_loans": 0,
        "repayments_due_in_window": 1,
        "repayments_overdue": 0,
        "secondary_listing_approvals": 0,
        "fx_unsettled_exchanges": 0,
        "failed_email_messages": 1,
        "reconciliation_breaks": 2,
        "balance_lots_overdue": 1,
        "balance_lots_penalty_mode": 0,
    }
    chf_summary = dashboard["currency_summaries"][0]
    assert chf_summary["currency"] == "CHF"
    assert chf_summary["available_balance_minor"] == 1_000_00
    assert chf_summary["overdue_available_minor"] == 1_000_00
    assert chf_summary["pending_withdrawal_minor"] == 500_00
    assert chf_summary["forced_withdrawal_minor"] == 500_00
    assert chf_summary["pending_bank_operation_minor"] == 250_00
    assert dashboard["queues"]["admin_tasks"][0]["title"] == "Review unmatched bank inflow"
    assert dashboard["queues"]["kyc_reviews"][0]["status"] == "pep_hit"
    assert dashboard["queues"]["balance_ageing_actions"][0]["kind"] == "balance_lot_overdue"
    assert dashboard["queues"]["servicing_due"][0]["amount_minor"] == 1_100_00
    assert dashboard["queues"]["failed_emails"][0]["metadata"]["attempts"] == 8
    reconciliation_signals = [
        item["metadata"]["break_signals"] for item in dashboard["queues"]["reconciliation_breaks"]
    ]
    assert ["account_sign_anomalies", "investor_balance_integrity_breaks"] in reconciliation_signals


@pytest.mark.django_db
def test_admin_dashboard_api_is_admin_only(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    client.force_login(cast(Any, investor))
    forbidden = client.get("/api/v1/admin-ops/dashboard/")
    assert forbidden.status_code == 403

    client.force_login(cast(Any, admin_user))
    response = client.get(
        "/api/v1/admin-ops/dashboard/",
        data={"due_window_days": 14, "limit": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["due_window_days"] == 14
    assert body["queue_limit"] == 3
    assert "summary" in body
    assert "queues" in body


@pytest.mark.django_db
def test_reconciliation_break_task_sync_creates_idempotent_tasks(
    admin_user: Model,
    investor: Model,
) -> None:
    clean_snapshot = _reconciliation_snapshot(admin_user)
    diff_snapshot = _reconciliation_snapshot(admin_user, difference_minor=-1_00)
    integrity_snapshot = _reconciliation_snapshot(
        admin_user,
        metadata={
            "account_sign_anomalies": [
                {"account_type": "withdrawal_payable", "credit_balance_minor": -10_00}
            ],
            "investor_balance_integrity_breaks": [
                {
                    "investor_user_id": str(investor.pk),
                    "currency": "CHF",
                    "lot_available_minor": 1_000_00,
                    "liability_posting_minor": 990_00,
                    "difference_minor": 10_00,
                }
            ],
        },
    )

    result = sync_reconciliation_break_tasks(
        SyncReconciliationBreakTasksCommand(actor=admin_user, limit=10)
    )
    rerun = sync_reconciliation_break_tasks(
        SyncReconciliationBreakTasksCommand(actor=admin_user, limit=10)
    )

    assert result["created_count"] == 2
    assert result["existing_count"] == 0
    assert result["skipped_count"] == 1
    assert rerun["created_count"] == 0
    assert rerun["existing_count"] == 2
    assert rerun["skipped_count"] == 1
    assert AdminTask.objects.count() == 2
    assert not AdminTask.objects.filter(related_object_id=str(clean_snapshot.pk)).exists()
    diff_task = AdminTask.objects.get(related_object_id=str(diff_snapshot.pk))
    integrity_task = AdminTask.objects.get(related_object_id=str(integrity_snapshot.pk))
    assert diff_task.task_type == AdminTaskType.PAYMENT_RECONCILIATION
    assert diff_task.priority == AdminTaskPriority.HIGH
    assert diff_task.status == AdminTaskStatus.OPEN
    assert diff_task.due_at is not None
    assert "reconciliation_difference" in diff_task.notes
    assert integrity_task.priority == AdminTaskPriority.URGENT
    assert "investor_balance_integrity_breaks" in integrity_task.notes
    assert AuditEvent.objects.filter(
        action="admin_ops.reconciliation_break_tasks_synced",
    ).count() == 2
    assert DomainEvent.objects.filter(event_type="ReconciliationBreakTasksSynced").count() == 2


@pytest.mark.django_db
def test_reconciliation_break_task_unique_constraint_blocks_duplicates(
    admin_user: Model,
) -> None:
    snapshot = _reconciliation_snapshot(admin_user, difference_minor=50_00)
    create_admin_task(
        CreateAdminTaskCommand(
            actor=admin_user,
            task_type=AdminTaskType.PAYMENT_RECONCILIATION,
            title="Investigate CHF reconciliation break",
            priority=AdminTaskPriority.HIGH,
            related_object_type="ReconciliationSnapshot",
            related_object_id=str(snapshot.pk),
        )
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        AdminTask.objects.create(
            task_type=AdminTaskType.PAYMENT_RECONCILIATION,
            title="Duplicate reconciliation break",
            priority=AdminTaskPriority.HIGH,
            created_by=cast(Any, admin_user),
            related_object_type="ReconciliationSnapshot",
            related_object_id=str(snapshot.pk),
        )


@pytest.mark.django_db
def test_reconciliation_break_task_sync_recovers_from_concurrent_create(
    admin_user: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _reconciliation_snapshot(admin_user, difference_minor=50_00)

    def create_from_overlapping_sync(command: CreateAdminTaskCommand) -> AdminTask:
        AdminTask.objects.create(
            task_type=AdminTaskType.PAYMENT_RECONCILIATION,
            title="Created by overlapping reconciliation sync",
            priority=AdminTaskPriority.HIGH,
            created_by=cast(Any, command.actor),
            due_at=timezone.now(),
            notes="Created by a concurrent admin sync.",
            related_object_type="ReconciliationSnapshot",
            related_object_id=str(snapshot.pk),
        )
        raise IntegrityError("duplicate reconciliation task")

    monkeypatch.setattr(
        admin_ops_services,
        "create_admin_task",
        create_from_overlapping_sync,
    )

    result = sync_reconciliation_break_tasks(
        SyncReconciliationBreakTasksCommand(actor=admin_user, limit=10)
    )

    assert result["created_count"] == 0
    assert result["existing_count"] == 1
    assert result["skipped_count"] == 0
    assert result["tasks"][0].related_object_id == str(snapshot.pk)
    assert AdminTask.objects.count() == 1


@pytest.mark.django_db
def test_reconciliation_break_task_sync_api_is_admin_only(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    _reconciliation_snapshot(admin_user, difference_minor=50_00)

    client.force_login(cast(Any, investor))
    forbidden = client.post(
        "/api/v1/admin-ops/reconciliation-break-tasks/sync/",
        data={"limit": 10},
        content_type="application/json",
    )

    client.force_login(cast(Any, admin_user))
    response = client.post(
        "/api/v1/admin-ops/reconciliation-break-tasks/sync/",
        data={"limit": 10},
        content_type="application/json",
    )

    assert forbidden.status_code == 403
    assert response.status_code == 200
    assert response.json()["created_count"] == 1
    assert response.json()["tasks"][0]["related_object_type"] == "ReconciliationSnapshot"
