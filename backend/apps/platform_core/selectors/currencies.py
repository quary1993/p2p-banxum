from __future__ import annotations

from django.db.models import QuerySet

from backend.apps.platform_core.models import Currency


def enabled_currencies() -> QuerySet[Currency]:
    return Currency.objects.filter(is_enabled=True).order_by("code")


def get_currency(code: str) -> Currency:
    return Currency.objects.get(code=code.upper())
