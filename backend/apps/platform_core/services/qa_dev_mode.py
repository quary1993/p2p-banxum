from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.db import models, transaction
from django.utils import timezone

from backend.apps.platform_core.domain.access import actor_ref_for_user, is_superadmin_actor
from backend.apps.platform_core.domain.time import (
    business_date,
    business_timezone,
    to_business_time,
)
from backend.apps.platform_core.models.qa import QaDevModeState
from backend.apps.platform_core.models.scheduled_jobs import ScheduledJobRunStatus
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event
from backend.apps.platform_core.services.scheduled_jobs import (
    DAILY_JOB_NAMES,
    DEFAULT_SCHEDULED_JOB_NAMES,
    EMAIL_OUTBOX_DISPATCH_JOB,
    RunScheduledJobsCommand,
    run_scheduled_jobs,
)

QA_DEV_MODE_CACHE_KEY = "platform_core:qa_dev_mode:current_time"
QA_DEV_MODE_DISABLED_CACHE_VALUE = "disabled"
QA_DEV_MODE_SINGLETON_ID = 1
QA_REVERT_CONFIRMATION = "REVERT QA DB"


class QaDevModeError(RuntimeError):
    pass


class QaDevModeAuthorizationError(QaDevModeError):
    pass


class QaDevModeValidationError(QaDevModeError):
    pass


@dataclass(frozen=True, slots=True)
class EnableQaDevModeCommand:
    actor: models.Model
    note: str = ""


@dataclass(frozen=True, slots=True)
class AdvanceQaDevModeTimeCommand:
    actor: models.Model
    days: int


@dataclass(frozen=True, slots=True)
class RevertQaDevModeCommand:
    actor: models.Model
    confirmation: str


def _clear_cached_time() -> None:
    cache.delete(QA_DEV_MODE_CACHE_KEY)


def _cache_current_time(value: datetime | None) -> None:
    if value is None:
        _clear_cached_time()
        return
    cache.set(QA_DEV_MODE_CACHE_KEY, value, timeout=None)


def _qa_enabled_by_settings() -> bool:
    return bool(getattr(settings, "QA_DEV_MODE_ALLOWED", False)) and not bool(
        getattr(settings, "IS_PRODUCTION", False)
    )


def _assert_qa_allowed() -> None:
    if bool(getattr(settings, "IS_PRODUCTION", False)):
        raise QaDevModeValidationError("QA development mode is never allowed in production.")
    if not bool(getattr(settings, "QA_DEV_MODE_ALLOWED", False)):
        raise QaDevModeValidationError(
            "QA development mode is disabled by deployment config."
        )


def _require_superadmin_actor(actor: models.Model) -> None:
    if not is_superadmin_actor(actor):
        raise QaDevModeAuthorizationError("Only an active superadmin can manage QA mode.")


def _snapshot_dir() -> Path:
    path = Path(str(getattr(settings, "QA_DEV_MODE_SNAPSHOT_DIR", ""))).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _snapshot_filename(*, created_at: datetime) -> str:
    stamp = created_at.astimezone(business_timezone()).strftime("%Y%m%dT%H%M%S%z")
    return f"qa-dev-mode-entry-{stamp}.json"


def _create_database_snapshot(*, created_at: datetime) -> str:
    target = _snapshot_dir() / _snapshot_filename(created_at=created_at)
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=str(_snapshot_dir()),
        suffix=".json.tmp",
        encoding="utf-8",
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        call_command(
            "dumpdata",
            exclude=["contenttypes", "auth.Permission", "sessions.Session"],
            indent=2,
            output=str(tmp_path),
            verbosity=0,
        )
        tmp_path.replace(target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return str(target)


def _restore_database_snapshot(snapshot_path: str) -> None:
    path = Path(snapshot_path)
    if not path.exists():
        raise QaDevModeValidationError("QA snapshot file is missing; database was not changed.")
    call_command("flush", interactive=False, verbosity=0)
    call_command("loaddata", str(path), verbosity=0)


def _state_for_update() -> QaDevModeState:
    state, _created = QaDevModeState.objects.select_for_update().get_or_create(
        singleton_id=QA_DEV_MODE_SINGLETON_ID
    )
    return state


def get_qa_dev_mode_state() -> QaDevModeState:
    if not _qa_enabled_by_settings():
        _clear_cached_time()
    state, _created = QaDevModeState.objects.get_or_create(
        singleton_id=QA_DEV_MODE_SINGLETON_ID
    )
    return state


def qa_time_override_from_db() -> datetime | None:
    if not _qa_enabled_by_settings():
        return None
    cached = cache.get(QA_DEV_MODE_CACHE_KEY)
    if isinstance(cached, datetime):
        return cached
    if cached == QA_DEV_MODE_DISABLED_CACHE_VALUE:
        return None
    try:
        state = QaDevModeState.objects.only("is_enabled", "current_time").get(
            singleton_id=QA_DEV_MODE_SINGLETON_ID
        )
    except QaDevModeState.DoesNotExist:
        cache.set(QA_DEV_MODE_CACHE_KEY, QA_DEV_MODE_DISABLED_CACHE_VALUE, timeout=5)
        return None
    if not state.is_enabled or state.current_time is None:
        cache.set(QA_DEV_MODE_CACHE_KEY, QA_DEV_MODE_DISABLED_CACHE_VALUE, timeout=5)
        return None
    _cache_current_time(state.current_time)
    return state.current_time


def _record_qa_event(
    *,
    actor: models.Model,
    action: str,
    state: QaDevModeState,
    metadata: dict[str, Any],
) -> None:
    actor_ref = actor_ref_for_user(actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action=action,
            target_type="QaDevModeState",
            target_id=str(state.singleton_id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="QaDevModeChanged",
            aggregate_type="QaDevModeState",
            aggregate_id=str(state.singleton_id),
            payload={"action": action, **metadata},
            idempotency_key=f"qa-dev-mode:{action}:{state.updated_at.isoformat()}",
        )
    )


def serialize_qa_dev_mode_state(state: QaDevModeState) -> dict[str, Any]:
    return {
        "allowed": _qa_enabled_by_settings(),
        "is_enabled": state.is_enabled if _qa_enabled_by_settings() else False,
        "current_time": state.current_time,
        "entered_at": state.entered_at,
        "entered_by_user_id": state.entered_by_user_id,
        "snapshot_created_at": state.snapshot_created_at,
        "has_snapshot": bool(state.snapshot_path),
        "note": state.note,
        "last_advanced_at": state.last_advanced_at,
        "last_advance_summary": state.last_advance_summary,
        "max_advance_days": int(getattr(settings, "QA_DEV_MODE_MAX_ADVANCE_DAYS", 120)),
        "environment": str(getattr(settings, "ENVIRONMENT", "local")),
    }


def enable_qa_dev_mode(command: EnableQaDevModeCommand) -> QaDevModeState:
    _assert_qa_allowed()
    _require_superadmin_actor(command.actor)
    real_now = timezone.now()
    with transaction.atomic():
        state = _state_for_update()
        if state.is_enabled:
            _cache_current_time(state.current_time)
            return state
        snapshot_path = _create_database_snapshot(created_at=real_now)
        state.is_enabled = True
        state.entered_at = real_now
        state.entered_by_user_id = command.actor.pk
        state.current_time = real_now
        state.snapshot_path = snapshot_path
        state.snapshot_created_at = real_now
        state.note = command.note[:2000]
        state.last_advanced_at = None
        state.last_advance_summary = {}
        state.save(
            update_fields=[
                "is_enabled",
                "entered_at",
                "entered_by_user_id",
                "current_time",
                "snapshot_path",
                "snapshot_created_at",
                "note",
                "last_advanced_at",
                "last_advance_summary",
                "updated_at",
            ]
        )
        _cache_current_time(real_now)
        _record_qa_event(
            actor=command.actor,
            action="platform_core.qa_dev_mode.enabled",
            state=state,
            metadata={
                "current_time": real_now.isoformat(),
                "snapshot_created_at": real_now.isoformat(),
                "note": state.note,
            },
        )
        return state


def _midday_for_business_date(value: datetime, *, days_delta: int) -> datetime:
    local = to_business_time(value) + timedelta(days=days_delta)
    return datetime.combine(local.date(), time(hour=12), tzinfo=business_timezone())


def _scheduled_result_payload(result: Any) -> list[dict[str, Any]]:
    return [
        {
            "job_name": job_result.job_name,
            "run_key": job_result.run_key,
            "status": job_result.status,
            "run_id": job_result.run_id,
            "error": job_result.error,
            "summary": job_result.summary,
        }
        for job_result in result.results
    ]


def advance_qa_dev_mode_time(command: AdvanceQaDevModeTimeCommand) -> QaDevModeState:
    _assert_qa_allowed()
    _require_superadmin_actor(command.actor)
    max_days = int(getattr(settings, "QA_DEV_MODE_MAX_ADVANCE_DAYS", 120))
    if command.days < 1 or command.days > max_days:
        raise QaDevModeValidationError(f"Advance days must be between 1 and {max_days}.")

    with transaction.atomic():
        state = _state_for_update()
        if not state.is_enabled or state.current_time is None:
            raise QaDevModeValidationError("Enable QA development mode before advancing time.")
        start_time = state.current_time
        target_time = start_time + timedelta(days=command.days)
        state.current_time = target_time
        state.last_advanced_at = timezone.now()
        state.save(update_fields=["current_time", "last_advanced_at", "updated_at"])
        _cache_current_time(target_time)

    run_batches: list[dict[str, Any]] = []
    start_date = business_date(start_time)
    target_date = business_date(target_time)
    crossed_days = (target_date - start_date).days
    for day_index in range(1, crossed_days + 1):
        as_of = _midday_for_business_date(start_time, days_delta=day_index)
        QaDevModeState.objects.filter(singleton_id=QA_DEV_MODE_SINGLETON_ID).update(
            current_time=as_of,
            updated_at=timezone.now(),
        )
        _cache_current_time(as_of)
        daily_result = run_scheduled_jobs(
            RunScheduledJobsCommand(
                job_names=tuple(
                    job_name
                    for job_name in DEFAULT_SCHEDULED_JOB_NAMES
                    if job_name in DAILY_JOB_NAMES
                ),
                as_of=as_of,
                actor=command.actor,
            )
        )
        email_result = run_scheduled_jobs(
            RunScheduledJobsCommand(
                job_names=(EMAIL_OUTBOX_DISPATCH_JOB,),
                as_of=as_of,
                actor=command.actor,
            )
        )
        run_batches.append(
            {
                "as_of": as_of.isoformat(),
                "business_date": business_date(as_of).isoformat(),
                "results": _scheduled_result_payload(daily_result)
                + _scheduled_result_payload(email_result),
            }
        )

    QaDevModeState.objects.filter(singleton_id=QA_DEV_MODE_SINGLETON_ID).update(
        current_time=target_time,
        updated_at=timezone.now(),
    )
    _cache_current_time(target_time)
    final_email_result = run_scheduled_jobs(
        RunScheduledJobsCommand(
            job_names=(EMAIL_OUTBOX_DISPATCH_JOB,),
            as_of=target_time,
            actor=command.actor,
        )
    )
    run_batches.append(
        {
            "as_of": target_time.isoformat(),
            "business_date": business_date(target_time).isoformat(),
            "results": _scheduled_result_payload(final_email_result),
        }
    )
    failed_jobs = [
        result
        for batch in run_batches
        for result in batch["results"]
        if result["status"] == ScheduledJobRunStatus.FAILED
    ]
    summary = {
        "start_time": start_time.isoformat(),
        "target_time": target_time.isoformat(),
        "advanced_days": command.days,
        "crossed_business_dates": crossed_days,
        "batches": run_batches,
        "failed_count": len(failed_jobs),
    }
    with transaction.atomic():
        state = _state_for_update()
        state.current_time = target_time
        state.last_advanced_at = timezone.now()
        state.last_advance_summary = summary
        state.save(
            update_fields=[
                "current_time",
                "last_advanced_at",
                "last_advance_summary",
                "updated_at",
            ]
        )
        _record_qa_event(
            actor=command.actor,
            action="platform_core.qa_dev_mode.time_advanced",
            state=state,
            metadata={
                "advanced_days": command.days,
                "target_time": target_time.isoformat(),
                "failed_count": len(failed_jobs),
            },
        )
    return state


def revert_qa_dev_mode(command: RevertQaDevModeCommand) -> None:
    _assert_qa_allowed()
    _require_superadmin_actor(command.actor)
    if command.confirmation != QA_REVERT_CONFIRMATION:
        raise QaDevModeValidationError(f'Type "{QA_REVERT_CONFIRMATION}" to revert QA mode.')
    with transaction.atomic():
        state = _state_for_update()
        if not state.is_enabled:
            raise QaDevModeValidationError("QA development mode is not enabled.")
        snapshot_path = state.snapshot_path
        if not snapshot_path:
            raise QaDevModeValidationError("QA snapshot path is missing; database was not changed.")
        metadata = {
            "snapshot_created_at": (
                state.snapshot_created_at.isoformat() if state.snapshot_created_at else ""
            ),
            "current_time": state.current_time.isoformat() if state.current_time else "",
        }
        _record_qa_event(
            actor=command.actor,
            action="platform_core.qa_dev_mode.revert_requested",
            state=state,
            metadata=metadata,
        )
    _clear_cached_time()
    _restore_database_snapshot(snapshot_path)


def qa_dev_mode_snapshot_manifest() -> dict[str, Any]:
    state = get_qa_dev_mode_state()
    if not state.snapshot_path:
        return {}
    path = Path(state.snapshot_path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def qa_dev_mode_state_json() -> str:
    return json.dumps(serialize_qa_dev_mode_state(get_qa_dev_mode_state()), default=_json_default)


def remove_snapshot_file(path: str) -> None:
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def copy_snapshot_to(path: str, target: str) -> None:
    shutil.copyfile(path, target)
