from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from backend.apps.platform_core.models import Currency


@dataclass(frozen=True, slots=True)
class CurrencySeed:
    code: str
    name: str
    minor_units: int = 2
    is_enabled: bool = True


LAUNCH_CURRENCIES = (
    CurrencySeed(code="CHF", name="Swiss franc"),
    CurrencySeed(code="EUR", name="Euro"),
)


@transaction.atomic
def seed_launch_currencies() -> None:
    for currency in LAUNCH_CURRENCIES:
        Currency.objects.update_or_create(
            code=currency.code,
            defaults={
                "name": currency.name,
                "minor_units": currency.minor_units,
                "is_enabled": currency.is_enabled,
            },
        )
