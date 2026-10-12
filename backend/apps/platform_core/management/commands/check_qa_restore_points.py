"""IP of Webby-Soft SRL. Validate durable QA restore points without restoring data."""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from backend.apps.platform_core.services.qa_dev_mode import _schema_signature
from backend.apps.platform_core.services.qa_restore_points import (
    read_restore_points,
    validate_snapshot_file,
)


class Command(BaseCommand):
    help = "Validate saved QA restore points, checksums and migration compatibility."

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument("--require-seed", action="store_true")

    def handle(self, *args, **options):  # type: ignore[no-untyped-def]
        try:
            points = read_restore_points()
            if options["require_seed"] and "seed" not in points:
                raise ValueError("The QA seed restore point is not registered.")
            migrations = _schema_signature()
            validated = {}
            for kind, point in points.items():
                content = validate_snapshot_file(point["path"], migrations=migrations)
                validated[kind] = {
                    "created_at": point["created_at"],
                    "size_bytes": len(content),
                }
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps({"restore_points": validated}, sort_keys=True))
