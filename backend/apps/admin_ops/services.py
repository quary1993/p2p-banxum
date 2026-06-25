from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count, Model, Sum
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
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event


class AdminOpsError(ValueError):
    pass


class AdminTaskAuthorizationError(AdminOpsError):
    pass


class AdminTaskValidationError(AdminOpsError):
    pass


KYC_ADMIN_REVIEW_STATUSES = frozenset(
    {
        "declined",
        "manual_review",
        "high_risk",
        "sanctions_hit",
        "pep_hit",
        "adverse_media_hit",
        "reverification_required",
    }
)
LOAN_FUNDING_STATUS = "published"
LOAN_SERVICING_STATUSES = frozenset({"funded", "late"})
LOAN_RISK_STATUSES = frozenset({"late", "defaulted", "written_off"})
BANK_OPERATION_EXCEPTION_STATUSES = frozenset({"pending_review", "unmatched"})
WITHDRAWAL_REQUESTED_STATUS = "requested"
BALANCE_AVAILABLE_STATUS = "available"
BALANCE_FROZEN_STATUS = "frozen"
BALANCE_PENALTY_MODE_STATUS = "penalty_mode"
SECONDARY_APPROVAL_REQUESTED_STATUS = "approval_requested"
OUTBOX_DEAD_LETTER_STATUS = "dead_letter"


def _actor_account_type(actor: Model) -> str:
    return str(getattr(actor, "account_type", ""))


def _require_admin_actor(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise AdminTaskAuthorizationError("Only an active admin can manage admin tasks.")


def _actor_for_admin(actor: Model) -> ActorRef:
    return actor_ref_for_user(actor)


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
    if admin is None or not is_admin_actor(admin):
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


def _model(app_label: str, model_name: str) -> Any:
    return apps.get_model(app_label, model_name)


def _documents_services() -> Any:
    return import_module("backend.apps.documents.services")


def _servicing_services() -> Any:
    return import_module("backend.apps.servicing.services")


def _currency_code(instance: Any) -> str:
    currency = getattr(instance, "currency", None)
    code = getattr(currency, "code", None)
    if code:
        return str(code)
    currency_id = getattr(instance, "currency_id", "")
    return str(currency_id)


def _sum_minor(queryset: Any, field: str) -> int:
    aggregate = queryset.aggregate(total=Sum(field))
    return int(aggregate["total"] or 0)


def _queue_item(
    *,
    kind: str,
    item_id: str,
    title: str,
    status: str = "",
    priority: str = "",
    due_at: datetime | None = None,
    due_date: date | None = None,
    currency: str = "",
    amount_minor: int | None = None,
    object_type: str = "",
    object_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": item_id,
        "title": title,
        "status": status,
        "priority": priority,
        "due_at": due_at,
        "due_date": due_date,
        "currency": currency,
        "amount_minor": amount_minor,
        "object_type": object_type,
        "object_id": object_id,
        "metadata": metadata or {},
    }


def _currency_summary_defaults(currency_code: str) -> dict[str, Any]:
    return {
        "currency": currency_code,
        "available_balance_minor": 0,
        "investable_available_minor": 0,
        "withdraw_only_available_minor": 0,
        "overdue_available_minor": 0,
        "frozen_available_minor": 0,
        "penalty_mode_available_minor": 0,
        "pending_withdrawal_minor": 0,
        "forced_withdrawal_minor": 0,
        "pending_bank_operation_minor": 0,
        "fx_unsettled_sold_minor": 0,
        "fx_unsettled_bought_minor": 0,
        "fx_unsettled_fee_minor": 0,
    }


def _currency_summary(
    summaries: dict[str, dict[str, Any]],
    currency_code: str,
) -> dict[str, Any]:
    if currency_code not in summaries:
        summaries[currency_code] = _currency_summary_defaults(currency_code)
    return summaries[currency_code]


def _reconciliation_break_signals(snapshot: Any) -> list[str]:
    signals: list[str] = []
    if int(getattr(snapshot, "reconciliation_difference_minor", 0)) != 0:
        signals.append("reconciliation_difference")
    metadata = cast(dict[str, Any], getattr(snapshot, "metadata", {}) or {})
    if metadata.get("account_sign_anomalies"):
        signals.append("account_sign_anomalies")
    if metadata.get("investor_balance_integrity_breaks"):
        signals.append("investor_balance_integrity_breaks")
    return signals


def _reconciliation_break_task_priority(signals: list[str]) -> AdminTaskPriority:
    if "investor_balance_integrity_breaks" in signals or "account_sign_anomalies" in signals:
        return AdminTaskPriority.URGENT
    return AdminTaskPriority.HIGH


def _reconciliation_break_task_title(snapshot: Any, signals: list[str]) -> str:
    signal_label = ", ".join(signal.replace("_", " ") for signal in signals)
    return (
        f"Reconciliation exception {getattr(snapshot, 'currency_id', '')} "
        f"{getattr(snapshot, 'as_of_date', '')}: {signal_label}"
    )


def _reconciliation_break_task_notes(snapshot: Any, signals: list[str]) -> str:
    metadata = cast(dict[str, Any], getattr(snapshot, "metadata", {}) or {})
    account_anomalies = metadata.get("account_sign_anomalies") or []
    investor_breaks = metadata.get("investor_balance_integrity_breaks") or []
    return "\n".join(
        [
            "Auto-created from a reconciliation snapshot integrity signal.",
            f"Snapshot ID: {snapshot.pk}",
            f"Currency: {getattr(snapshot, 'currency_id', '')}",
            f"As-of date: {getattr(snapshot, 'as_of_date', '')}",
            f"Signals: {', '.join(signals)}",
            (
                "Reconciliation difference minor: "
                f"{int(getattr(snapshot, 'reconciliation_difference_minor', 0))}"
            ),
            f"Bank stated balance minor: {int(getattr(snapshot, 'bank_stated_balance_minor', 0))}",
            (
                "Investor balance liability minor: "
                f"{int(getattr(snapshot, 'investor_balance_liability_minor', 0))}"
            ),
            (
                "Bank-to-collection-cash difference minor: "
                f"{int(metadata.get('bank_to_collection_cash_difference_minor') or 0)}"
            ),
            f"Account sign anomalies: {len(account_anomalies)}",
            f"Investor balance integrity breaks: {len(investor_breaks)}",
            (
                "Resolve this task only after finance/admin confirms the break is "
                "corrected, explained, or accepted as operational evidence."
            ),
        ]
    )


def _existing_reconciliation_break_task(snapshot: Any) -> AdminTask | None:
    return (
        AdminTask.objects.filter(
            task_type=AdminTaskType.PAYMENT_RECONCILIATION,
            related_object_type="ReconciliationSnapshot",
            related_object_id=str(snapshot.pk),
        )
        .order_by("-created_at", "-id")
        .first()
    )


@dataclass(frozen=True, slots=True)
class GetAdminDashboardCommand:
    actor: Model
    as_of: datetime | None = None
    due_window_days: int = 7
    queue_limit: int = 10


@dataclass(frozen=True, slots=True)
class SyncReconciliationBreakTasksCommand:
    actor: Model
    limit: int = 100


@dataclass(frozen=True, slots=True)
class ListAdminUserDocumentsCommand:
    actor: Model
    user_id: str


@dataclass(frozen=True, slots=True)
class RenderAdminUserDocumentCommand:
    actor: Model
    user_id: str
    acceptance_id: str
    output_format: str = "pdf"


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


def _document_subject_user(user_id: str) -> Model:
    user = get_user_model().objects.filter(id=user_id).first()
    if user is None:
        raise AdminTaskValidationError("User was not found.")
    return cast(Model, user)


def list_admin_user_documents(command: ListAdminUserDocumentsCommand) -> dict[str, Any]:
    _require_admin_actor(command.actor)
    subject = _document_subject_user(command.user_id)
    acceptance_model = _model("documents", "DocumentAcceptanceEvidence")
    documents = _documents_services()
    acceptances = (
        acceptance_model.objects.filter(user_id=subject.pk)
        .select_related("template", "template_version")
        .order_by("-accepted_at", "-id")
    )
    document_rows = [documents.acceptance_history_item(acceptance) for acceptance in acceptances]
    payload = {
        "user": {
            "id": str(subject.pk),
            "email": str(getattr(subject, "email", "")),
            "full_name": str(getattr(subject, "full_name", "")),
            "investor_reference": str(getattr(subject, "investor_reference", "") or ""),
            "account_type": str(getattr(subject, "account_type", "")),
            "status": str(getattr(subject, "status", "")),
        },
        "documents": document_rows,
        "disclaimer": (
            "Accepted-document artifacts are generated on demand from immutable clickwrap "
            "evidence. "
            "The generation is audited to the admin actor, not to the user."
        ),
    }
    record_audit_event(
        AuditCommand(
            actor=_actor_for_admin(command.actor),
            action="admin_user_documents.listed",
            target_type="User",
            target_id=str(subject.pk),
            metadata={"document_count": len(document_rows)},
        )
    )
    return payload


def render_admin_user_document(command: RenderAdminUserDocumentCommand) -> dict[str, Any]:
    _require_admin_actor(command.actor)
    subject = _document_subject_user(command.user_id)
    acceptance_model = _model("documents", "DocumentAcceptanceEvidence")
    acceptance = acceptance_model.objects.filter(
        id=command.acceptance_id,
        user_id=subject.pk,
    ).first()
    if acceptance is None:
        raise AdminTaskValidationError("Document evidence was not found for this user.")
    documents = _documents_services()
    try:
        artifact = documents.render_document_acceptance_artifact(
            documents.RenderDocumentAcceptanceArtifactCommand(
                actor=command.actor,
                acceptance_id=str(acceptance.pk),
                output_format=command.output_format,
                purpose="admin_download",
                metadata={
                    "source": "admin_users",
                    "download_subject_user_id": str(subject.pk),
                    "download_actor_user_id": str(command.actor.pk),
                },
            )
        )
    except documents.DocumentAuthorizationError as exc:
        raise AdminTaskAuthorizationError(str(exc)) from exc
    except documents.DocumentValidationError as exc:
        raise AdminTaskValidationError(str(exc)) from exc
    return {
        "rendered_artifact_id": str(artifact.rendered_artifact.id),
        "content_type": artifact.content_type,
        "filename": artifact.filename,
        "content_encoding": artifact.content_encoding,
        "content": artifact.content,
        "content_sha256": artifact.content_sha256,
        "manifest": artifact.manifest,
    }


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


def sync_reconciliation_break_tasks(
    command: SyncReconciliationBreakTasksCommand,
) -> dict[str, Any]:
    _require_admin_actor(command.actor)
    limit = max(1, min(command.limit, 500))
    reconciliation_model = _model("ledger", "ReconciliationSnapshot")
    created_tasks: list[AdminTask] = []
    existing_tasks: list[AdminTask] = []
    skipped_count = 0
    synced_at = now_utc()

    for snapshot in (
        reconciliation_model.objects.select_related("currency")
        .order_by("-as_of_date", "-created_at", "-id")[:limit]
    ):
        break_signals = _reconciliation_break_signals(snapshot)
        if not break_signals:
            skipped_count += 1
            continue
        existing = _existing_reconciliation_break_task(snapshot)
        if existing is not None:
            existing_tasks.append(existing)
            continue

        try:
            task = create_admin_task(
                CreateAdminTaskCommand(
                    actor=command.actor,
                    task_type=AdminTaskType.PAYMENT_RECONCILIATION,
                    title=_reconciliation_break_task_title(snapshot, break_signals),
                    priority=_reconciliation_break_task_priority(break_signals),
                    due_at=synced_at,
                    notes=_reconciliation_break_task_notes(snapshot, break_signals),
                    related_object_type="ReconciliationSnapshot",
                    related_object_id=str(snapshot.pk),
                )
            )
        except IntegrityError:
            existing = _existing_reconciliation_break_task(snapshot)
            if existing is None:
                raise
            existing_tasks.append(existing)
            continue
        created_tasks.append(task)

    metadata = {
        "limit": limit,
        "created_count": len(created_tasks),
        "existing_count": len(existing_tasks),
        "skipped_count": skipped_count,
        "created_task_ids": [str(task.id) for task in created_tasks],
        "existing_task_ids": [str(task.id) for task in existing_tasks],
    }
    record_audit_event(
        AuditCommand(
            actor=_actor_for_admin(command.actor),
            action="admin_ops.reconciliation_break_tasks_synced",
            target_type="AdminTask",
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="ReconciliationBreakTasksSynced",
            aggregate_type="AdminOps",
            aggregate_id=str(command.actor.pk),
            payload=metadata,
            idempotency_key=(
                "admin-ops:reconciliation-break-tasks-synced:"
                f"{command.actor.pk}:{synced_at.isoformat()}"
            ),
        )
    )
    return {
        "created_count": len(created_tasks),
        "existing_count": len(existing_tasks),
        "skipped_count": skipped_count,
        "tasks": [*created_tasks, *existing_tasks],
    }


def get_admin_operations_dashboard(command: GetAdminDashboardCommand) -> dict[str, Any]:
    _require_admin_actor(command.actor)
    as_of = command.as_of or now_utc()
    as_of_day = business_date(as_of)
    due_window_days = max(0, min(command.due_window_days, 60))
    queue_limit = max(1, min(command.queue_limit, 50))
    due_window_end = as_of_day + timedelta(days=due_window_days)

    currency_summaries: dict[str, dict[str, Any]] = {}
    queues: dict[str, list[dict[str, Any]]] = {
        "admin_tasks": [],
        "kyc_reviews": [],
        "bank_operations_pending": [],
        "withdrawals_requested": [],
        "forced_withdrawals_requested": [],
        "balance_ageing_actions": [],
        "funding_loans": [],
        "servicing_due": [],
        "loan_risk": [],
        "secondary_listing_approvals": [],
        "fx_settlement_deltas": [],
        "failed_emails": [],
        "reconciliation_breaks": [],
    }

    open_task_queryset = AdminTask.objects.exclude(status__in=TERMINAL_ADMIN_TASK_STATUSES)
    overdue_task_count = open_task_queryset.filter(due_at__lt=as_of).count()
    for task in (
        open_task_queryset.select_related("assigned_admin")
        .order_by("due_at", "-created_at", "id")[:queue_limit]
    ):
        queues["admin_tasks"].append(
            _queue_item(
                kind="admin_task",
                item_id=str(task.id),
                title=task.title,
                status=task.status,
                priority=task.priority,
                due_at=task.due_at,
                object_type=task.related_object_type,
                object_id=task.related_object_id,
                metadata={
                    "task_type": task.task_type,
                    "assigned_admin_id": str(task.assigned_admin_id or ""),
                },
            )
        )

    kyc_case_model = _model("kyc_compliance", "KycVerificationCase")
    kyc_review_queryset = kyc_case_model.objects.filter(status__in=KYC_ADMIN_REVIEW_STATUSES)
    for case in kyc_review_queryset.order_by("-updated_at", "-created_at", "id")[:queue_limit]:
        queues["kyc_reviews"].append(
            _queue_item(
                kind="kyc_review",
                item_id=str(case.pk),
                title=f"KYC review required: {getattr(case, 'subject_reference', '')}",
                status=str(getattr(case, "status", "")),
                object_type="KycVerificationCase",
                object_id=str(case.pk),
                metadata={
                    "subject_type": str(getattr(case, "subject_type", "")),
                    "subject_reference": str(getattr(case, "subject_reference", "")),
                    "provider": str(getattr(case, "provider", "")),
                    "manual_review_required": bool(
                        getattr(case, "manual_review_required", False)
                    ),
                },
            )
        )

    bank_operation_model = _model("ledger", "BankOperation")
    bank_exception_queryset = bank_operation_model.objects.filter(
        status__in=BANK_OPERATION_EXCEPTION_STATUSES
    ).select_related("currency")
    for row in (
        bank_exception_queryset.values("currency_id")
        .annotate(total=Sum("amount_minor"))
        .order_by("currency_id")
    ):
        summary = _currency_summary(currency_summaries, str(row["currency_id"]))
        summary["pending_bank_operation_minor"] = int(row["total"] or 0)
    for operation in bank_exception_queryset.order_by("-value_date", "-confirmed_at", "-id")[
        :queue_limit
    ]:
        queues["bank_operations_pending"].append(
            _queue_item(
                kind="bank_operation",
                item_id=str(operation.pk),
                title=f"{getattr(operation, 'operation_type', '')} pending reconciliation",
                status=str(getattr(operation, "status", "")),
                due_date=getattr(operation, "value_date", None),
                currency=_currency_code(operation),
                amount_minor=int(getattr(operation, "amount_minor", 0)),
                object_type=str(getattr(operation, "linked_object_type", "")),
                object_id=str(getattr(operation, "linked_object_id", "")),
                metadata={
                    "bank_reference": str(getattr(operation, "bank_reference", "")),
                    "payment_reference": str(getattr(operation, "payment_reference", "")),
                },
            )
        )

    withdrawal_model = _model("ledger", "InvestorWithdrawalRequest")
    requested_withdrawals = withdrawal_model.objects.filter(
        status=WITHDRAWAL_REQUESTED_STATUS
    ).select_related("currency")
    forced_withdrawals = requested_withdrawals.filter(is_forced=True)
    for row in (
        requested_withdrawals.values("currency_id")
        .annotate(total=Sum("amount_minor"))
        .order_by("currency_id")
    ):
        summary = _currency_summary(currency_summaries, str(row["currency_id"]))
        summary["pending_withdrawal_minor"] = int(row["total"] or 0)
    for row in (
        forced_withdrawals.values("currency_id")
        .annotate(total=Sum("amount_minor"))
        .order_by("currency_id")
    ):
        summary = _currency_summary(currency_summaries, str(row["currency_id"]))
        summary["forced_withdrawal_minor"] = int(row["total"] or 0)
    for request in requested_withdrawals.order_by("requested_at", "id")[:queue_limit]:
        item = _queue_item(
            kind="withdrawal_request",
            item_id=str(request.pk),
            title="Investor withdrawal awaiting bank execution",
            status=str(getattr(request, "status", "")),
            due_at=getattr(request, "requested_at", None),
            currency=_currency_code(request),
            amount_minor=int(getattr(request, "amount_minor", 0)),
            object_type="InvestorWithdrawalRequest",
            object_id=str(request.pk),
            metadata={
                "investor_user_id": str(getattr(request, "investor_user_id", "")),
                "is_forced": bool(getattr(request, "is_forced", False)),
            },
        )
        queues["withdrawals_requested"].append(item)
        if (
            getattr(request, "is_forced", False)
            and len(queues["forced_withdrawals_requested"]) < queue_limit
        ):
            queues["forced_withdrawals_requested"].append(item)

    balance_lot_model = _model("ledger", "InvestorBalanceLot")
    active_lots = balance_lot_model.objects.filter(available_amount_minor__gt=0).select_related(
        "currency"
    )
    balance_lots_overdue_count = 0
    balance_lots_penalty_mode_count = 0
    for lot in active_lots.only(
        "id",
        "investor_user_id",
        "currency",
        "status",
        "available_amount_minor",
        "investment_deadline_at",
        "withdrawal_deadline_at",
        "source_type",
    ):
        lot_ref = cast(Any, lot)
        currency_code = _currency_code(lot)
        summary = _currency_summary(currency_summaries, currency_code)
        amount = int(lot_ref.available_amount_minor)
        summary["available_balance_minor"] += amount
        status = str(lot_ref.status)
        if status == BALANCE_AVAILABLE_STATUS:
            if lot_ref.withdrawal_deadline_at < as_of:
                summary["overdue_available_minor"] += amount
                balance_lots_overdue_count += 1
                if len(queues["balance_ageing_actions"]) < queue_limit:
                    queues["balance_ageing_actions"].append(
                        _queue_item(
                            kind="balance_lot_overdue",
                            item_id=str(lot.pk),
                            title="Balance lot past 60-day withdrawal deadline",
                            status=status,
                            due_at=getattr(lot, "withdrawal_deadline_at", None),
                            currency=currency_code,
                            amount_minor=amount,
                            object_type="InvestorBalanceLot",
                            object_id=str(lot.pk),
                            metadata={
                                "investor_user_id": str(lot_ref.investor_user_id),
                                "source_type": str(lot_ref.source_type),
                                "investment_deadline_at": (
                                    lot_ref.investment_deadline_at.isoformat()
                                ),
                                "withdrawal_deadline_at": (
                                    lot_ref.withdrawal_deadline_at.isoformat()
                                ),
                            },
                        )
                    )
            elif lot_ref.investment_deadline_at < as_of:
                summary["withdraw_only_available_minor"] += amount
            else:
                summary["investable_available_minor"] += amount
        elif status == BALANCE_FROZEN_STATUS:
            summary["frozen_available_minor"] += amount
        elif status == BALANCE_PENALTY_MODE_STATUS:
            summary["penalty_mode_available_minor"] += amount
            balance_lots_penalty_mode_count += 1
            if len(queues["balance_ageing_actions"]) < queue_limit:
                queues["balance_ageing_actions"].append(
                    _queue_item(
                        kind="balance_lot_penalty_mode",
                        item_id=str(lot.pk),
                        title="Balance lot in penalty mode awaiting usable payout IBAN",
                        status=status,
                        due_at=getattr(lot, "withdrawal_deadline_at", None),
                        currency=currency_code,
                        amount_minor=amount,
                        object_type="InvestorBalanceLot",
                        object_id=str(lot.pk),
                        metadata={
                            "investor_user_id": str(lot_ref.investor_user_id),
                            "source_type": str(lot_ref.source_type),
                        },
                    )
                )

    loan_model = _model("loans", "Loan")
    funding_loans = loan_model.objects.filter(status=LOAN_FUNDING_STATUS).select_related(
        "currency", "borrower"
    )
    for loan in funding_loans.order_by("funding_deadline", "id")[:queue_limit]:
        queues["funding_loans"].append(
            _queue_item(
                kind="funding_loan",
                item_id=str(loan.pk),
                title=str(getattr(loan, "title", "")),
                status=str(getattr(loan, "status", "")),
                due_date=getattr(loan, "funding_deadline", None),
                currency=_currency_code(loan),
                amount_minor=int(getattr(loan, "principal_minor", 0))
                - int(getattr(loan, "committed_principal_minor", 0)),
                object_type="Loan",
                object_id=str(loan.pk),
                metadata={
                    "principal_minor": int(getattr(loan, "principal_minor", 0)),
                    "committed_principal_minor": int(
                        getattr(loan, "committed_principal_minor", 0)
                    ),
                    "borrower_id": str(getattr(loan, "borrower_id", "")),
                },
            )
        )

    risk_loans = loan_model.objects.filter(status__in=LOAN_RISK_STATUSES).select_related(
        "currency", "borrower"
    )
    for loan in risk_loans.order_by("status", "funding_deadline", "id")[:queue_limit]:
        queues["loan_risk"].append(
            _queue_item(
                kind="loan_risk",
                item_id=str(loan.pk),
                title=str(getattr(loan, "title", "")),
                status=str(getattr(loan, "status", "")),
                currency=_currency_code(loan),
                amount_minor=int(getattr(loan, "principal_minor", 0)),
                object_type="Loan",
                object_id=str(loan.pk),
                metadata={"borrower_id": str(getattr(loan, "borrower_id", ""))},
            )
        )

    servicing_due_count = 0
    servicing_overdue_count = 0
    servicing = _servicing_services()
    for loan in (
        loan_model.objects.filter(status__in=LOAN_SERVICING_STATUSES)
        .select_related("currency", "borrower")
        .order_by("first_payment_date", "id")[:1000]
    ):
        snapshot = servicing.get_loan_servicing_status_snapshot(
            loan=loan,
            as_of_date=as_of_day,
        )
        if snapshot.triggering_due_date is None:
            continue
        if snapshot.triggering_due_date <= due_window_end:
            servicing_due_count += 1
            if snapshot.triggering_due_date < as_of_day:
                servicing_overdue_count += 1
            if len(queues["servicing_due"]) < queue_limit:
                queues["servicing_due"].append(
                    _queue_item(
                        kind="servicing_due",
                        item_id=str(snapshot.triggering_installment_id),
                        title=f"Borrower repayment due: {getattr(loan, 'title', '')}",
                        status=str(snapshot.status),
                        due_date=snapshot.triggering_due_date,
                        currency=_currency_code(loan),
                        amount_minor=int(snapshot.outstanding_minor),
                        object_type="LoanInstallment",
                        object_id=str(snapshot.triggering_installment_id),
                        metadata={
                            "loan_id": str(loan.pk),
                            "loan_status": str(getattr(loan, "status", "")),
                            "days_past_due": int(snapshot.days_past_due),
                        },
                    )
                )

    secondary_listing_model = _model("secondary_market", "SecondaryMarketListing")
    secondary_approval_queryset = secondary_listing_model.objects.filter(
        status=SECONDARY_APPROVAL_REQUESTED_STATUS
    ).select_related("loan", "currency")
    for listing in secondary_approval_queryset.order_by("created_at", "id")[:queue_limit]:
        listing_title = str(getattr(listing.loan, "title", ""))
        queues["secondary_listing_approvals"].append(
            _queue_item(
                kind="secondary_listing_approval",
                item_id=str(listing.pk),
                title=f"Secondary-market listing requires approval: {listing_title}",
                status=str(getattr(listing, "status", "")),
                currency=_currency_code(listing),
                amount_minor=int(getattr(listing, "current_principal_minor", 0)),
                object_type="SecondaryMarketListing",
                object_id=str(listing.pk),
                metadata={
                    "loan_id": str(getattr(listing, "loan_id", "")),
                    "loan_status_at_listing": str(
                        getattr(listing, "loan_status_at_listing", "")
                    ),
                    "days_past_due": int(getattr(listing, "days_past_due", 0)),
                    "risk_acknowledgement_required": bool(
                        getattr(listing, "risk_acknowledgement_required", False)
                    ),
                },
            )
        )

    fx_exchange_model = _model("fx", "FxExchange")
    unsettled_fx = fx_exchange_model.objects.filter(settlement_links__isnull=True)
    for row in (
        unsettled_fx.values("source_currency_id", "target_currency_id")
        .annotate(
            count=Count("id"),
            sold=Sum("source_amount_minor"),
            bought=Sum("gross_target_amount_minor"),
            credited=Sum("target_amount_minor"),
            fees=Sum("fee_minor"),
        )
        .order_by("source_currency_id", "target_currency_id")
    ):
        source_currency = str(row["source_currency_id"])
        target_currency = str(row["target_currency_id"])
        sold = int(row["sold"] or 0)
        bought = int(row["bought"] or 0)
        fees = int(row["fees"] or 0)
        _currency_summary(currency_summaries, source_currency)["fx_unsettled_sold_minor"] += sold
        target_summary = _currency_summary(currency_summaries, target_currency)
        target_summary["fx_unsettled_bought_minor"] += bought
        target_summary["fx_unsettled_fee_minor"] += fees
        queues["fx_settlement_deltas"].append(
            _queue_item(
                kind="fx_settlement_delta",
                item_id=f"{source_currency}-{target_currency}",
                title=f"Unsettled FX {source_currency}/{target_currency}",
                currency=source_currency,
                amount_minor=sold,
                object_type="FxExchange",
                metadata={
                    "source_currency": source_currency,
                    "target_currency": target_currency,
                    "exchange_count": int(row["count"] or 0),
                    "source_sold_minor": sold,
                    "gross_target_bought_minor": bought,
                    "target_credited_minor": int(row["credited"] or 0),
                    "fees_minor": fees,
                },
            )
        )
    queues["fx_settlement_deltas"] = queues["fx_settlement_deltas"][:queue_limit]

    outbox_model = _model("platform_core", "OutboxMessage")
    failed_email_queryset = outbox_model.objects.filter(
        status=OUTBOX_DEAD_LETTER_STATUS,
        topic__startswith="email.",
    )
    for message in failed_email_queryset.order_by("-updated_at", "-created_at", "id")[:queue_limit]:
        queues["failed_emails"].append(
            _queue_item(
                kind="failed_email",
                item_id=str(message.pk),
                title=f"Failed email delivery: {getattr(message, 'topic', '')}",
                status=str(getattr(message, "status", "")),
                due_at=getattr(message, "next_attempt_at", None),
                object_type="OutboxMessage",
                object_id=str(message.pk),
                metadata={
                    "topic": str(getattr(message, "topic", "")),
                    "attempts": int(getattr(message, "attempts", 0)),
                    "last_error": str(getattr(message, "last_error", ""))[:500],
                },
            )
        )

    reconciliation_model = _model("ledger", "ReconciliationSnapshot")
    reconciliation_break_count = 0
    for snapshot in (
        reconciliation_model.objects.select_related("currency")
        .order_by("-as_of_date", "-created_at", "-id")
        .all()
    ):
        break_signals = _reconciliation_break_signals(snapshot)
        if not break_signals:
            continue
        reconciliation_break_count += 1
        if len(queues["reconciliation_breaks"]) >= queue_limit:
            continue
        snapshot_metadata = cast(dict[str, Any], getattr(snapshot, "metadata", {}) or {})
        queues["reconciliation_breaks"].append(
            _queue_item(
                kind="reconciliation_break",
                item_id=str(snapshot.pk),
                title="Ledger/bank reconciliation exception",
                status="break",
                due_date=getattr(snapshot, "as_of_date", None),
                currency=_currency_code(snapshot),
                amount_minor=int(getattr(snapshot, "reconciliation_difference_minor", 0)),
                object_type="ReconciliationSnapshot",
                object_id=str(snapshot.pk),
                metadata={
                    "break_signals": break_signals,
                    "account_sign_anomaly_count": len(
                        snapshot_metadata.get("account_sign_anomalies") or []
                    ),
                    "investor_balance_integrity_break_count": len(
                        snapshot_metadata.get("investor_balance_integrity_breaks") or []
                    ),
                    "bank_stated_balance_minor": int(
                        getattr(snapshot, "bank_stated_balance_minor", 0)
                    ),
                    "investor_balance_liability_minor": int(
                        getattr(snapshot, "investor_balance_liability_minor", 0)
                    ),
                    "bank_to_collection_cash_difference_minor": int(
                        snapshot_metadata.get("bank_to_collection_cash_difference_minor") or 0
                    ),
                },
            )
        )

    summary = {
        "admin_tasks_open": open_task_queryset.count(),
        "admin_tasks_overdue": overdue_task_count,
        "kyc_review_required": kyc_review_queryset.count(),
        "bank_operations_pending": bank_exception_queryset.count(),
        "withdrawals_requested": requested_withdrawals.count(),
        "forced_withdrawals_requested": forced_withdrawals.count(),
        "published_loans": funding_loans.count(),
        "late_loans": risk_loans.filter(status="late").count(),
        "defaulted_loans": risk_loans.filter(status="defaulted").count(),
        "written_off_loans": risk_loans.filter(status="written_off").count(),
        "repayments_due_in_window": servicing_due_count,
        "repayments_overdue": servicing_overdue_count,
        "secondary_listing_approvals": secondary_approval_queryset.count(),
        "fx_unsettled_exchanges": unsettled_fx.count(),
        "failed_email_messages": failed_email_queryset.count(),
        "reconciliation_breaks": reconciliation_break_count,
        "balance_lots_overdue": balance_lots_overdue_count,
        "balance_lots_penalty_mode": balance_lots_penalty_mode_count,
    }

    return {
        "as_of": as_of,
        "as_of_date": as_of_day,
        "due_window_days": due_window_days,
        "queue_limit": queue_limit,
        "summary": summary,
        "currency_summaries": sorted(currency_summaries.values(), key=lambda row: row["currency"]),
        "queues": queues,
    }
