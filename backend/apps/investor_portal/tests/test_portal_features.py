"""IP of Webby-Soft SRL. Investor app feature switches (owner decision 2026-10-16, row 6)."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from backend.apps.platform_core.models import PlatformSetting

FEATURES_URL = "/api/v1/investor/portal/features/"


@pytest.mark.django_db
def test_features_payload_reports_fx_off_by_default_and_on_when_switched_on() -> None:
    PlatformSetting.objects.filter(key="fx.enabled").delete()
    anonymous = Client()

    response = anonymous.get(FEATURES_URL)
    assert response.status_code == 200
    assert response.json() == {"fx_enabled": False}

    PlatformSetting.objects.create(key="fx.enabled", value=True, value_type="boolean")
    assert anonymous.get(FEATURES_URL).json() == {"fx_enabled": True}

    # Signed-in investors read the same payload; it holds no account data.
    investor: Any = get_user_model().objects.create_user(
        email="features-portal@example.test",
        full_name="Features Investor",
        account_type="natural_person_lender",
        status="active",
    )
    signed_in = Client()
    signed_in.force_login(investor)
    assert signed_in.get(FEATURES_URL).json() == {"fx_enabled": True}
