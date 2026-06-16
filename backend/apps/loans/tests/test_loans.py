from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.loans.domain.schedules import add_months
from backend.apps.loans.models import (
    CollateralType,
    Loan,
    LoanEvent,
    LoanPurpose,
    LoanStatus,
    RepaymentType,
    RiskRating,
)
from backend.apps.loans.services import (
    CreateLoanCommand,
    LoanValidationError,
    ManualScheduleRowCommand,
    PublishLoanCommand,
    UpdateLoanCommand,
    create_loan,
    publish_loan,
    update_loan,
)
from backend.apps.platform_core.models import AuditEvent, DomainEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="loan-admin@example.test",
            password="AdminPass123!",
            full_name="Loan Admin",
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
            email="loan-investor@example.test",
            full_name="Loan Investor",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


def _borrower(admin_user: Model, *, kyb_status: str = "approved", hold: bool = False) -> Model:
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    return cast(
        Model,
        borrower_model.objects.create(
            legal_name="Loan Borrower AG",
            year_founded=2018,
            kyb_status=kyb_status,
            compliance_hold=hold,
            country="Switzerland",
            created_by_admin_id=admin_user.pk,
        ),
    )


def _loan_command(
    admin_user: Model,
    borrower: Model,
    *,
    repayment_type: str = RepaymentType.EQUAL_INSTALLMENTS,
    interest_only_months: int = 0,
) -> CreateLoanCommand:
    funding_deadline = timezone.localdate() + timedelta(days=20)
    return CreateLoanCommand(
        actor=admin_user,
        borrower_id=str(borrower.pk),
        title="Senior secured bridge loan",
        investor_summary="Real-estate backed corporate bridge financing.",
        purpose=LoanPurpose.BRIDGE_FINANCING,
        principal_minor=1200_00,
        currency="CHF",
        interest_rate_bps=1200,
        term_months=12,
        repayment_type=repayment_type,
        interest_only_months=interest_only_months,
        funding_deadline=funding_deadline,
        first_payment_date=add_months(funding_deadline, 1),
        collateral_type=CollateralType.REAL_ESTATE,
        collateral_value_minor=2400_00,
        risk_rating=RiskRating.BBB,
    )


@pytest.mark.django_db
def test_admin_can_create_complete_loan_with_equal_installment_schedule(admin_user: Model) -> None:
    borrower = _borrower(admin_user)

    loan = create_loan(_loan_command(admin_user, borrower))
    installments = list(loan.installments.order_by("installment_number"))

    assert loan.status == LoanStatus.DRAFT
    assert loan.ltv_bps == 5000
    assert loan.ltv_warnings == ["collateral_value_exceeds_principal"]
    assert loan.total_scheduled_principal_minor == 1200_00
    assert loan.total_scheduled_interest_minor == 7942
    assert [(row.principal_minor, row.interest_minor, row.total_minor) for row in installments] == [
        (9462, 1200, 10662),
        (9557, 1105, 10662),
        (9652, 1010, 10662),
        (9749, 913, 10662),
        (9846, 816, 10662),
        (9945, 717, 10662),
        (10044, 618, 10662),
        (10145, 517, 10662),
        (10246, 416, 10662),
        (10348, 314, 10662),
        (10452, 210, 10662),
        (10554, 106, 10660),
    ]
    assert LoanEvent.objects.filter(loan=loan, event_type="created").exists()
    assert AuditEvent.objects.filter(action="loan.created", target_id=str(loan.id)).exists()
    assert DomainEvent.objects.filter(event_type="LoanCreated", aggregate_id=str(loan.id)).exists()


@pytest.mark.django_db
def test_manual_schedule_override_must_match_principal(admin_user: Model) -> None:
    borrower = _borrower(admin_user)
    funding_deadline = timezone.localdate() + timedelta(days=30)
    base_command = _loan_command(admin_user, borrower)

    with pytest.raises(LoanValidationError):
        create_loan(
            replace(
                base_command,
                term_months=2,
                first_payment_date=add_months(funding_deadline, 1),
                manual_schedule_rows=[
                    ManualScheduleRowCommand(
                        due_date=add_months(funding_deadline, 1),
                        principal_minor=500_00,
                        interest_minor=10_00,
                    ),
                    ManualScheduleRowCommand(
                        due_date=add_months(funding_deadline, 2),
                        principal_minor=500_00,
                        interest_minor=5_00,
                    ),
                ],
            )
        )


@pytest.mark.django_db
def test_interest_only_then_amortizing_requires_interest_only_period(admin_user: Model) -> None:
    borrower = _borrower(admin_user)

    with pytest.raises(LoanValidationError):
        create_loan(
            _loan_command(
                admin_user,
                borrower,
                repayment_type=RepaymentType.INTEREST_ONLY_THEN_AMORTIZING,
            )
        )

    loan = create_loan(
        _loan_command(
            admin_user,
            borrower,
            repayment_type=RepaymentType.INTEREST_ONLY_THEN_AMORTIZING,
            interest_only_months=3,
        )
    )
    first_rows = list(loan.installments.order_by("installment_number")[:3])

    assert loan.interest_only_months == 3
    assert [row.principal_minor for row in first_rows] == [0, 0, 0]
    assert all(row.interest_minor == 1200 for row in first_rows)


@pytest.mark.django_db
def test_zero_collateral_hides_ltv_and_warns(admin_user: Model) -> None:
    borrower = _borrower(admin_user)
    base_command = _loan_command(admin_user, borrower)

    loan = create_loan(replace(base_command, collateral_value_minor=0))

    assert loan.ltv_bps is None
    assert loan.ltv_warnings == ["collateral_value_zero"]


@pytest.mark.django_db
def test_publish_requires_borrower_can_transact(admin_user: Model) -> None:
    pending_borrower = _borrower(admin_user, kyb_status="pending")
    loan = create_loan(_loan_command(admin_user, pending_borrower))

    with pytest.raises(LoanValidationError):
        publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.id)))

    approved_borrower = _borrower(admin_user)
    publishable_loan = create_loan(_loan_command(admin_user, approved_borrower))
    published = publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(publishable_loan.id)))

    assert published.status == LoanStatus.PUBLISHED
    assert published.published_at is not None
    assert LoanEvent.objects.filter(loan=published, event_type="published").exists()


@pytest.mark.django_db
def test_default_funding_deadline_is_publishable(admin_user: Model) -> None:
    borrower = _borrower(admin_user)
    loan = create_loan(
        replace(
            _loan_command(admin_user, borrower),
            funding_deadline=None,
            first_payment_date=None,
        )
    )

    assert loan.funding_deadline == timezone.localdate() + timedelta(days=29)

    published = publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.id)))

    assert published.status == LoanStatus.PUBLISHED


@pytest.mark.django_db
def test_publish_rejects_funding_deadline_in_past(admin_user: Model) -> None:
    borrower = _borrower(admin_user)
    loan = create_loan(_loan_command(admin_user, borrower))
    loan.funding_deadline = timezone.localdate() - timedelta(days=1)
    loan.save(update_fields=["funding_deadline", "updated_at"])

    with pytest.raises(LoanValidationError, match="Zurich business date"):
        publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.id)))

    loan.refresh_from_db()
    assert loan.status == LoanStatus.DRAFT


@pytest.mark.django_db
def test_publish_rejects_funding_deadline_at_thirty_day_cutoff(admin_user: Model) -> None:
    borrower = _borrower(admin_user)
    funding_deadline = timezone.localdate() + timedelta(days=30)
    loan = create_loan(
        replace(
            _loan_command(admin_user, borrower),
            funding_deadline=funding_deadline,
            first_payment_date=add_months(funding_deadline, 1),
        )
    )

    with pytest.raises(LoanValidationError, match="too far in the future"):
        publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.id)))

    loan.refresh_from_db()
    assert loan.status == LoanStatus.DRAFT


@pytest.mark.django_db
def test_post_commit_edit_allows_only_lowering_amount_with_message(admin_user: Model) -> None:
    borrower = _borrower(admin_user)
    loan = create_loan(_loan_command(admin_user, borrower))
    loan.committed_principal_minor = 600_00
    loan.save(update_fields=["committed_principal_minor", "updated_at"])

    with pytest.raises(LoanValidationError):
        update_loan(
            UpdateLoanCommand(
                actor=admin_user,
                loan_id=str(loan.id),
                interest_rate_bps=1100,
            )
        )

    with pytest.raises(LoanValidationError):
        update_loan(
            UpdateLoanCommand(
                actor=admin_user,
                loan_id=str(loan.id),
                principal_minor=1100_00,
            )
        )

    updated = update_loan(
        UpdateLoanCommand(
            actor=admin_user,
            loan_id=str(loan.id),
            principal_minor=1000_00,
            investor_message="The target amount was lowered before funding close.",
            note="Lowered target.",
        )
    )

    assert updated.principal_minor == 1000_00
    assert updated.schedule_version == 2
    assert sum(
        row.principal_minor
        for row in updated.installments.filter(schedule_version=updated.schedule_version)
    ) == 1000_00


@pytest.mark.django_db
def test_loan_admin_api_create_publish_schedule_and_events(
    client: Client,
    admin_user: Model,
) -> None:
    borrower = _borrower(admin_user)
    client.force_login(cast(Any, admin_user))
    funding_deadline = timezone.localdate() + timedelta(days=20)

    create_response = client.post(
        "/api/v1/loans/admin/loans/",
        data={
            "borrower_id": str(borrower.pk),
            "title": "API Loan",
            "investor_summary": "API-created loan.",
            "purpose": LoanPurpose.WORKING_CAPITAL,
            "principal_minor": 1500_00,
            "currency": "CHF",
            "interest_rate_bps": 1000,
            "term_months": 6,
            "repayment_type": RepaymentType.EQUAL_INSTALLMENTS,
            "funding_deadline": funding_deadline.isoformat(),
            "first_payment_date": add_months(funding_deadline, 1).isoformat(),
            "collateral_type": CollateralType.REAL_ESTATE,
            "collateral_value_minor": 3000_00,
            "risk_rating": RiskRating.A,
        },
        content_type="application/json",
    )
    loan_id = create_response.json()["id"]
    list_response = client.get("/api/v1/loans/admin/loans/", data={"q": "API Loan"})
    schedule_response = client.get(f"/api/v1/loans/admin/loans/{loan_id}/schedule/")
    publish_response = client.post(
        f"/api/v1/loans/admin/loans/{loan_id}/publish/",
        data={"note": "Publish after offline review."},
        content_type="application/json",
    )
    events_response = client.get(f"/api/v1/loans/admin/loans/{loan_id}/events/")

    assert create_response.status_code == 201
    assert create_response.json()["ltv_bps"] == 5000
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert schedule_response.status_code == 200
    assert len(schedule_response.json()) == 6
    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == LoanStatus.PUBLISHED
    assert events_response.status_code == 200
    assert [event["event_type"] for event in events_response.json()] == [
        "created",
        "published",
    ]


@pytest.mark.django_db
def test_non_admin_cannot_use_loan_admin_api(client: Client, investor: Model) -> None:
    client.force_login(cast(Any, investor))

    response = client.get("/api/v1/loans/admin/loans/")

    assert response.status_code == 403
    assert Loan.objects.count() == 0


@pytest.mark.django_db
def test_loan_events_are_append_only(admin_user: Model) -> None:
    borrower = _borrower(admin_user)
    loan = create_loan(_loan_command(admin_user, borrower))
    event = LoanEvent.objects.get(loan=loan, event_type="created")

    event.note = "changed"
    with pytest.raises(AppendOnlyViolation):
        event.save()
    with pytest.raises(AppendOnlyViolation):
        LoanEvent.objects.filter(id=event.id).update(note="changed")
    with pytest.raises(AppendOnlyViolation):
        LoanEvent.objects.filter(id=event.id).delete()

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("UPDATE loans_loanevent SET note = %s WHERE id = %s", ["x", event.id])

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM loans_loanevent WHERE id = %s", [event.id])


@pytest.mark.django_db
def test_loan_installments_are_append_only(admin_user: Model) -> None:
    borrower = _borrower(admin_user)
    loan = create_loan(_loan_command(admin_user, borrower))
    installment = loan.installments.order_by("installment_number").first()
    assert installment is not None

    installment.total_minor += 1
    with pytest.raises(AppendOnlyViolation):
        installment.save()
    with pytest.raises(AppendOnlyViolation):
        loan.installments.filter(id=installment.id).update(total_minor=installment.total_minor)
    with pytest.raises(AppendOnlyViolation):
        loan.installments.filter(id=installment.id).delete()

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE loans_loaninstallment SET total_minor = %s WHERE id = %s",
                [installment.total_minor, installment.id],
            )

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM loans_loaninstallment WHERE id = %s", [installment.id])
