"""IP of Webby-Soft SRL. U33-DEC-09: the superadmin sets the platform's Late and Default days."""

from __future__ import annotations

from typing import Any

import pytest

from backend.apps.platform_core.models import AuditEvent, PlatformSettingVersion
from backend.apps.platform_core.selectors.settings import platform_loan_status_thresholds
from backend.apps.platform_core.tests.test_platform_features import _client, _user, superadmin

__all__ = ["superadmin"]

pytestmark = pytest.mark.django_db

URL = "/api/v1/admin/loan-status-days/"


def _put(user: Any, **data: Any) -> Any:
    return _client(user).put(URL, data=data, content_type="application/json")


def test_the_superadmin_reads_and_changes_both_days_with_a_reason(superadmin: Any) -> None:
    current = _client(superadmin).get(URL).json()
    assert (current["late_days"], current["default_days"]) == (15, 60)
    assert current["last_change"] is None

    changed = _put(superadmin, late_days=20, default_days=90, reason="Owner decision 2026-11")

    assert changed.status_code == 200, changed.content
    body = changed.json()
    assert (body["late_days"], body["default_days"]) == (20, 90)
    assert body["last_change"]["reason"] == "Owner decision 2026-11"
    assert body["last_change"]["changed_by_email"] == superadmin.email
    thresholds = platform_loan_status_thresholds()
    assert (thresholds.late_days, thresholds.default_days) == (20, 90)
    assert PlatformSettingVersion.objects.filter(key__startswith="servicing.").count() == 2
    assert AuditEvent.objects.filter(target_id__startswith="servicing.").count() >= 2


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"late_days": 60, "default_days": 60, "reason": "x"}, "Late must start before Default"),
        ({"late_days": 20, "default_days": 400, "reason": "x"}, "Late must start before Default"),
        ({"late_days": 20, "default_days": 90, "reason": " "}, "Enter a reason"),
        ({"late_days": 15, "default_days": 60, "reason": "same"}, "already in use"),
    ],
)
def test_wrong_days_are_refused(superadmin: Any, data: dict[str, Any], message: str) -> None:
    response = _put(superadmin, **data)

    assert response.status_code == 400, response.content
    assert message in response.json()["detail"]


def test_only_a_superadmin_reads_or_changes_the_days() -> None:
    admin = _user("days-admin@example.test", account_type="admin", staff=True, superuser=False)

    assert _client(admin).get(URL).status_code == 403
    assert _put(admin, late_days=20, default_days=90, reason="x").status_code == 403
