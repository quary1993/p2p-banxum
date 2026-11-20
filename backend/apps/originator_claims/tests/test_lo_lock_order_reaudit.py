"""IP of Webby-Soft SRL. Re-audit R7-2: a Loan Originator quote and purchase lock the loan first.

PostgreSQL only (SQLite has no row locks): after the email code and PIN step, the first
SELECT ... FOR UPDATE of each path is on the loan row, before the quote and the profile, also
for a claim of a non-Swiss borrower.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

pytestmark = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="Row locks are visible on PostgreSQL only."
)


def _locked_tables(queries: list[dict[str, Any]]) -> list[str]:
    tables = []
    for query in queries:
        sql = str(query["sql"])
        if "FOR UPDATE" not in sql:
            continue
        table = sql.split(" FROM ", 1)[1].split()[0].strip('"')
        if not table.startswith("accounts_auth_"):  # the email code and PIN step comes first
            tables.append(table)
    return tables


@pytest.mark.django_db
def test_the_loan_originator_paths_lock_the_loan_first() -> None:
    races: Any = import_module("backend.apps.kyc_compliance.tests.test_compliance_races_s7")
    originator: Any = import_module("backend.apps.originator_claims.services")
    models: Any = import_module("backend.apps.originator_claims.models")
    investor, attempt, _error, _nothing = races._loan_originator_purchase()
    quote = models.OriginatorClaimQuote.objects.filter(investor_user_id=investor.pk).latest(
        "created_at"
    )
    loan_id = str(quote.loan_profile.loan_id)

    with CaptureQueriesContext(connection) as purchase_queries:
        attempt()
    purchase_locks = _locked_tables(purchase_queries.captured_queries)
    assert purchase_locks[0] == "loans_loan", purchase_locks
    assert purchase_locks.index("loans_loan") < purchase_locks.index(
        "originator_claims_originatorloanprofile"
    )

    with CaptureQueriesContext(connection) as quote_queries:
        try:
            originator.create_originator_claim_quote(
                originator.CreateOriginatorClaimQuoteCommand(
                    actor=investor, loan_id=loan_id, requested_cash_minor=100_000
                )
            )
        except originator.OriginatorClaimsValidationError:
            pass  # the lock order is what this test checks
    quote_locks = _locked_tables(quote_queries.captured_queries)
    assert quote_locks and quote_locks[0] == "loans_loan", quote_locks
