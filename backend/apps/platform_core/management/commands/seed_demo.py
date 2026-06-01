from __future__ import annotations

from django.core.management.base import BaseCommand

from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.services.currencies import seed_launch_currencies
from backend.apps.platform_core.services.settings import seed_default_platform_settings


class Command(BaseCommand):
    help = "Seed local demo data. Domain-specific data will be added as modules are implemented."

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        seed_launch_currencies()
        seed_default_platform_settings(actor=ActorRef.system())
        self.stdout.write(self.style.SUCCESS("Seeded platform core reference data."))
