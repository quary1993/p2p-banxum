from __future__ import annotations

from importlib import import_module
from typing import Any, cast

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed local demo data. Domain-specific data will be added as modules are implemented."

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        call_command("seed_reference_data", verbosity=options.get("verbosity", 1))
        documents_services = import_module("backend.apps.documents.services")
        created_templates = cast(
            list[Any],
            documents_services.seed_placeholder_legal_templates(),
        )
        if created_templates:
            self.stdout.write(
                self.style.WARNING(
                    "Seeded temporary secondary-market terms placeholders. "
                    "Replace them with advisor-approved legal templates before production use."
                )
            )
        self.stdout.write(self.style.SUCCESS("Seeded local demo data."))
