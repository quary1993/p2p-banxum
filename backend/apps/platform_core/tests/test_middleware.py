# IP of Webby-Soft SRL.
from __future__ import annotations

from django.http import HttpResponse
from django.test import RequestFactory

from backend.apps.platform_core.middleware import (
    BUILD_ORIGIN_HEADER,
    BUILD_ORIGIN_TOKEN,
    SOFTWARE_IP_HEADER,
    SOFTWARE_IP_NOTICE,
    SoftwareIpNoticeMiddleware,
)


def test_software_ip_notice_is_exposed_on_django_responses() -> None:
    request = RequestFactory().get("/api/v1/health/")
    middleware = SoftwareIpNoticeMiddleware(lambda _request: HttpResponse("ok"))

    response = middleware(request)

    assert response.headers[SOFTWARE_IP_HEADER] == SOFTWARE_IP_NOTICE
    assert response.headers[BUILD_ORIGIN_HEADER] == BUILD_ORIGIN_TOKEN
