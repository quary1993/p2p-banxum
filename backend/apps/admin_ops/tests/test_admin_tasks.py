from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

import pytest
from django.db import DatabaseError, connection, transaction
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
    UpdateAdminTaskCommand,
    create_admin_task,
    update_admin_task,
)
from backend.apps.admin_ops.tests.factories import create_user
from backend.apps.platform_core.models import AuditEvent, DomainEvent
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
