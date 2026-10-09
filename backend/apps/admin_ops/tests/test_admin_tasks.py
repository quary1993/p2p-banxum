from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.admin_ops.models import (
    AdminTask,
    AdminTaskEvent,
    AdminTaskPriority,
    AdminTaskStatus,
    AdminTaskType,
)
from backend.apps.admin_ops.services import (
    AdminTaskAuthorizationError,
    AdminTaskValidationError,
    CreateAdminTaskCommand,
    EnsureLoanDefaultReviewTaskCommand,
    UpdateAdminTaskCommand,
    create_admin_task,
    ensure_loan_default_review_task,
    update_admin_task,
)
from backend.apps.admin_ops.tests.factories import create_user
from backend.apps.platform_core.models import AuditEvent, DomainEvent, OutboxMessage
from backend.apps.platform_core.models.base import AppendOnlyViolation


@pytest.fixture
def admin_user() -> Model:
    return create_user(email="admin@example.test")


@pytest.fixture
def assigned_admin() -> Model:
    return create_user(email="assigned@example.test")


@pytest.fixture
def investor() -> Model:
    return create_user(
        email="investor@example.test",
        account_type="natural_person_lender",
        is_staff=False,
    )


@pytest.mark.django_db
def test_admin_can_create_and_resolve_task(admin_user: Model, assigned_admin: Model) -> None:
    due_at = timezone.now() + timedelta(hours=4)

    task = create_admin_task(
        CreateAdminTaskCommand(
            actor=admin_user,
            task_type=AdminTaskType.KYC_MANUAL_REVIEW,
            title="Review PEP match",
            priority=AdminTaskPriority.HIGH,
            assigned_admin_id=str(assigned_admin.pk),
            due_at=due_at,
            notes="Provider flagged PEP.",
            related_object_type="KycVerificationCase",
            related_object_id="case-123",
        )
    )

    assert task.status == AdminTaskStatus.OPEN
    assert task.assigned_admin_id == assigned_admin.pk
    assert AdminTaskEvent.objects.filter(task=task, event_type="created").exists()
    assert AuditEvent.objects.filter(action="admin_task.created", target_id=str(task.id)).exists()
    assert DomainEvent.objects.filter(
        event_type="AdminTaskCreated",
        aggregate_id=str(task.id),
    ).exists()

    resolved = update_admin_task(
        UpdateAdminTaskCommand(
            actor=admin_user,
            task_id=str(task.id),
            status=AdminTaskStatus.RESOLVED,
            completion_note="Approved by compliance.",
        )
    )

    assert resolved.status == AdminTaskStatus.RESOLVED
    assert resolved.completed_at is not None
    assert resolved.completion_note == "Approved by compliance."
    assert AdminTaskEvent.objects.filter(task=task, event_type="status_changed").exists()
    assert DomainEvent.objects.filter(
        event_type="AdminTaskUpdated",
        aggregate_id=str(task.id),
    ).exists()


@pytest.mark.django_db
def test_non_admin_cannot_create_task(investor: Model) -> None:
    with pytest.raises(AdminTaskAuthorizationError):
        create_admin_task(
            CreateAdminTaskCommand(
                actor=investor,
                task_type=AdminTaskType.SUPPORT,
                title="Should fail",
            )
        )


@pytest.mark.django_db
def test_task_assignment_requires_active_admin(admin_user: Model, investor: Model) -> None:
    with pytest.raises(AdminTaskValidationError):
        create_admin_task(
            CreateAdminTaskCommand(
                actor=admin_user,
                task_type=AdminTaskType.SUPPORT,
                title="Bad assignment",
                assigned_admin_id=str(investor.pk),
            )
        )


@pytest.mark.django_db
def test_admin_task_api_create_filter_update_and_events(
    client: Client,
    admin_user: Model,
    assigned_admin: Model,
) -> None:
    client.force_login(cast(Any, admin_user))

    create_response = client.post(
        "/api/v1/admin-ops/tasks/",
        data={
            "task_type": AdminTaskType.PAYMENT_RECONCILIATION,
            "title": "Match bank inflow",
            "priority": AdminTaskPriority.URGENT,
            "assigned_admin_id": str(assigned_admin.pk),
            "related_object_type": "BankOperation",
            "related_object_id": "bank-op-1",
            "notes": "Incoming payment needs review.",
        },
        content_type="application/json",
    )

    assert create_response.status_code == 201
    task_id = create_response.json()["id"]

    list_response = client.get(
        "/api/v1/admin-ops/tasks/",
        data={
            "status": AdminTaskStatus.OPEN,
            "task_type": AdminTaskType.PAYMENT_RECONCILIATION,
            "assigned_admin_id": str(assigned_admin.pk),
        },
    )
    patch_response = client.patch(
        f"/api/v1/admin-ops/tasks/{task_id}/",
        data={
            "status": AdminTaskStatus.IN_PROGRESS,
            "notes": "Finance started matching the transfer.",
        },
        content_type="application/json",
    )
    events_response = client.get(f"/api/v1/admin-ops/tasks/{task_id}/events/")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == task_id
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == AdminTaskStatus.IN_PROGRESS
    assert events_response.status_code == 200
    assert [event["event_type"] for event in events_response.json()] == [
        "created",
        "status_changed",
    ]


@pytest.mark.django_db
def test_admin_task_api_filters_pending_finance_workstream(
    client: Client,
    admin_user: Model,
) -> None:
    open_finance = create_admin_task(
        CreateAdminTaskCommand(
            actor=admin_user,
            task_type=AdminTaskType.PAYOUT_INSTRUCTION_VERIFICATION,
            title="Verify investor payout IBAN",
            related_object_type="InvestorPayoutInstruction",
            related_object_id="payout-1",
        )
    )
    create_admin_task(
        CreateAdminTaskCommand(
            actor=admin_user,
            task_type=AdminTaskType.KYC_MANUAL_REVIEW,
            title="Review investor KYC",
        )
    )
    resolved_finance = create_admin_task(
        CreateAdminTaskCommand(
            actor=admin_user,
            task_type=AdminTaskType.FX_SETTLEMENT,
            title="Declare settled FX batch",
        )
    )
    update_admin_task(
        UpdateAdminTaskCommand(
            actor=admin_user,
            task_id=str(resolved_finance.id),
            status=AdminTaskStatus.RESOLVED,
            completion_note="Settled.",
        )
    )

    client.force_login(cast(Any, admin_user))
    response = client.get(
        "/api/v1/admin-ops/tasks/",
        data={"pending_only": "true", "workstream": "finance"},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(open_finance.id)]


@pytest.mark.django_db
def test_admin_audit_log_endpoint_is_admin_only(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    task = create_admin_task(
        CreateAdminTaskCommand(
            actor=admin_user,
            task_type=AdminTaskType.REPORTING,
            title="Prepare month-end export",
        )
    )

    client.force_login(cast(Any, investor))
    forbidden = client.get("/api/v1/admin-ops/audit-events/")
    assert forbidden.status_code == 403

    client.force_login(cast(Any, admin_user))
    response = client.get(
        "/api/v1/admin-ops/audit-events/",
        data={"action": "admin_task.created", "target_id": str(task.id)},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["target_id"] == str(task.id)
    search_event = AuditEvent.objects.get(action="audit_event.search_performed")
    assert search_event.actor_id == str(admin_user.pk)
    assert search_event.metadata["filters"] == {
        "action": "admin_task.created",
        "target_id": str(task.id),
        "limit": 100,
    }
    assert search_event.metadata["result_count"] == 1


@pytest.mark.django_db
def test_admin_task_events_are_append_only(admin_user: Model) -> None:
    task = create_admin_task(
        CreateAdminTaskCommand(
            actor=admin_user,
            task_type=AdminTaskType.SUPPORT,
            title="Support follow-up",
        )
    )
    event = AdminTaskEvent.objects.get(task=task, event_type="created")

    event.note = "changed"
    with pytest.raises(AppendOnlyViolation):
        event.save()
    with pytest.raises(AppendOnlyViolation):
        AdminTaskEvent.objects.filter(id=event.id).update(note="changed")
    with pytest.raises(AppendOnlyViolation):
        AdminTaskEvent.objects.filter(id=event.id).delete()

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE admin_ops_admintaskevent SET note = %s WHERE id = %s",
                ["changed", event.id],
            )

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM admin_ops_admintaskevent WHERE id = %s",
                [event.id],
            )


@pytest.mark.django_db
def test_task_update_rejects_empty_change(admin_user: Model) -> None:
    task = create_admin_task(
        CreateAdminTaskCommand(
            actor=admin_user,
            task_type=AdminTaskType.SUPPORT,
            title="Support follow-up",
        )
    )

    with pytest.raises(AdminTaskValidationError):
        update_admin_task(UpdateAdminTaskCommand(actor=admin_user, task_id=str(task.id)))

    assert AdminTask.objects.get(id=task.id).status == AdminTaskStatus.OPEN


def _loan_default_command(
    actor: Model,
    *,
    loan_id: str = "6f1c1a52-6a39-4d1e-8f43-0a8d1f6f9e10",
    as_of_date: date = date(2026, 11, 27),
) -> EnsureLoanDefaultReviewTaskCommand:
    return EnsureLoanDefaultReviewTaskCommand(
        actor=actor,
        loan_id=loan_id,
        loan_title="QA Direct Reprice Test",
        product_type="direct",
        currency="CHF",
        as_of_date=as_of_date,
        days_past_due=16,
        outstanding_minor=1_366_67,
        triggering_due_date=date(2026, 11, 11),
    )


@pytest.mark.django_db
def test_loan_default_review_task_is_single_per_loan_and_reopens_when_closed(
    admin_user: Model,
    investor: Model,
) -> None:
    alerts = OutboxMessage.objects.filter(topic="email.loan_defaulted")

    with pytest.raises(AdminTaskAuthorizationError):
        ensure_loan_default_review_task(_loan_default_command(investor))

    task = ensure_loan_default_review_task(_loan_default_command(admin_user))
    assert task.task_type == AdminTaskType.LOAN_RISK_REVIEW
    assert task.related_object_type == "LoanDefault"
    assert task.status == AdminTaskStatus.OPEN
    assert "Overdue installment outstanding: CHF 1'366.67" in task.notes
    assert alerts.count() == 1

    # Calling again while the task is open changes nothing and sends no new alert.
    again = ensure_loan_default_review_task(_loan_default_command(admin_user))
    assert again.id == task.id
    assert AdminTask.objects.filter(task_type=AdminTaskType.LOAN_RISK_REVIEW).count() == 1
    assert AdminTaskEvent.objects.filter(task=task).count() == 1
    assert alerts.count() == 1

    # The database refuses a second default-review task for the same loan.
    with pytest.raises(IntegrityError), transaction.atomic():
        AdminTask.objects.create(
            task_type=AdminTaskType.LOAN_RISK_REVIEW,
            title="Duplicate",
            created_by=cast(Any, admin_user),
            related_object_type="LoanDefault",
            related_object_id=task.related_object_id,
        )

    # A resolved task is reopened (not duplicated) if the loan defaults again.
    update_admin_task(
        UpdateAdminTaskCommand(
            actor=admin_user,
            task_id=str(task.id),
            status=AdminTaskStatus.RESOLVED,
            completion_note="Recovery plan agreed.",
        )
    )
    reopened = ensure_loan_default_review_task(
        _loan_default_command(admin_user, as_of_date=date(2027, 1, 20))
    )
    assert reopened.id == task.id
    assert reopened.status == AdminTaskStatus.OPEN
    assert reopened.completed_at is None
    assert alerts.count() == 2

    # A different loan gets its own task.
    other = ensure_loan_default_review_task(
        _loan_default_command(admin_user, loan_id="0b6c3a1e-58d7-4f0f-9a43-2f5d4c7e8a91")
    )
    assert other.id != task.id


def _pending_payout_iban_task(investor: Model) -> tuple[Any, AdminTask]:
    from importlib import import_module

    from backend.apps.platform_core.tests.factories import issue_sensitive_action_test_code

    _approve_investor(investor)
    ledger = import_module("backend.apps.ledger.services")
    code = issue_sensitive_action_test_code(investor, "bank_account_change")
    instruction = ledger.register_investor_self_service_payout_instruction(
        ledger.RegisterInvestorSelfServicePayoutInstructionCommand(
            actor=investor,
            currency="CHF",
            destination_iban="CH5604835012345678009",
            destination_account_name="Task Investor",
            sensitive_action_code_id=code.code_id,
            sensitive_action_code=code.raw_code,
        )
    )
    task = AdminTask.objects.get(
        task_type=AdminTaskType.PAYOUT_INSTRUCTION_VERIFICATION,
        related_object_id=str(instruction.pk),
    )
    return instruction, task


def _approve_investor(investor: Model) -> None:
    from django.apps import apps

    cast(Any, investor).phone_verified_at = timezone.now()
    investor.save(update_fields=["phone_verified_at"])
    apps.get_model("kyc_compliance", "KycVerificationCase").objects.update_or_create(
        user_id=investor.pk,
        defaults={
            "subject_reference": f"user:{investor.pk}",
            "provider_environment": "test",
            "workflow_id": "test-workflow",
            "vendor_data": f"user:{investor.pk}",
            "status": "approved",
            "decision_at": timezone.now(),
        },
    )


@pytest.mark.django_db
def test_payout_iban_task_cannot_be_closed_while_the_iban_is_pending(
    admin_user: Model,
    investor: Model,
) -> None:
    from importlib import import_module

    instruction, task = _pending_payout_iban_task(investor)

    for status in (AdminTaskStatus.RESOLVED, AdminTaskStatus.CANCELLED):
        with pytest.raises(AdminTaskValidationError, match="Verify or reject the IBAN first"):
            update_admin_task(
                UpdateAdminTaskCommand(actor=admin_user, task_id=str(task.id), status=status)
            )
    task.refresh_from_db()
    assert task.status == AdminTaskStatus.OPEN

    ledger = import_module("backend.apps.ledger.services")
    ledger.verify_investor_payout_instruction(
        ledger.VerifyInvestorPayoutInstructionCommand(
            actor=admin_user,
            instruction_id=str(instruction.pk),
            evidence_reference="bank-letter:task",
        )
    )
    task.refresh_from_db()
    assert task.status == AdminTaskStatus.RESOLVED


@pytest.mark.django_db
def test_task_edit_without_status_change_records_no_status_pair(admin_user: Model) -> None:
    task = create_admin_task(
        CreateAdminTaskCommand(
            actor=admin_user,
            task_type=AdminTaskType.OTHER,
            title="Close the month",
        )
    )
    update_admin_task(
        UpdateAdminTaskCommand(actor=admin_user, task_id=str(task.id), status="resolved")
    )
    update_admin_task(
        UpdateAdminTaskCommand(actor=admin_user, task_id=str(task.id), notes="Filed the report.")
    )

    events = list(AdminTaskEvent.objects.filter(task=task).order_by("occurred_at", "id"))
    status_event = next(event for event in events if event.event_type == "status_changed")
    notes_event = next(event for event in events if event.event_type == "updated")
    assert (status_event.previous_status, status_event.new_status) == ("open", "resolved")
    # No "Resolved -> Resolved" line for a notes edit (MONEY-24).
    assert (notes_event.previous_status, notes_event.new_status) == ("", "")
