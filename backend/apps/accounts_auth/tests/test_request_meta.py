from __future__ import annotations

from rest_framework.test import APIRequestFactory

from backend.apps.accounts_auth.api.request_meta import client_ip


def test_client_ip_ignores_forwarded_for_by_default(settings) -> None:  # type: ignore[no-untyped-def]
    settings.TRUST_X_FORWARDED_FOR = False
    request = APIRequestFactory().post(
        "/",
        HTTP_X_FORWARDED_FOR="198.51.100.10, 203.0.113.20",
        REMOTE_ADDR="127.0.0.1",
    )

    assert client_ip(request) == "127.0.0.1"


def test_client_ip_can_trust_forwarded_for_when_configured(settings) -> None:  # type: ignore[no-untyped-def]
    settings.TRUST_X_FORWARDED_FOR = True
    request = APIRequestFactory().post(
        "/",
        HTTP_X_FORWARDED_FOR="198.51.100.10, 203.0.113.20",
        REMOTE_ADDR="127.0.0.1",
    )

    assert client_ip(request) == "198.51.100.10"
