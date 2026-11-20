"""IP of Webby-Soft SRL. Re-audit R8-1: the user summary gives the registered mobile, masked."""

from __future__ import annotations

from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from backend.apps.accounts_auth.api.serializers import mask_phone_number


def test_the_mask_keeps_only_the_country_code_and_the_last_two_digits() -> None:
    assert mask_phone_number("+41791234567") == "+41 ••• ••• •• 67"
    assert mask_phone_number("") == ""
    assert mask_phone_number("12") == ""


@pytest.mark.django_db
def test_auth_me_returns_the_masked_number_never_the_full_number() -> None:
    user: Any = get_user_model().objects.create_user(
        email="masked@example.test",
        full_name="Masked",
        account_type="natural_person_lender",
        status="pending_kyc",
        phone_number="+41791234567",
    )
    client = Client()
    client.force_login(cast(Any, user))
    payload = client.get("/api/v1/auth/me/").json()
    assert payload["user"]["phone_number_masked"] == "+41 ••• ••• •• 67"
    assert "791234567" not in str(payload)
