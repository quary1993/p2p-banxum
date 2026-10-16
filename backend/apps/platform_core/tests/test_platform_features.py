"""IP of Webby-Soft SRL. Superadmin platform switches (owner decision 2026-10-16, row 6)."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from backend.apps.platform_core.models import (
    AuditEvent,
    PlatformSetting,
    PlatformSettingVersion,
)
from backend.apps.platform_core.selectors.settings import (
    get_platform_setting_value,
    platform_switch_enabled,
)
from backend.apps.platform_core.services.settings import DEFAULT_PLATFORM_SETTINGS

FEATURES_URL = "/api/v1/admin/platform-features/"


def _user(email: str, *, account_type: str, staff: bool, superuser: bool) -> Any:
    return get_user_model().objects.create_user(
        email=email,
        password=None,
        full_name="Platform Operator",
        account_type=account_type,
        status="active",
        is_staff=staff,
        is_superuser=superuser,
    )


@pytest.fixture
def superadmin() -> Any:
    return _user("features-sa@example.test", account_type="superadmin", staff=True, superuser=True)


def _client(user: Any | None) -> Client:
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def test_defaults_for_the_2026_10_16_decisions() -> None:
    defaults = {definition.key: definition for definition in DEFAULT_PLATFORM_SETTINGS}
    assert defaults["secondary_market.maker_fee_bps"].value == 200
    assert defaults["secondary_market.taker_fee_bps"].value == 0
    assert defaults["fx.enabled"].value is False
    assert defaults["fx.enabled"].value_type == "boolean"


@pytest.mark.django_db
def test_switch_is_off_unless_explicitly_true() -> None:
    # A missing row is off (fail closed).
    assert platform_switch_enabled("fx.enabled") is False
    for value in (1, "true", {"enabled": True}, False):
        PlatformSetting.objects.update_or_create(key="fx.enabled", defaults={"value": value})
        assert platform_switch_enabled("fx.enabled") is False
    PlatformSetting.objects.filter(key="fx.enabled").update(value=True)
    assert platform_switch_enabled("fx.enabled") is True


@pytest.mark.django_db
def test_only_a_superadmin_can_read_or_change_platform_features() -> None:
    investor = _user(
        "features-investor@example.test",
        account_type="natural_person_lender",
        staff=False,
        superuser=False,
    )
    admin = _user("features-admin@example.test", account_type="admin", staff=True, superuser=False)
    body = {"key": "fx.enabled", "enabled": True, "reason": "Try it"}

    assert _client(None).get(FEATURES_URL).status_code in {401, 403}
    for user in (investor, admin):
        client = _client(user)
        assert client.get(FEATURES_URL).status_code == 403
        response = client.post(FEATURES_URL, body, content_type="application/json")
        assert response.status_code == 403
        assert response.json() == {"detail": "Only a superadmin can change platform features."}
    assert get_platform_setting_value("fx.enabled") is None
    assert not AuditEvent.objects.filter(target_id="fx.enabled").exists()


@pytest.mark.django_db
def test_superadmin_switches_fx_on_and_off_with_reason_and_audit(superadmin: Any) -> None:
    client = _client(superadmin)

    initial = client.get(FEATURES_URL)
    assert initial.status_code == 200
    assert initial.json() == {
        "features": [
            {
                "key": "fx.enabled",
                "title": "Currency exchange (FX)",
                "description": initial.json()["features"][0]["description"],
                "enabled": False,
                "last_change": None,
            }
        ]
    }

    blank = client.post(
        FEATURES_URL,
        {"key": "fx.enabled", "enabled": True, "reason": "  "},
        content_type="application/json",
    )
    assert blank.status_code == 400
    assert blank.json() == {"detail": "Enter a reason for this change."}
    unknown = client.post(
        FEATURES_URL,
        {"key": "fx.platform_fee_bps", "enabled": True, "reason": "No"},
        content_type="application/json",
    )
    assert unknown.status_code == 400
    assert unknown.json() == {"detail": "This platform feature does not exist."}
    assert get_platform_setting_value("fx.enabled") is None

    switched_on = client.post(
        FEATURES_URL,
        {"key": "fx.enabled", "enabled": True, "reason": "Pilot with two investors"},
        content_type="application/json",
    )
    assert switched_on.status_code == 200
    feature = switched_on.json()["features"][0]
    assert feature["enabled"] is True
    assert feature["last_change"]["version"] == 1
    assert feature["last_change"]["enabled"] is True
    assert feature["last_change"]["changed_by_type"] == "superadmin"
    assert feature["last_change"]["changed_by_id"] == str(superadmin.pk)
    assert feature["last_change"]["changed_by_email"] == "features-sa@example.test"
    assert feature["last_change"]["reason"] == "Pilot with two investors"
    assert feature["last_change"]["changed_at"]
    assert get_platform_setting_value("fx.enabled") is True

    again = client.post(
        FEATURES_URL,
        {"key": "fx.enabled", "enabled": True, "reason": "Twice"},
        content_type="application/json",
    )
    assert again.status_code == 400
    assert again.json() == {"detail": "Currency exchange (FX) is already on. Nothing was changed."}

    switched_off = client.post(
        FEATURES_URL,
        {"key": "fx.enabled", "enabled": False, "reason": "Pilot finished"},
        content_type="application/json",
    )
    assert switched_off.status_code == 200
    assert switched_off.json()["features"][0]["enabled"] is False
    assert switched_off.json()["features"][0]["last_change"]["version"] == 2
    assert get_platform_setting_value("fx.enabled") is False

    versions = list(PlatformSettingVersion.objects.filter(key="fx.enabled").order_by("version"))
    assert [(row.value, row.reason, row.changed_by_type) for row in versions] == [
        (True, "Pilot with two investors", "superadmin"),
        (False, "Pilot finished", "superadmin"),
    ]
    audits = list(AuditEvent.objects.filter(target_id="fx.enabled").order_by("occurred_at"))
    assert [audit.action for audit in audits] == [
        "platform_setting.created",
        "platform_setting.updated",
    ]
    assert audits[-1].actor_type == "superadmin"
    assert audits[-1].actor_id == str(superadmin.pk)
    assert audits[-1].metadata["previous_enabled"] is True
    assert audits[-1].metadata["enabled"] is False
    assert audits[-1].metadata["reason"] == "Pilot finished"
