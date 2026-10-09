"""Loan notes (public / email / both) work for Loan Originator loans (audit A-29).

Old code: every note on an LO loan returned HTTP 500 because the note required a
BANXUM borrower, which LO loans do not have.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any, cast

import pytest
from django.db.models import Model
from django.test import Client
from freezegun import freeze_time

from backend.apps.originator_claims.tests.test_originator_claims import (  # noqa: F401
    _activate_par_subscription_for_test,
    _allocate_par_subscription,
    _create_par_subscription_loan,
    admin_user,
    investor,
)
from backend.apps.platform_core.models import OutboxMessage

T0 = date(2026, 6, 1)


@pytest.mark.django_db
def test_admin_publishes_public_and_email_notes_on_a_loan_originator_loan(
    client: Client,
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    with freeze_time(datetime.combine(T0, time(10), UTC)):
        result = _create_par_subscription_loan(admin_user=admin_user, today=T0, suffix="NOTES")
        _allocate_par_subscription(
            admin_user=admin_user,
            investor=investor,
            loan=result.loan,
            today=T0,
            amount_minor=160_000,
            suffix="NOTES",
        )
    with freeze_time(datetime.combine(T0 + timedelta(days=11), time(10), UTC)):
        _activate_par_subscription_for_test(
            admin_user=admin_user, result=result, today=T0, suffix="notes"
        )
        result.loan.refresh_from_db()
        assert result.loan.product_type == "originator_claim"
        assert result.loan.borrower_id is None

        client.force_login(cast(Any, admin_user))

        def post(key: str, visibility: str, email: bool) -> Any:
            return client.post(
                "/api/v1/servicing/admin/risk-notes/",
                data={
                    "loan_id": str(result.loan.pk),
                    "visibility": visibility,
                    "note_type": "public_update",
                    "title": "Loan Originator update",
                    "body": "The Loan Originator reports the borrower is on schedule.",
                    "email_affected_investors": email,
                    "idempotency_key": key,
                },
                content_type="application/json",
            )

        email_only = post("lo-note-email", "internal", True)
        assert email_only.status_code == 201, email_only.content
        assert email_only.json()["borrower_id"] is None
        public_only = post("lo-note-public", "public", False)
        assert public_only.status_code == 201, public_only.content
        both = post("lo-note-both", "public", True)
        assert both.status_code == 201, both.content

        emails = OutboxMessage.objects.filter(topic="email.loan_risk_note_published")
        assert emails.count() == 2
        assert {message.payload["user_id"] for message in emails} == {str(investor.pk)}

        client.logout()
        client.force_login(cast(Any, investor))
        notes = client.get("/api/v1/servicing/loan-risk-notes/", {"loan_id": str(result.loan.pk)})
        assert notes.status_code == 200
        # Frozen time: both public notes share one timestamp, so compare as a set.
        assert {note["id"] for note in notes.json()} == {
            both.json()["id"],
            public_only.json()["id"],
        }
