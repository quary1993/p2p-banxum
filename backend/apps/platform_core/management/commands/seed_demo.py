from __future__ import annotations

from importlib import import_module
from typing import Any, cast

from django.core.management.base import BaseCommand

from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.services.currencies import seed_launch_currencies
from backend.apps.platform_core.services.settings import seed_default_platform_settings


class Command(BaseCommand):
    help = "Seed local demo data. Domain-specific data will be added as modules are implemented."

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        seed_launch_currencies()
        seed_default_platform_settings(actor=ActorRef.system())
        documents_services = import_module("backend.apps.documents.services")
        created_templates = cast(
            list[Any],
            documents_services.seed_secondary_market_placeholder_terms(),
        )
        if created_templates:
            self.stdout.write(
                self.style.WARNING(
                    "Seeded temporary secondary-market terms placeholders. "
                    "Replace them with advisor-approved legal templates before production use."
                )
            )
        self.stdout.write(self.style.SUCCESS("Seeded platform core reference data."))
