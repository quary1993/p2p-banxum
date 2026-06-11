from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib import import_module
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, models, transaction

from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.time import business_date, now_utc, to_business_time
from backend.apps.platform_core.models.scheduled_jobs import (
    ScheduledJobRun,
    ScheduledJobRunStatus,
)
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event

EMAIL_OUTBOX_DISPATCH_JOB = "email_outbox_dispatch"
BALANCE_AGEING_SCAN_JOB = "balance_ageing_scan"
LOAN_SERVICING_STATUS_SCAN_JOB = "loan_servicing_status_scan"
PRIMARY_FUNDING_EXPIRY_SCAN_JOB = "primary_funding_expiry_scan"
RECONCILIATION_BREAK_TASK_SYNC_JOB = "reconciliation_break_task_sync"

DEFAULT_SCHEDULED_JOB_NAMES = (
    EMAIL_OUTBOX_DISPATCH_JOB,
    BALANCE_AGEING_SCAN_JOB,
    LOAN_SERVICING_STATUS_SCAN_JOB,
    PRIMARY_FUNDING_EXPIRY_SCAN_JOB,
    RECONCILIATION_BREAK_TASK_SYNC_JOB,
)
ALL_SCHEDULED_JOB_NAMES = frozenset(DEFAULT_SCHEDULED_JOB_NAMES)
ADMIN_ACTOR_JOB_NAMES = frozenset(DEFAULT_SCHEDULED_JOB_NAMES) - {EMAIL_OUTBOX_DISPATCH_JOB}
DAILY_JOB_NAMES = frozenset(DEFAULT_SCHEDULED_JOB_NAMES) - {EMAIL_OUTBOX_DISPATCH_JOB}


class ScheduledJobError(RuntimeError):
    pass


class ScheduledJobValidationError(ScheduledJobError):
    pass


@dataclass(frozen=True, slots=True)
class RunScheduledJobsCommand:
    job_names: tuple[str, ...] = DEFAULT_SCHEDULED_JOB_NAMES
    as_of: datetime | None = None
    actor: models.Model | None = None
    force: bool = False
    email_limit: int | None = None
    balance_currency: str | None = None
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class ScheduledJobExecutionResult:
    job_name: str
    run_key: str
    status: str
    summary: dict[str, Any]
    error: str = ""
    run_id: str = ""


@dataclass(frozen=True, slots=True)
class ScheduledJobsResult:
    as_of: datetime
    results: tuple[ScheduledJobExecutionResult, ...]


def _unique_job_names(job_names: tuple[str, ...]) -> tuple[str, ...]:
    if not job_names:
        return DEFAULT_SCHEDULED_JOB_NAMES
    unique: list[str] = []
    for job_name in job_names:
        if job_name not in unique:
            unique.append(job_name)
    unknown = sorted(set(unique) - ALL_SCHEDULED_JOB_NAMES)
    if unknown:
        raise ScheduledJobValidationError(f"Unknown scheduled job(s): {', '.join(unknown)}.")
    return tuple(unique)


def _validate_dry_run_scope(*, dry_run: bool, job_names: tuple[str, ...]) -> None:
    if dry_run and job_names != (BALANCE_AGEING_SCAN_JOB,):
        raise ScheduledJobValidationError(
            "--dry-run is supported only for balance_ageing_scan. "
            "Select --job balance_ageing_scan or omit --dry-run."
        )


def _requires_admin_actor(job_names: tuple[str, ...]) -> bool:
    return any(job_name in ADMIN_ACTOR_JOB_NAMES for job_name in job_names)


def _active_admin_queryset() -> Any:
    user_model = get_user_model()
    return user_model.objects.filter(is_active=True, is_staff=True).order_by(
        "-is_superuser",
        "email",
    )


def _resolve_scheduled_job_actor(
    *,
    actor: models.Model | None,
    job_names: tuple[str, ...],
) -> models.Model | None:
    if not _requires_admin_actor(job_names):
        return None
    if actor is not None:
        if not is_admin_actor(actor):
            raise ScheduledJobValidationError("Scheduled job actor must be an active admin.")
        return actor

    actor_email = str(getattr(settings, "SCHEDULED_JOBS_ACTOR_EMAIL", "")).strip()
    if actor_email:
        user = _active_admin_queryset().filter(email__iexact=actor_email).first()
        if user is None or not is_admin_actor(user):
            raise ScheduledJobValidationError(
                "SCHEDULED_JOBS_ACTOR_EMAIL must point to an active admin account."
            )
        return cast(models.Model, user)

    environment = str(getattr(settings, "ENVIRONMENT", "local"))
    if environment not in {"local", "test"}:
        raise ScheduledJobValidationError(
            "SCHEDULED_JOBS_ACTOR_EMAIL is required for non-local scheduled jobs."
        )

    user = next(
        (candidate for candidate in _active_admin_queryset() if is_admin_actor(candidate)),
        None,
    )
    if user is None:
        raise ScheduledJobValidationError(
            "No active admin account is available for scheduled jobs."
        )
    return cast(models.Model, user)


def _scheduled_job_run_key(job_name: str, *, as_of: datetime, force: bool) -> str:
    local_time = to_business_time(as_of)
    if job_name == EMAIL_OUTBOX_DISPATCH_JOB:
        bucket = local_time.replace(second=0, microsecond=0).isoformat()
    elif job_name in DAILY_JOB_NAMES:
        bucket = business_date(as_of).isoformat()
    else:
        bucket = local_time.isoformat()
    run_key = f"{job_name}:{bucket}"
    if force:
        run_key = f"{run_key}:force:{uuid.uuid4()}"
    return run_key


def _running_timeout() -> timedelta:
    minutes = max(1, int(getattr(settings, "SCHEDULED_JOBS_RUNNING_TIMEOUT_MINUTES", 120)))
    return timedelta(minutes=minutes)


def _is_stale_running_run(job_run: ScheduledJobRun, *, now: datetime) -> bool:
    if job_run.status != ScheduledJobRunStatus.RUNNING:
        return False
    return job_run.started_at <= now - _running_timeout()


def _claim_job_run(
    *,
    job_name: str,
    run_key: str,
    scheduled_for: datetime,
    actor: models.Model | None,
) -> tuple[ScheduledJobRun, bool]:
    actor_user_id = getattr(actor, "pk", None)
    started_at = now_utc()
    try:
        with transaction.atomic():
            existing = (
                ScheduledJobRun.objects.select_for_update()
                .filter(run_key=run_key)
                .first()
            )
            if existing is not None:
                stale_running = _is_stale_running_run(existing, now=started_at)
                was_failed = existing.status == ScheduledJobRunStatus.FAILED
                if was_failed or stale_running:
                    previous_started_at = existing.started_at
                    previous_summary = dict(existing.summary or {})
                    existing.status = ScheduledJobRunStatus.RUNNING
                    existing.scheduled_for = scheduled_for
                    existing.started_at = started_at
                    existing.finished_at = None
                    existing.actor_user_id = actor_user_id
                    existing.error = ""
                    existing.summary = {
                        "retry_of_failed_run": was_failed,
                        "reclaimed_stale_running_run": stale_running,
                        "previous_started_at": previous_started_at.isoformat(),
                        "previous_summary": previous_summary,
                        "running_timeout_minutes": int(_running_timeout().total_seconds() // 60),
                    }
                    existing.attempt_count += 1
                    existing.save(
                        update_fields=[
                            "status",
                            "scheduled_for",
                            "started_at",
                            "finished_at",
                            "actor_user_id",
                            "error",
                            "summary",
                            "attempt_count",
                            "updated_at",
                        ]
                    )
                    return existing, True
                return existing, False
            return (
                ScheduledJobRun.objects.create(
                    job_name=job_name,
                    run_key=run_key,
                    status=ScheduledJobRunStatus.RUNNING,
                    scheduled_for=scheduled_for,
                    started_at=started_at,
                    actor_user_id=actor_user_id,
                ),
                True,
            )
    except IntegrityError:
        existing = ScheduledJobRun.objects.get(run_key=run_key)
        return existing, False


def _complete_job_run(
    *,
    job_run: ScheduledJobRun,
    status: str,
    summary: dict[str, Any],
    error: str = "",
) -> ScheduledJobRun:
    job_run.status = status
    job_run.summary = summary
    job_run.error = error[:4000]
    job_run.finished_at = now_utc()
    job_run.save(update_fields=["status", "summary", "error", "finished_at", "updated_at"])
    return job_run


def _record_scheduled_job_evidence(
    *,
    job_run: ScheduledJobRun,
    actor: models.Model | None,
) -> None:
    actor_ref = actor_ref_for_user(actor) if actor is not None else ActorRef.system()
    metadata = {
        "job_name": job_run.job_name,
        "run_key": job_run.run_key,
        "status": job_run.status,
        "attempt_count": job_run.attempt_count,
        "summary": job_run.summary,
        "error": job_run.error,
    }
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action=f"platform_core.scheduled_job.{job_run.status}",
            target_type="ScheduledJobRun",
            target_id=str(job_run.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="ScheduledJobRunRecorded",
            aggregate_type="ScheduledJobRun",
            aggregate_id=str(job_run.id),
            payload=metadata,
            idempotency_key=f"scheduled-job-run:{job_run.id}:{job_run.status}",
        )
    )


def _email_outbox_dispatch_summary(
    command: RunScheduledJobsCommand,
    as_of: datetime,
) -> dict[str, Any]:
    services: Any = import_module("backend.apps.communications.services")
    result = services.dispatch_due_email_outbox_messages(
        services.DispatchEmailOutboxCommand(limit=command.email_limit, now=as_of)
    )
    return {
        "processed_count": result.processed_count,
        "sent_count": result.sent_count,
        "failed_count": result.failed_count,
        "dead_letter_count": result.dead_letter_count,
        "skipped_count": result.skipped_count,
        "message_ids": list(result.message_ids),
    }


def _balance_ageing_summary(
    command: RunScheduledJobsCommand,
    *,
    actor: models.Model,
    as_of: datetime,
) -> dict[str, Any]:
    services: Any = import_module("backend.apps.ledger.services")
    result = services.run_balance_ageing_scan(
        services.RunBalanceAgeingScanCommand(
            actor=actor,
            as_of=as_of,
            currency=command.balance_currency,
            dry_run=command.dry_run,
        )
    )
    return {
        "as_of": result.as_of.isoformat(),
        "currency": command.balance_currency or "",
        "dry_run": command.dry_run,
        "reminders_due_count": len(result.reminders_due),
        "forced_withdrawal_candidate_count": len(result.forced_withdrawal_candidates),
        "forced_withdrawal_request_count": len(result.forced_withdrawal_requests),
        "penalty_mode_transition_count": len(result.penalty_mode_transitions),
        "skipped_lot_ids": list(result.skipped_lot_ids),
        "forced_withdrawal_request_ids": [
            str(withdrawal_request.id)
            for withdrawal_request in result.forced_withdrawal_requests
        ],
    }


def _loan_servicing_status_summary(
    *,
    actor: models.Model,
    as_of: datetime,
) -> dict[str, Any]:
    services: Any = import_module("backend.apps.servicing.services")
    as_of_date = business_date(as_of)
    result = services.scan_loan_servicing_statuses(
        services.ScanLoanServicingStatusesCommand(actor=actor, as_of_date=as_of_date)
    )
    return {
        "as_of_date": result.as_of_date.isoformat(),
        "change_count": len(result.changes),
        "changes": [
            {
                "loan_id": change.loan_id,
                "previous_status": change.previous_status,
                "new_status": change.new_status,
                "days_past_due": change.days_past_due,
                "outstanding_minor": change.outstanding_minor,
            }
            for change in result.changes
        ],
    }


def _primary_funding_expiry_summary(
    *,
    actor: models.Model,
    as_of: datetime,
) -> dict[str, Any]:
    services: Any = import_module("backend.apps.marketplace_primary.services")
    as_of_date = business_date(as_of)
    result = services.scan_expired_primary_loan_funding(
        services.ScanExpiredPrimaryFundingCommand(
            actor=actor,
            as_of_date=as_of_date,
            idempotency_key=f"scheduled-primary-expiry:{as_of_date.isoformat()}",
            limit=1000,
        )
    )
    return {
        "as_of_date": result["as_of_date"].isoformat(),
        "scanned_count": result["scanned_count"],
        "cancelled_count": result["cancelled_count"],
        "skipped_count": result["skipped_count"],
        "cancellation_ids": [
            str(cancellation.id) for cancellation in result.get("cancellations", [])
        ],
        "skipped": list(result.get("skipped", [])),
    }


def _reconciliation_break_task_sync_summary(*, actor: models.Model) -> dict[str, Any]:
    services: Any = import_module("backend.apps.admin_ops.services")
    result = services.sync_reconciliation_break_tasks(
        services.SyncReconciliationBreakTasksCommand(actor=actor, limit=500)
    )
    return {
        "created_count": result["created_count"],
        "existing_count": result["existing_count"],
        "skipped_count": result["skipped_count"],
        "task_ids": [str(task.id) for task in result.get("tasks", [])],
    }


def _execute_scheduled_job(
    *,
    job_name: str,
    command: RunScheduledJobsCommand,
    actor: models.Model | None,
    as_of: datetime,
) -> dict[str, Any]:
    if job_name == EMAIL_OUTBOX_DISPATCH_JOB:
        return _email_outbox_dispatch_summary(command, as_of)
    if actor is None:
        raise ScheduledJobValidationError(f"{job_name} requires an admin actor.")
    if job_name == BALANCE_AGEING_SCAN_JOB:
        return _balance_ageing_summary(command, actor=actor, as_of=as_of)
    if job_name == LOAN_SERVICING_STATUS_SCAN_JOB:
        return _loan_servicing_status_summary(actor=actor, as_of=as_of)
    if job_name == PRIMARY_FUNDING_EXPIRY_SCAN_JOB:
        return _primary_funding_expiry_summary(actor=actor, as_of=as_of)
    if job_name == RECONCILIATION_BREAK_TASK_SYNC_JOB:
        return _reconciliation_break_task_sync_summary(actor=actor)
    raise ScheduledJobValidationError(f"Unknown scheduled job: {job_name}.")


def run_scheduled_jobs(command: RunScheduledJobsCommand | None = None) -> ScheduledJobsResult:
    command = command or RunScheduledJobsCommand()
    as_of = command.as_of or now_utc()
    to_business_time(as_of)
    job_names = _unique_job_names(command.job_names)
    _validate_dry_run_scope(dry_run=command.dry_run, job_names=job_names)
    actor = _resolve_scheduled_job_actor(actor=command.actor, job_names=job_names)

    results: list[ScheduledJobExecutionResult] = []
    for job_name in job_names:
        run_key = _scheduled_job_run_key(job_name, as_of=as_of, force=command.force)
        job_run, should_run = _claim_job_run(
            job_name=job_name,
            run_key=run_key,
            scheduled_for=as_of,
            actor=actor if job_name in ADMIN_ACTOR_JOB_NAMES else None,
        )
        if not should_run:
            results.append(
                ScheduledJobExecutionResult(
                    job_name=job_name,
                    run_key=run_key,
                    status=ScheduledJobRunStatus.SKIPPED,
                    run_id=str(job_run.id),
                    summary={
                        "existing_status": job_run.status,
                        "existing_summary": job_run.summary,
                    },
                )
            )
            continue
        try:
            summary = _execute_scheduled_job(
                job_name=job_name,
                command=command,
                actor=actor,
                as_of=as_of,
            )
            _complete_job_run(
                job_run=job_run,
                status=ScheduledJobRunStatus.SUCCEEDED,
                summary=summary,
            )
            _record_scheduled_job_evidence(job_run=job_run, actor=actor)
            results.append(
                ScheduledJobExecutionResult(
                    job_name=job_name,
                    run_key=run_key,
                    status=ScheduledJobRunStatus.SUCCEEDED,
                    run_id=str(job_run.id),
                    summary=summary,
                )
            )
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            _complete_job_run(
                job_run=job_run,
                status=ScheduledJobRunStatus.FAILED,
                summary={},
                error=error,
            )
            _record_scheduled_job_evidence(job_run=job_run, actor=actor)
            results.append(
                ScheduledJobExecutionResult(
                    job_name=job_name,
                    run_key=run_key,
                    status=ScheduledJobRunStatus.FAILED,
                    run_id=str(job_run.id),
                    summary={},
                    error=error,
                )
            )
    return ScheduledJobsResult(as_of=as_of, results=tuple(results))
