from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core import serializers
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection, models, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.time import (
    business_date,
    business_timezone,
    to_business_time,
)
from backend.apps.platform_core.models.qa import QaDevModeState
from backend.apps.platform_core.models.scheduled_jobs import ScheduledJobRunStatus
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event
from backend.apps.platform_core.services.qa_guard import QaEnvironmentBusy, qa_environment_guard
from backend.apps.platform_core.services.qa_restore_points import (
    read_restore_points,
    register_restore_point,
)
from backend.apps.platform_core.services.qa_snapshot import (
    partition_validated_snapshot,
    restore_snapshot_history,
)
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
    repeatable_seed_snapshot: bool = False


@dataclass(frozen=True, slots=True)
class AdvanceQaDevModeTimeCommand:
    actor: models.Model
    days: int


@dataclass(frozen=True, slots=True)
class RevertQaDevModeCommand:
    actor: models.Model
    confirmation: str
    target: str = "auto"


@dataclass(frozen=True, slots=True)
class CreateQaSnapshotCommand:
    actor: models.Model


def _clear_cached_time() -> None:
    cache.delete(QA_DEV_MODE_CACHE_KEY)


def _cache_current_time(value: datetime | None) -> None:
    if value is None:
        _clear_cached_time()
        return
    cache.set(QA_DEV_MODE_CACHE_KEY, value, timeout=None)


def _qa_enabled_by_settings() -> bool:
    return (
        bool(getattr(settings, "QA_DEV_MODE_ALLOWED", False))
        and not bool(getattr(settings, "IS_PRODUCTION", False))
        and str(getattr(settings, "ENVIRONMENT", "local")).lower() not in {"production", "prod"}
    )


def qa_controls_available(actor: Any) -> bool:
    return _qa_enabled_by_settings() and is_admin_actor(actor)


def qa_deployment_available() -> bool:
    return _qa_enabled_by_settings()


def _assert_qa_allowed() -> None:
    if bool(getattr(settings, "IS_PRODUCTION", False)) or str(
        getattr(settings, "ENVIRONMENT", "local")
    ).lower() in {"production", "prod"}:
        raise QaDevModeValidationError("QA development mode is never allowed in production.")
    if not bool(getattr(settings, "QA_DEV_MODE_ALLOWED", False)):
        raise QaDevModeValidationError("QA development mode is disabled by deployment config.")


def _require_qa_admin_actor(actor: models.Model) -> None:
    if not is_admin_actor(actor):
        raise QaDevModeAuthorizationError("Only an active admin can manage QA mode.")


def _snapshot_dir() -> Path:
    path = Path(str(getattr(settings, "QA_DEV_MODE_SNAPSHOT_DIR", ""))).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _snapshot_filename(*, created_at: datetime) -> str:
    stamp = created_at.astimezone(business_timezone()).strftime("%Y%m%dT%H%M%S%f%z")
    return f"qa-dev-mode-entry-{stamp}.json"


def _schema_signature() -> list[str]:
    return sorted(
        f"{app}.{name}" for app, name in MigrationRecorder(connection).applied_migrations()
    )


def _lock_database_tables() -> None:
    if connection.vendor == "postgresql":
        names = sorted(connection.introspection.table_names())
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute(
                "LOCK TABLE "
                + ", ".join(connection.ops.quote_name(name) for name in names)
                + " IN ACCESS EXCLUSIVE MODE"
            )


@contextmanager
def _exclusive_qa_operation() -> Iterator[None]:
    try:
        with qa_environment_guard(exclusive=True):
            yield
    except QaEnvironmentBusy as exc:
        raise QaDevModeValidationError(str(exc)) from exc
    except Exception:
        _clear_cached_time()
        raise


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
        serializers.register_serializer(
            "qa_snapshot", "backend.apps.platform_core.services.qa_snapshot"
        )
        call_command(
            "dumpdata",
            format="qa_snapshot",
            use_base_manager=True,
            exclude=["contenttypes", "auth.Permission", "sessions.Session"],
            indent=2,
            output=str(tmp_path),
            verbosity=0,
        )
        tmp_path.replace(target)
        manifest = {
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "migrations": _schema_signature(),
        }
        manifest_path = target.with_suffix(".manifest.json")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        target.chmod(0o600)
        manifest_path.chmod(0o600)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return str(target)


def _restore_database_snapshot(snapshot_path: str) -> None:
    _assert_qa_allowed()
    path = Path(snapshot_path)
    if not path.exists():
        raise QaDevModeValidationError("QA snapshot file is missing; database was not changed.")
    try:
        content = path.read_bytes()
        manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
        if manifest.get("sha256") != hashlib.sha256(content).hexdigest():
            raise ValueError("Snapshot checksum mismatch.")
        if manifest.get("migrations") != _schema_signature():
            raise ValueError("Database schema changed since the snapshot was created.")
        # Check model/field names and fixture structure before touching live rows.
        objects = list(serializers.deserialize("json", content.decode("utf-8")))
        fixture_content, history = partition_validated_snapshot(content, objects)
    except Exception as exc:
        raise QaDevModeValidationError(
            "QA snapshot validation failed; database was not changed. " + str(exc)
        ) from exc
    with connection.constraint_checks_disabled(), transaction.atomic():
        _lock_database_tables()
        triggers: list[tuple[str, str]] = []
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
                    "AND name LIKE '%append_only%'"
                )
                triggers = cursor.fetchall()
                for name, _sql in triggers:
                    cursor.execute(f"DROP TRIGGER {connection.ops.quote_name(name)}")
        call_command("flush", interactive=False, verbosity=0)
        # Load the validated non-history rows, never re-read a mutable snapshot path.
        with tempfile.NamedTemporaryFile(suffix=".json") as validated:
            validated.write(fixture_content)
            validated.flush()
            call_command("loaddata", validated.name, verbosity=0)
        restore_snapshot_history(history)
        with connection.cursor() as cursor:
            for _name, sql in triggers:
                cursor.execute(sql)
        connection.check_constraints()
    _clear_cached_time()


def _state_for_update() -> QaDevModeState:
    state, _created = QaDevModeState.objects.select_for_update().get_or_create(
        singleton_id=QA_DEV_MODE_SINGLETON_ID
    )
    return state


def get_qa_dev_mode_state() -> QaDevModeState:
    if not _qa_enabled_by_settings():
        _clear_cached_time()
    state, _created = QaDevModeState.objects.get_or_create(singleton_id=QA_DEV_MODE_SINGLETON_ID)
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
    points = _restore_points(state) if _qa_enabled_by_settings() else {}
    snapshot = points.get("snapshot", {})
    seed = points.get("seed", {})
    return {
        "allowed": _qa_enabled_by_settings(),
        "is_enabled": state.is_enabled if _qa_enabled_by_settings() else False,
        "current_time": state.current_time,
        "entered_at": state.entered_at,
        "entered_by_user_id": state.entered_by_user_id,
        "snapshot_created_at": snapshot.get("created_at"),
        "has_snapshot": bool(snapshot),
        "seed_created_at": seed.get("created_at"),
        "has_seed": bool(seed),
        "default_restore_target": "snapshot" if snapshot else "seed",
        "note": state.note,
        "last_advanced_at": state.last_advanced_at,
        "last_advance_summary": state.last_advance_summary,
        "max_advance_days": int(getattr(settings, "QA_DEV_MODE_MAX_ADVANCE_DAYS", 120)),
        "environment": str(getattr(settings, "ENVIRONMENT", "local")),
    }


def enable_qa_dev_mode(command: EnableQaDevModeCommand) -> QaDevModeState:
    _assert_qa_allowed()
    _require_qa_admin_actor(command.actor)
    with _exclusive_qa_operation():
        return _enable_qa_dev_mode(command)


def _enable_qa_dev_mode(command: EnableQaDevModeCommand) -> QaDevModeState:
    _assert_qa_allowed()
    _require_qa_admin_actor(command.actor)
    real_now = timezone.now()
    with transaction.atomic():
        _lock_database_tables()
        state = _state_for_update()
        if state.is_enabled:
            _cache_current_time(state.current_time)
            return state
        snapshot_path = (
            str(_snapshot_dir() / _snapshot_filename(created_at=real_now))
            if command.repeatable_seed_snapshot
            else _create_database_snapshot(created_at=real_now)
        )
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
        if command.repeatable_seed_snapshot:
            # Include the enabled clock and its own snapshot pointer. Restoring this
            # baseline can be repeated without capturing a later, already-used dataset.
            _create_database_snapshot(created_at=real_now)
        transaction.on_commit(
            lambda: register_restore_point(
                kind="seed" if command.repeatable_seed_snapshot else "snapshot",
                path=snapshot_path,
                created_at=real_now,
                new_seed=command.repeatable_seed_snapshot,
            )
        )
        return state


def _restore_points(state: QaDevModeState) -> dict[str, dict[str, Any]]:
    points = read_restore_points()
    if not points and state.snapshot_path and state.snapshot_created_at:
        # Legacy entry snapshots remain usable until an explicit seed is registered.
        points["snapshot"] = {
            "path": state.snapshot_path,
            "created_at": state.snapshot_created_at.isoformat(),
        }
    return points


def create_qa_snapshot(command: CreateQaSnapshotCommand) -> QaDevModeState:
    _assert_qa_allowed()
    _require_qa_admin_actor(command.actor)
    with _exclusive_qa_operation(), transaction.atomic():
        _lock_database_tables()
        state = _state_for_update()
        if not state.is_enabled:
            raise QaDevModeValidationError("Enable QA mode before creating a snapshot.")
        created_at = timezone.now()
        state.snapshot_path = str(_snapshot_dir() / _snapshot_filename(created_at=created_at))
        state.snapshot_created_at = created_at
        state.save(update_fields=["snapshot_path", "snapshot_created_at", "updated_at"])
        _record_qa_event(
            actor=command.actor,
            action="platform_core.qa_dev_mode.snapshot_created",
            state=state,
            metadata={"created_at": created_at.isoformat()},
        )
        path = _create_database_snapshot(created_at=created_at)
        transaction.on_commit(
            lambda: register_restore_point(
                kind="snapshot",
                path=path,
                created_at=created_at,
            )
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
    _require_qa_admin_actor(command.actor)
    with _exclusive_qa_operation():
        return _advance_qa_dev_mode_time(command)


def _advance_qa_dev_mode_time(command: AdvanceQaDevModeTimeCommand) -> QaDevModeState:
    _assert_qa_allowed()
    _require_qa_admin_actor(command.actor)
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


def revert_qa_dev_mode(command: RevertQaDevModeCommand) -> str:
    _assert_qa_allowed()
    _require_qa_admin_actor(command.actor)
    with _exclusive_qa_operation():
        return _revert_qa_dev_mode(command)


def _revert_qa_dev_mode(command: RevertQaDevModeCommand) -> str:
    _assert_qa_allowed()
    _require_qa_admin_actor(command.actor)
    if command.confirmation != QA_REVERT_CONFIRMATION:
        raise QaDevModeValidationError(f'Type "{QA_REVERT_CONFIRMATION}" to revert QA mode.')
    with transaction.atomic():
        state = _state_for_update()
        points = _restore_points(state)
        target = command.target
        if target == "auto":
            target = "snapshot" if "snapshot" in points else "seed"
        if target not in {"seed", "snapshot"}:
            raise QaDevModeValidationError("Choose snapshot or seed to restore.")
        point = points.get(target)
        if not point:
            raise QaDevModeValidationError(f"No {target} is saved; database was not changed.")
        snapshot_path = point["path"]
        metadata = {
            "snapshot_created_at": (
                state.snapshot_created_at.isoformat() if state.snapshot_created_at else ""
            ),
            "current_time": state.current_time.isoformat() if state.current_time else "",
            "target": target,
        }
        _record_qa_event(
            actor=command.actor,
            action="platform_core.qa_dev_mode.revert_requested",
            state=state,
            metadata=metadata,
        )
    _clear_cached_time()
    _restore_database_snapshot(snapshot_path)
    return target


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
