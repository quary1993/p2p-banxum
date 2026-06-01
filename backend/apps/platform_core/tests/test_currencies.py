from __future__ import annotations

import pytest

from backend.apps.platform_core.selectors.currencies import enabled_currencies
from backend.apps.platform_core.services.currencies import seed_launch_currencies


@pytest.mark.django_db
def test_seed_launch_currencies_creates_chf_and_eur() -> None:
    seed_launch_currencies()

    currencies = list(enabled_currencies().values_list("code", "minor_units"))

    assert currencies == [("CHF", 2), ("EUR", 2)]
