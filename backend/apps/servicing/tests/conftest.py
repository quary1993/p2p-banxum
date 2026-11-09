"""IP of Webby-Soft SRL. Shared fixtures of the servicing tests."""

from __future__ import annotations

import pytest

from backend.apps.platform_core.models import PlatformSetting


@pytest.fixture
def legacy_status_days(db: None) -> None:
    """Late from day 5 and Default from day 16, the days before U33-DEC-09.

    The servicing flow tests (payments, recoveries, write-offs, notices) were written with
    these days, and their dates and amounts depend on them. They set the platform values
    the way an operator can. test_loan_status_thresholds.py covers the U33-DEC-09 defaults
    (day 15 / day 60), the per-loan contract days and the termination.
    """
    for key, value in (
        ("servicing.late_threshold_days", 5),
        ("servicing.default_threshold_days", 16),
    ):
        PlatformSetting.objects.update_or_create(
            key=key, defaults={"value": value, "value_type": "integer"}
        )
