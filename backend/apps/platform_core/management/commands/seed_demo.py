from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed local demo data. Domain-specific data will be added as modules are implemented."

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        self.stdout.write(self.style.SUCCESS("Seed command ready; no domain data yet."))
