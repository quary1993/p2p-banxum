from __future__ import annotations

import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from backend.apps.investor_portal.services import (
    InvestorPortalAuthorizationError,
    get_investor_activity,
    get_investor_balances,
    get_investor_portfolio,
)
from backend.apps.platform_core.models import ArchivedInvestorActivity, AuditEvent, QaDatasetReset
from backend.apps.platform_core.services.activity_archive import (
    archive_activity_entries,
    merge_archived_activity,
)
from backend.apps.platform_core.services.qa_reset import (
    ResetQaDatasetCommand,
    qa_reset_plan,
    reset_confirmation,
    reset_qa_dataset,
)
from backend.apps.platform_core.services.qa_seed import INVESTOR_EMAIL, seed_qa_starting_point

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_reset(settings: Any, tmp_path: Path) -> ResetQaDatasetCommand:
    settings.ENVIRONMENT = "local"
    settings.IS_PRODUCTION = False
    settings.QA_DATA_RESET_ALLOWED = True
    settings.COMMUNICATIONS_EMAIL_PROVIDER = "mock"
    actor = get_user_model().objects.create_superuser(
        email="reset.operator@example.test", full_name="QA Operator", password="TestPassword123!"
    )
    seed_qa_starting_point(actor=actor)
    return ResetQaDatasetCommand(
        actor=actor,
        reset_id=uuid4(),
        expected_environment="local",
        confirmation=reset_confirmation(),
        backup_directory=tmp_path / "backups",
        maintenance_confirmed=True,
    )


def test_reset_preserves_identity_audit_history_and_balances_only_investors(
    setup_reset: ResetQaDatasetCommand,
) -> None:
    users = get_user_model()
    investor = users.objects.get(email=INVESTOR_EMAIL)
    restricted = users.objects.create_user(
        email="restricted@example.test",
        full_name="Restricted investor",
        password=None,
        account_type="natural_person_lender",
        status="restricted",
    )
    company = users.objects.create_user(
        email="company@example.test",
        full_name="Company investor",
        password=None,
        account_type="legal_entity_lender_representative",
        status="active",
    )
    users.objects.create_user(
        email="admin@example.test",
        full_name="Admin",
        password=None,
        account_type="admin",
        status="active",
        is_staff=True,
    )
    identity = list(users.objects.order_by("pk").values())
    verification = list(apps.get_model("kyc_compliance", "KycVerificationCase").objects.values())
    audits = {str(row.pk): row.metadata for row in AuditEvent.objects.all()}
    evidence_ids = set(
        apps.get_model("documents", "DocumentAcceptanceEvidence").objects.values_list(
            "pk", flat=True
        )
    )
    old_activity = get_investor_activity(actor=investor, limit=250)["entries"]
    old_loan_ids = set(apps.get_model("loans", "Loan").objects.values_list("pk", flat=True))
    assert qa_reset_plan()["new_direct_loans"] == 10
    result = reset_qa_dataset(setup_reset)
    assert result["investors_credited"] == 3
    assert list(users.objects.order_by("pk").values()) == identity
    assert (
        list(apps.get_model("kyc_compliance", "KycVerificationCase").objects.values())
        == verification
    )
    assert {str(row.pk): row.metadata for row in AuditEvent.objects.filter(pk__in=audits)} == audits
    assert (
        set(
            apps.get_model("documents", "DocumentAcceptanceEvidence").objects.values_list(
                "pk", flat=True
            )
        )
        == evidence_ids
    )
    loans = apps.get_model("loans", "Loan").objects.all()
    assert loans.count() == 20
    assert not loans.filter(pk__in=old_loan_ids).exists()
    assert not loans.exclude(status="published", committed_principal_minor=0).exists()
    profiles = apps.get_model("originator_claims", "OriginatorLoanProfile").objects.all()
    assert profiles.count() == 10
    assert not profiles.exclude(
        distribution_model="par_component_v2", opportunity_status="open"
    ).exists()
    assert get_investor_portfolio(actor=investor)["holdings"] == []
    assert apps.get_model("marketplace_primary", "PrimaryInvestmentOrder").objects.count() == 0
    lots = apps.get_model("ledger", "InvestorBalanceLot").objects.all()
    assert lots.count() == 6
    assert set(lots.values_list("investor_user_id", flat=True)) == {
        investor.pk,
        restricted.pk,
        company.pk,
    }
    assert not lots.exclude(
        available_amount_minor=50_000_000, original_amount_minor=50_000_000
    ).exists()
    assert apps.get_model("ledger", "InvestorPayoutInstruction").objects.count() == 0
    assert apps.get_model("ledger", "BankOperation").objects.count() == 0
    for summary in get_investor_balances(actor=investor)["summaries"]:
        assert summary["total_available_minor"] == 50_000_000
        assert summary["investable_minor"] == 50_000_000
    with pytest.raises(InvestorPortalAuthorizationError):
        get_investor_balances(actor=restricted)
    entries = {
        entry["id"]: entry for entry in get_investor_activity(actor=investor, limit=250)["entries"]
    }
    for old in old_activity:
        assert entries[old["id"]]["archived_at"]
        assert {
            key: value for key, value in entries[old["id"]].items() if key != "archived_at"
        } == old
    record = QaDatasetReset.objects.get(pk=setup_reset.reset_id)
    snapshot = Path(record.backup_path).read_bytes()
    assert hashlib.sha256(snapshot).hexdigest() == record.backup_sha256
    assert list(serializers.deserialize("json", snapshot.decode()))
    assert any(row["model"] == "accounts_auth.user" for row in json.loads(snapshot))
    assert Path(record.backup_path).stat().st_mode & 0o777 == 0o600
    assert AuditEvent.objects.filter(
        action="qa.dataset_reset", actor_id=str(setup_reset.actor.pk)
    ).exists()
    assert (
        not apps.get_model("platform_core", "OutboxMessage")
        .objects.exclude(status="processed")
        .exists()
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM platform_core_archivedinvestoractivity")


def test_same_run_is_idempotent_and_next_reset_keeps_prior_archive(
    setup_reset: ResetQaDatasetCommand,
) -> None:
    first = reset_qa_dataset(setup_reset)
    ids = set(apps.get_model("loans", "Loan").objects.values_list("pk", flat=True))
    second = reset_qa_dataset(setup_reset)
    assert second.pop("already_completed") is True
    assert second == first
    preview = io.StringIO()
    call_command("reset_qa_dataset", run_id=str(setup_reset.reset_id), stdout=preview)
    assert json.loads(preview.getvalue())["already_completed"] is True
    assert set(apps.get_model("loans", "Loan").objects.values_list("pk", flat=True)) == ids
    archived_ids = set(ArchivedInvestorActivity.objects.values_list("pk", flat=True))
    reset_qa_dataset(replace(setup_reset, reset_id=uuid4()))
    assert set(ArchivedInvestorActivity.objects.values_list("pk", flat=True)) > archived_ids
    assert QaDatasetReset.objects.count() == 2
    assert apps.get_model("ledger", "InvestorBalanceLot").objects.count() == 2


def test_failure_rolls_back_deletion_and_archive(
    setup_reset: ResetQaDatasetCommand,
    monkeypatch: Any,
) -> None:
    loan_model = apps.get_model("loans", "Loan")
    old_loans = set(loan_model.objects.values_list("pk", flat=True))
    old_lots = list(apps.get_model("ledger", "InvestorBalanceLot").objects.values())

    def fail(**kwargs: Any) -> None:
        raise RuntimeError("Injected seed failure")

    monkeypatch.setattr("backend.apps.platform_core.services.qa_reset._seed_catalogue", fail)
    with pytest.raises(RuntimeError, match="Injected seed failure"):
        reset_qa_dataset(setup_reset)
    assert set(loan_model.objects.values_list("pk", flat=True)) == old_loans
    assert list(apps.get_model("ledger", "InvestorBalanceLot").objects.values()) == old_lots
    assert ArchivedInvestorActivity.objects.count() == 0
    assert QaDatasetReset.objects.count() == 0
    assert list(setup_reset.backup_directory.glob("*.manifest.json"))
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM ledger_ledgerjournalentry")


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"confirmation": "RESET QA DATA"}, "exact environment"),
        ({"expected_environment": "production"}, "target environment"),
        ({"maintenance_confirmed": False}, "Stop the serving backend"),
        ({"actor": None}, "active superadmin"),
        ({"backup_directory": Path("relative")}, "absolute private"),
    ],
)
def test_reset_guardrails(
    setup_reset: ResetQaDatasetCommand, changes: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        reset_qa_dataset(replace(setup_reset, **changes))
    assert apps.get_model("loans", "Loan").objects.count() == 18
    assert not setup_reset.backup_directory.exists()


def test_production_requires_explicit_ack_and_process_opt_in(
    setup_reset: ResetQaDatasetCommand,
    settings: Any,
) -> None:
    settings.IS_PRODUCTION = True
    settings.ENVIRONMENT = "production"
    command = replace(
        setup_reset, expected_environment="production", confirmation=reset_confirmation()
    )
    with pytest.raises(ValueError, match="allow-production"):
        reset_qa_dataset(command)
    settings.QA_DATA_RESET_ALLOWED = False
    with pytest.raises(ValueError, match="offline maintenance"):
        reset_qa_dataset(replace(command, allow_production=True))


def test_archive_is_uncapped_scoped_and_never_overwrites_existing_evidence() -> None:
    investor_id, other_id, reset_id = str(uuid4()), str(uuid4()), uuid4()
    rows = [
        {"id": str(uuid4()), "occurred_at": timezone.now(), "amount_minor": index}
        for index in range(301)
    ]
    assert (
        archive_activity_entries(
            investor_user_id=investor_id, stream="portfolio", entries=rows, reset_id=reset_id
        )
        == 301
    )
    changed = [{**rows[0], "amount_minor": 999999}]
    assert (
        archive_activity_entries(
            investor_user_id=investor_id, stream="portfolio", entries=changed, reset_id=uuid4()
        )
        == 0
    )
    assert (
        ArchivedInvestorActivity.objects.get(source_id=rows[0]["id"]).payload["amount_minor"] == 0
    )
    assert (
        merge_archived_activity(
            investor_user_id=other_id, stream="portfolio", entries=[], limit=250
        )
        == []
    )
    assert (
        len(
            merge_archived_activity(
                investor_user_id=investor_id, stream="portfolio", entries=[], limit=250
            )
        )
        == 250
    )


def test_command_defaults_to_preview(setup_reset: ResetQaDatasetCommand, capsys: Any) -> None:
    call_command("reset_qa_dataset")
    assert "confirmation" in capsys.readouterr().out
    assert QaDatasetReset.objects.count() == 0
