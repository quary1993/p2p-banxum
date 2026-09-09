"""IP of Webby-Soft SRL. Explicit offline QA rebuild, separate from normal operations."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import asdict, dataclass, replace
from datetime import timedelta
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import UUID

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection, models, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from backend.apps.platform_core.domain.access import actor_ref_for_user, is_superadmin_actor
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import (
    ArchivedInvestorActivity,
    AuditEvent,
    OutboxMessage,
    QaDatasetReset,
    QaDevModeState,
)
from backend.apps.platform_core.services.activity_archive import archive_activity_entries
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.qa_dev_mode import _lock_database_tables

LENDER_TYPES = ("natural_person_lender", "legal_entity_lender_representative")
RESET_APPS = frozenset(
    {
        "entities",
        "loans",
        "marketplace_primary",
        "originator_claims",
        "holdings",
        "ledger",
        "servicing",
        "secondary_market",
        "fx",
        "reporting",
        "smart_invest",
        "admin_ops",
    }
)


@dataclass(frozen=True)
class ResetQaDatasetCommand:
    actor: Any
    reset_id: UUID
    expected_environment: str
    confirmation: str
    backup_directory: Path
    maintenance_confirmed: bool = False
    allow_production: bool = False


def reset_confirmation() -> str:
    return f"RESET QA DATA {settings.ENVIRONMENT} {settings.PUBLIC_APP_BASE_URL.rstrip('/')}"


def _reset_models() -> list[type[models.Model]]:
    return sorted(
        (model for model in apps.get_models() if model._meta.app_label in RESET_APPS),
        key=lambda model: model._meta.label_lower,
    )


def qa_reset_plan() -> dict[str, Any]:
    return {
        "environment": settings.ENVIRONMENT,
        "confirmation": reset_confirmation(),
        "accounts_preserved": get_user_model().objects.count(),
        "investors_credited": get_user_model()
        .objects.filter(account_type__in=LENDER_TYPES)
        .count(),
        "balance_per_investor_minor": {"CHF": 50_000_000, "EUR": 50_000_000},
        "new_direct_loans": 10,
        "new_originator_loans": 10,
        "rows_to_clear": {m._meta.label_lower: m._base_manager.count() for m in _reset_models()},
        "preserved": [
            "accounts and roles",
            "identity verification",
            "legal agreements",
            "user/admin audit and login history",
            "investor activity archive",
            "platform configuration",
            "files and communication history",
            "job evidence",
        ],
    }


def _validate(command: ResetQaDatasetCommand) -> None:
    if not settings.QA_DATA_RESET_ALLOWED:
        raise ValueError("Set QA_DATA_RESET_ALLOWED=true on the offline maintenance process only.")
    if not is_superadmin_actor(command.actor):
        raise ValueError("An active superadmin must run the reset.")
    if command.expected_environment != settings.ENVIRONMENT:
        raise ValueError("The target environment does not match the running application.")
    if settings.IS_PRODUCTION and not command.allow_production:
        raise ValueError("Production requires explicit --allow-production acknowledgement.")
    if command.confirmation != reset_confirmation():
        raise ValueError("The exact environment and site confirmation is required.")
    if not command.maintenance_confirmed:
        raise ValueError(
            "Stop the serving backend and all workers before acknowledging maintenance."
        )
    if not command.backup_directory.is_absolute():
        raise ValueError("An absolute private, durable backup directory is required.")
    if connection.vendor not in {"postgresql", "sqlite"}:
        raise ValueError("This database engine is not supported by the QA reset.")
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise ValueError("Apply all migrations before running the QA reset.")


def _require_offline_database() -> None:
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                "AND pid <> pg_backend_pid() AND backend_type = 'client backend'"
            )
            if cursor.fetchone()[0]:
                raise ValueError(
                    "Other database clients are connected; stop the backend/workers first."
                )


def _backup(command: ResetQaDatasetCommand) -> tuple[Path, str]:
    directory = command.backup_directory
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        raise ValueError("Backup directory must be private (0700) and not a symlink.")
    path = directory / f"qa-reset-{command.reset_id}.json"
    # Exclusive creation prevents overwriting a prior archive, even after a failed reset.
    with path.open("x", encoding="utf-8") as output:
        path.chmod(0o600)
        call_command("dumpdata", use_base_manager=True, stdout=output, verbosity=0)
    content = path.read_bytes()
    list(serializers.deserialize("json", content.decode("utf-8")))
    digest = hashlib.sha256(content).hexdigest()
    manifest = {
        "sha256": digest,
        "environment": settings.ENVIRONMENT,
        "reset_id": str(command.reset_id),
        "created_at": timezone.now().isoformat(),
    }
    manifest_path = path.with_suffix(".manifest.json")
    with manifest_path.open("x", encoding="utf-8") as output:
        manifest_path.chmod(0o600)
        json.dump(manifest, output)
    return path, digest


def _fingerprint(queryset: Any) -> str:
    content = serializers.serialize("json", queryset.order_by("pk"))
    return hashlib.sha256(content.encode()).hexdigest()


def _clear_operational_tables() -> None:
    models_to_clear = _reset_models()
    tables = {model._meta.db_table for model in models_to_clear}
    for model in apps.get_models(include_auto_created=True):
        if model._meta.db_table in tables:
            continue
        for field in model._meta.local_fields:
            related = field.related_model
            if isinstance(related, type) and related._meta.db_table in tables:
                raise ValueError(f"Protected model {model._meta.label} references reset data.")
    names = ", ".join(connection.ops.quote_name(name) for name in sorted(tables))
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            # Flush deferred FK checks before TRUNCATE, including nested maintenance calls.
            connection.check_constraints()
            # No CASCADE: an unexpected protected FK must abort, not widen the deletion.
            cursor.execute(f"TRUNCATE TABLE {names}")
            return
        cursor.execute("PRAGMA defer_foreign_keys = ON")
        cursor.execute("SELECT name, sql, tbl_name FROM sqlite_master WHERE type = 'trigger'")
        triggers = [(name, sql) for name, sql, table in cursor.fetchall() if table in tables]
        for name, _sql in triggers:
            cursor.execute(f"DROP TRIGGER {connection.ops.quote_name(name)}")
        for table in sorted(tables):
            cursor.execute(f"DELETE FROM {connection.ops.quote_name(table)}")
        for _name, sql in triggers:
            cursor.execute(sql)


def _seed_catalogue(*, actor: Any) -> None:
    entity_services = import_module("backend.apps.entities.services")
    loan_services = import_module("backend.apps.loans.services")
    catalogue = import_module("backend.apps.loans.management.commands.seed_marketplace_demo_loans")
    borrowers = [
        entity_services.create_borrower_entity(
            entity_services.CreateBorrowerEntityCommand(
                actor=actor,
                legal_name=name,
                year_founded=2016,
                country="Switzerland",
                registration_number=f"BANXUM-QA-RESET-BORROWER-{index}",
                kyb_status="approved",
                business_classification="Manufacturing" if index == 0 else "Wholesale",
                business_classification_public=True,
                note="Synthetic QA borrower; no real financial offer.",
            )
        )
        for index, name in enumerate(("QA Alpine Equipment AG", "QA Lake Trading SA"))
    ]
    specs = (
        *catalogue.DEMO_LOAN_SPECS,
        replace(
            catalogue.DEMO_LOAN_SPECS[0],
            key="export-working-capital",
            title="Demo - Export working capital",
            currency="EUR",
            principal_minor=12_000_000,
            interest_rate_bps=875,
            term_months=18,
            funding_deadline_days=35,
        ),
        replace(
            catalogue.DEMO_LOAN_SPECS[1],
            key="automation-equipment",
            title="Demo - Automation equipment",
            principal_minor=22_000_000,
            interest_rate_bps=950,
            term_months=30,
            funding_deadline_days=49,
        ),
    )
    today = business_date(now_utc())
    for index, spec in enumerate(specs):
        fields = asdict(spec)
        fields.pop("key")
        deadline = today + timedelta(days=fields.pop("funding_deadline_days"))
        loan = loan_services.create_loan(
            loan_services.CreateLoanCommand(
                **fields,
                actor=actor,
                borrower_id=str(borrowers[index % 2].pk),
                funding_deadline=deadline,
                loan_start_date=deadline,
                minimum_subscription_bps=5000,
                note="Synthetic QA reset catalogue.",
            )
        )
        loan_services.publish_loan(
            loan_services.PublishLoanCommand(actor=actor, loan_id=str(loan.pk))
        )
    call_command(
        "seed_originator_demo_loans",
        actor_email=actor.email,
        allow_production=settings.IS_PRODUCTION,
        stdout=io.StringIO(),
        verbosity=0,
    )


def reset_qa_dataset(command: ResetQaDatasetCommand) -> dict[str, Any]:
    _validate(command)
    try:
        with transaction.atomic():
            _require_offline_database()
            _lock_database_tables()
            previous = QaDatasetReset.objects.filter(pk=command.reset_id).first()
            if previous:
                return {**previous.summary, "already_completed": True}
            users = get_user_model().objects.all()
            identity_fingerprint = _fingerprint(users)
            audit_ids = list(AuditEvent.objects.values_list("pk", flat=True))
            audit_fingerprint = _fingerprint(AuditEvent.objects.filter(pk__in=audit_ids))
            plan = qa_reset_plan()
            backup, checksum = _backup(command)
            investors = list(users.filter(account_type__in=LENDER_TYPES).order_by("id"))
            portal = import_module("backend.apps.investor_portal.services")
            archived = 0
            for investor in users.order_by("id"):
                for stream, entries in portal.activity_for_qa_archive(
                    investor_user_id=str(investor.pk)
                ).items():
                    archived += archive_activity_entries(
                        investor_user_id=str(investor.pk),
                        stream=stream,
                        entries=entries,
                        reset_id=command.reset_id,
                    )
            _clear_operational_tables()
            QaDevModeState.objects.all().delete()
            cache.delete("platform_core:qa_dev_mode:current_time")
            _seed_catalogue(actor=command.actor)
            ledger_seed = import_module("backend.apps.ledger.qa_seed")
            for investor in investors:
                for currency in ("CHF", "EUR"):
                    ledger_seed.create_qa_opening_balance(
                        actor=command.actor,
                        investor_user_id=str(investor.pk),
                        currency_code=currency,
                        reset_id=command.reset_id,
                    )
            # Preserve communication evidence, but never send stale or synthetic requests.
            discarded = OutboxMessage.objects.exclude(status="processed").update(
                status="processed",
                processed_at=timezone.now(),
                next_attempt_at=None,
                last_error=f"Suppressed by QA reset {command.reset_id}; not delivered.",
            )
            loan_model = apps.get_model("loans", "Loan")
            if (
                loan_model.objects.count() != 20
                or loan_model.objects.exclude(
                    status="published", committed_principal_minor=0
                ).exists()
            ):
                raise ValueError("The seed did not produce exactly 20 unfunded published loans.")
            if apps.get_model("originator_claims", "OriginatorLoanProfile").objects.count() != 10:
                raise ValueError("The seed did not produce exactly ten LO v2 loans.")
            if (
                _fingerprint(users) != identity_fingerprint
                or _fingerprint(AuditEvent.objects.filter(pk__in=audit_ids)) != audit_fingerprint
            ):
                raise ValueError("Protected account/audit evidence changed; rolling back.")
            connection.check_constraints()
            summary = {key: value for key, value in plan.items() if key != "confirmation"}
            summary.update(
                {
                    "reset_id": str(command.reset_id),
                    "archived_activity_rows": archived,
                    "suppressed_outbox_messages": discarded,
                    "archive_total": ArchivedInvestorActivity.objects.count(),
                }
            )
            QaDatasetReset.objects.create(
                id=command.reset_id,
                actor_user_id=command.actor.pk,
                environment=settings.ENVIRONMENT,
                backup_path=str(backup),
                backup_sha256=checksum,
                summary=summary,
            )
            record_audit_event(
                AuditCommand(
                    actor=actor_ref_for_user(command.actor),
                    action="qa.dataset_reset",
                    target_type="QaDatasetReset",
                    target_id=str(command.reset_id),
                    metadata=summary,
                )
            )
            transaction.on_commit(cache.clear)
            return summary
    finally:
        cache.delete("platform_core:qa_dev_mode:current_time")
