from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Model
from django.utils import timezone

from backend.apps.admin_ops.models import (
    TERMINAL_ADMIN_TASK_STATUSES,
    AdminTask,
    AdminTaskEvent,
    AdminTaskEventType,
    AdminTaskPriority,
    AdminTaskStatus,
    AdminTaskType,
)
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event


class AdminOpsError(ValueError):
    pass


class AdminTaskAuthorizationError(AdminOpsError):
    pass


class AdminTaskValidationError(AdminOpsError):
    pass


def _actor_account_type(actor: Model) -> str:
    return str(getattr(actor, "account_type", ""))


def _is_admin_actor(actor: Model) -> bool:
    return (
        bool(getattr(actor, "is_active", False))
        and bool(getattr(actor, "is_staff", False))
        and _actor_account_type(actor) in {"admin", "superadmin"}
        and str(getattr(actor, "status", "")) not in {"restricted", "locked", "closed"}
    )


def _require_admin_actor(actor: Model) -> None:
    if not _is_admin_actor(actor):
        raise AdminTaskAuthorizationError("Only an active admin can manage admin tasks.")


def _actor_for_admin(actor: Model) -> ActorRef:
    account_type = _actor_account_type(actor)
    return ActorRef("superadmin" if account_type == "superadmin" else "admin", str(actor.pk))


def _task_type(value: str) -> AdminTaskType:
    try:
        return AdminTaskType(value)
    except ValueError as exc:
        raise AdminTaskValidationError(f"Invalid value: {value}") from exc


def _priority(value: str) -> AdminTaskPriority:
    try:
        return AdminTaskPriority(value)
    except ValueError as exc:
        raise AdminTaskValidationError(f"Invalid value: {value}") from exc


def _status(value: str) -> AdminTaskStatus:
    try:
        return AdminTaskStatus(value)
    except ValueError as exc:
        raise AdminTaskValidationError(f"Invalid value: {value}") from exc


def _clean_required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise AdminTaskValidationError(f"{label} is required.")
    return cleaned


def _resolve_assignable_admin(admin_id: str | None) -> Model | None:
    if not admin_id:
        return None
    user_model = get_user_model()
    admin = cast(Model | None, user_model.objects.filter(id=admin_id).first())
    if admin is None or not _is_admin_actor(admin):
        raise AdminTaskValidationError("Assigned user must be an active admin.")
    return admin


def _record_task_event(
    *,
    task: AdminTask,
    actor: Model,
    event_type: AdminTaskEventType,
    previous_status: str = "",
    new_status: str = "",
    note: str = "",
    metadata: dict[str, Any] | None = None,
) -> AdminTaskEvent:
    return cast(
        AdminTaskEvent,
        AdminTaskEvent.objects.create(
            task=task,
            event_type=event_type,
            actor_user_id=actor.pk,
            actor_account_type=_actor_account_type(actor),
            previous_status=previous_status,
            new_status=new_status,
            note=note.strip(),
            metadata=metadata or {},
        ),
    )


@dataclass(frozen=True, slots=True)
class CreateAdminTaskCommand:
    actor: Model
    task_type: str
    title: str
    priority: str = AdminTaskPriority.NORMAL
    assigned_admin_id: str | None = None
    due_at: datetime | None = None
    notes: str = ""
    related_object_type: str = ""
    related_object_id: str = ""


@dataclass(frozen=True, slots=True)
class UpdateAdminTaskCommand:
    actor: Model
    task_id: str
    task_type: str | None = None
    title: str | None = None
    priority: str | None = None
    status: str | None = None
    assigned_admin_id: str | None = None
    clear_assigned_admin: bool = False
    due_at: datetime | None = None
    clear_due_at: bool = False
    notes: str | None = None
    completion_note: str | None = None


@transaction.atomic
def create_admin_task(command: CreateAdminTaskCommand) -> AdminTask:
    _require_admin_actor(command.actor)
    assigned_admin = _resolve_assignable_admin(command.assigned_admin_id)
    task = AdminTask.objects.create(
        task_type=_task_type(command.task_type),
        title=_clean_required(command.title, "Title"),
        priority=_priority(command.priority),
        assigned_admin=cast(Any, assigned_admin),
        created_by=cast(Any, command.actor),
        due_at=command.due_at,
        notes=command.notes.strip(),
        related_object_type=command.related_object_type.strip(),
        related_object_id=command.related_object_id.strip(),
    )
    metadata = {
        "task_type": task.task_type,
        "priority": task.priority,
        "status": task.status,
        "assigned_admin_id": str(task.assigned_admin_id or ""),
        "related_object_type": task.related_object_type,
        "related_object_id": task.related_object_id,
    }
    _record_task_event(
        task=task,
        actor=command.actor,
        event_type=AdminTaskEventType.CREATED,
        new_status=task.status,
        note=task.notes,
        metadata=metadata,
    )
    actor_ref = _actor_for_admin(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="admin_task.created",
            target_type="AdminTask",
            target_id=str(task.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="AdminTaskCreated",
            aggregate_type="AdminTask",
            aggregate_id=str(task.id),
            payload=metadata,
            idempotency_key=f"admin-task:{task.id}:created",
        )
    )
    return task


@transaction.atomic
def update_admin_task(command: UpdateAdminTaskCommand) -> AdminTask:
    _require_admin_actor(command.actor)
    task = AdminTask.objects.select_for_update().filter(id=command.task_id).first()
    if task is None:
        raise AdminTaskValidationError("Admin task does not exist.")

    changes: dict[str, dict[str, str]] = {}

    if command.task_type is not None:
        new_type = _task_type(command.task_type)
        if task.task_type != new_type:
            changes["task_type"] = {"previous": task.task_type, "new": new_type}
            task.task_type = new_type
    if command.title is not None:
        new_title = _clean_required(command.title, "Title")
        if task.title != new_title:
            changes["title"] = {"previous": task.title, "new": new_title}
            task.title = new_title
    if command.priority is not None:
        new_priority = _priority(command.priority)
        if task.priority != new_priority:
            changes["priority"] = {"previous": task.priority, "new": new_priority}
            task.priority = new_priority
    previous_status = task.status
    if command.status is not None:
        new_status = _status(command.status)
        if task.status != new_status:
            changes["status"] = {"previous": task.status, "new": new_status}
            task.status = new_status
            if new_status in TERMINAL_ADMIN_TASK_STATUSES:
                task.completed_at = timezone.now()
            else:
                task.completed_at = None
                task.completion_note = ""
    if command.clear_assigned_admin:
        if task.assigned_admin_id is not None:
            changes["assigned_admin_id"] = {
                "previous": str(task.assigned_admin_id),
                "new": "",
            }
            task.assigned_admin = None
    elif command.assigned_admin_id is not None:
        assigned_admin = _resolve_assignable_admin(command.assigned_admin_id)
        new_assigned_id = str(assigned_admin.pk) if assigned_admin else ""
        if str(task.assigned_admin_id or "") != new_assigned_id:
            changes["assigned_admin_id"] = {
                "previous": str(task.assigned_admin_id or ""),
                "new": new_assigned_id,
            }
            task.assigned_admin = cast(Any, assigned_admin)
    if command.clear_due_at:
        if task.due_at is not None:
            changes["due_at"] = {"previous": task.due_at.isoformat(), "new": ""}
            task.due_at = None
    elif command.due_at is not None:
        if task.due_at != command.due_at:
            changes["due_at"] = {
                "previous": task.due_at.isoformat() if task.due_at else "",
                "new": command.due_at.isoformat(),
            }
            task.due_at = command.due_at
    if command.notes is not None:
        new_notes = command.notes.strip()
        if task.notes != new_notes:
            changes["notes"] = {"previous": task.notes, "new": new_notes}
            task.notes = new_notes
    if command.completion_note is not None:
        new_completion_note = command.completion_note.strip()
        if task.completion_note != new_completion_note:
            changes["completion_note"] = {
                "previous": task.completion_note,
                "new": new_completion_note,
            }
            task.completion_note = new_completion_note

    if not changes:
        raise AdminTaskValidationError("No task changes were provided.")

    task.save(
        update_fields=[
            "task_type",
            "title",
            "priority",
            "status",
            "assigned_admin",
            "due_at",
            "notes",
            "completed_at",
            "completion_note",
            "updated_at",
        ]
    )

    event_type = AdminTaskEventType.UPDATED
    if "status" in changes:
        event_type = AdminTaskEventType.STATUS_CHANGED
    elif "assigned_admin_id" in changes:
        event_type = AdminTaskEventType.ASSIGNED
    metadata = {"changes": changes}
    event = _record_task_event(
        task=task,
        actor=command.actor,
        event_type=event_type,
        previous_status=previous_status,
        new_status=task.status,
        note=command.notes or command.completion_note or "",
        metadata=metadata,
    )
    actor_ref = _actor_for_admin(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="admin_task.updated",
            target_type="AdminTask",
            target_id=str(task.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="AdminTaskUpdated",
            aggregate_type="AdminTask",
            aggregate_id=str(task.id),
            payload=metadata,
            idempotency_key=f"admin-task:{task.id}:event:{event.id}",
        )
    )
    return task
