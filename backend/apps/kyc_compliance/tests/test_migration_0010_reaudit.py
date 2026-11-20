"""IP of Webby-Soft SRL. Re-audit R7-1: migration 0010 merges duplicate rows before its rules.

From 0009, two unresolved necessary reviews and two current re-verification dates of one
investor are created; after 0010 one of each stays current and no row is lost.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = ("kyc_compliance", "0009_recovery_identity_check")
AFTER = ("kyc_compliance", "0010_review_history_and_unique_rows")


def _migrate(target: tuple[str, str]) -> Any:
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([target])
    return executor.loader.project_state([target]).apps


# Transactional because SQLite cannot alter tables inside the per-test transaction.
@pytest.mark.django_db(transaction=True)
def test_migration_0010_merges_duplicate_reviews_and_dates() -> None:
    investor: Any = get_user_model().objects.create_user(
        email="dupes@example.test",
        full_name="Dupes",
        account_type="natural_person_lender",
        status="active",
    )
    other: Any = get_user_model().objects.create_user(
        email="single@example.test",
        full_name="Single",
        account_type="natural_person_lender",
        status="active",
    )
    try:
        old = _migrate(BEFORE)
        review = old.get_model("kyc_compliance", "ComplianceReview")
        dates = old.get_model("kyc_compliance", "InvestorReverification")
        first = review.objects.create(
            user_id=investor.pk, necessary=True, status="more_information", triggers=["pep"]
        )
        second = review.objects.create(
            user_id=investor.pk,
            necessary=True,
            status="open",
            triggers=["manual"],
            opened_reason="Adverse media.",
        )
        single = review.objects.create(
            user_id=other.pk, necessary=True, status="open", triggers=["volume"]
        )
        closed = review.objects.create(
            user_id=investor.pk, necessary=True, status="closed", triggers=["pep"]
        )
        due = date(2027, 3, 1)
        older_date = dates.objects.create(
            user_id=investor.pk, due_date=due, set_by_user_id=investor.pk
        )
        newer_date = dates.objects.create(
            user_id=investor.pk, due_date=due + timedelta(days=30), set_by_user_id=investor.pk
        )

        new = _migrate(AFTER)
        review = new.get_model("kyc_compliance", "ComplianceReview")
        dates = new.get_model("kyc_compliance", "InvestorReverification")
        kept = review.objects.get(id=first.id)
        merged = review.objects.get(id=second.id)
        assert review.objects.count() == 4
        assert kept.status == "open"
        assert kept.triggers == ["pep", "manual"]
        assert kept.trigger_events[0]["type"] == "merged_by_migration"
        assert kept.trigger_events[0]["review_id"] == str(second.id)
        assert merged.status == "closed"
        assert str(first.id) in merged.outcome_note
        assert review.objects.get(id=single.id).status == "open"
        assert review.objects.get(id=closed.id).status == "closed"
        assert dates.objects.count() == 2
        assert dates.objects.get(id=newer_date.id).replaced_at is None
        assert dates.objects.get(id=older_date.id).replaced_at is not None
    finally:
        _migrate(("kyc_compliance", "0010_review_history_and_unique_rows"))
