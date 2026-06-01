from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_endpoint_returns_platform_metadata(client: Client, settings) -> None:  # type: ignore[no-untyped-def]
    settings.PLATFORM_BRAND_NAME = "BANXUM"
    settings.LEGAL_OPERATOR_NAME = "Garanta Finanzgruppe AG"
    settings.TIME_ZONE = "Europe/Zurich"
    settings.ENVIRONMENT = "test"

    response = client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "platform": "BANXUM",
        "operator": "Garanta Finanzgruppe AG",
        "timezone": "Europe/Zurich",
        "environment": "test",
    }
