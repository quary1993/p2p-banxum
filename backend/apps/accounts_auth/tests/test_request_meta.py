from __future__ import annotations

from typing import Any

from rest_framework.test import APIRequestFactory

from backend.apps.accounts_auth.api.request_meta import client_ip


def _request(forwarded_for: str | None, remote_addr: str = "172.18.0.5") -> Any:
    extra: dict[str, str] = {"REMOTE_ADDR": remote_addr}
    if forwarded_for is not None:
        extra["HTTP_X_FORWARDED_FOR"] = forwarded_for
    return APIRequestFactory().post("/", **extra)


def test_client_ip_ignores_forwarded_for_by_default(settings: Any) -> None:
    settings.TRUSTED_PROXY_COUNT = 0
    request = _request("198.51.100.10, 203.0.113.20", remote_addr="127.0.0.1")

    assert client_ip(request) == "127.0.0.1"


def test_client_ip_counts_trusted_proxy_hops_from_the_right(settings: Any) -> None:
    # Deployment chain: client -> Caddy (sets XFF=client) -> nginx (appends Caddy) -> Django.
    settings.TRUSTED_PROXY_COUNT = 2

    assert client_ip(_request("198.51.100.10, 172.18.0.1")) == "198.51.100.10"


def test_client_ip_never_uses_a_client_supplied_forwarded_for_entry(settings: Any) -> None:
    # Audit A-48: the leftmost value is whatever the client sent; it must be ignored.
    settings.TRUSTED_PROXY_COUNT = 2
    spoofed = _request("6.6.6.6, 1.2.3.4, 198.51.100.10, 172.18.0.1")

    assert client_ip(spoofed) == "198.51.100.10"


def test_client_ip_rotating_spoofed_headers_stay_in_one_bucket(settings: Any) -> None:
    settings.TRUSTED_PROXY_COUNT = 1
    seen = {
        client_ip(_request(f"10.0.0.{index}, 198.51.100.10")) for index in range(1, 20)
    }

    assert seen == {"198.51.100.10"}


def test_client_ip_falls_back_to_the_socket_when_a_proxy_hop_is_missing(settings: Any) -> None:
    settings.TRUSTED_PROXY_COUNT = 2

    assert client_ip(_request("198.51.100.10")) == "172.18.0.5"
    assert client_ip(_request(None)) == "172.18.0.5"


def test_client_ip_rejects_garbage_entries(settings: Any) -> None:
    settings.TRUSTED_PROXY_COUNT = 1

    assert client_ip(_request("not-an-ip")) == "172.18.0.5"
    assert client_ip(_request("203.0.113.7:51234")) == "203.0.113.7"
    assert client_ip(_request("[2001:db8::1]:443")) == "2001:db8::1"
