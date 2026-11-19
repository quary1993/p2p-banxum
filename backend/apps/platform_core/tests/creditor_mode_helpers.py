"""IP of Webby-Soft SRL. 18.9 test helpers: put Swiss test borrowers in a creditor mode.

The legal limits are 10 creditors per financing and 20 per borrower (10/20 mode). Tests may lower
the per-financing limit to keep the data small; ``restore_limits`` (autouse fixture in the test
modules) puts the legal values back.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from django.apps import apps
from django.utils import timezone

from backend.apps.platform_core.domain import countries, creditor_regime
from backend.apps.platform_core.tests.swiss_uid import next_test_uid

LEGAL_FINANCING_LIMIT = creditor_regime.FINANCING_CREDITOR_LIMIT
LEGAL_BORROWER_LIMIT = creditor_regime.BORROWER_CREDITOR_LIMIT


@pytest.fixture(autouse=True)
def restore_limits() -> Iterator[None]:
    yield
    creditor_regime.FINANCING_CREDITOR_LIMIT = LEGAL_FINANCING_LIMIT
    creditor_regime.BORROWER_CREDITOR_LIMIT = LEGAL_BORROWER_LIMIT


def set_swiss_creditor_mode(
    *,
    financing_limit: int | None = None,
    mode: str = creditor_regime.MODE_TEN_TWENTY,
) -> None:
    """Every Swiss test borrower (Direct entities and claim profiles) gets a UID and ``mode``;
    ``financing_limit`` lowers the 10/20 per-financing limit for the test (0 = sandbox mode)."""
    if financing_limit == 0:
        mode = creditor_regime.MODE_SANDBOX
    elif financing_limit is not None:
        creditor_regime.FINANCING_CREDITOR_LIMIT = financing_limit
    regime_model: Any = apps.get_model("entities", "SwissCreditorRegime")
    uids: set[str] = set()
    for borrower in apps.get_model("entities", "BorrowerEntity").objects.all():
        if not countries.is_switzerland(borrower.country):
            continue
        if not borrower.uid:
            borrower.uid = next_test_uid()
            borrower.save(update_fields=["uid", "updated_at"])
        uids.add(str(borrower.uid))
    for profile in apps.get_model("originator_claims", "OriginatorLoanProfile").objects.all():
        if not countries.is_switzerland(profile.borrower_country):
            continue
        if not profile.borrower_uid:
            profile.borrower_uid = next_test_uid()
            profile.save(update_fields=["borrower_uid", "updated_at"])
        uids.add(str(profile.borrower_uid))
    for uid in uids:
        regime_model.objects.update_or_create(
            uid=uid, defaults={"mode": mode, "confirmed_at": timezone.now()}
        )
