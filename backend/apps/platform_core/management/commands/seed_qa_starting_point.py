from __future__ import annotations

import json
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError, CommandParser

from backend.apps.platform_core.services.qa_seed import seed_qa_starting_point


class Command(BaseCommand):
    help = "Build an idempotent, synthetic QA starting point; production is always refused."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--actor-email", required=True)

    def handle(self, *args: Any, **options: Any) -> None:
        actor = get_user_model().objects.filter(email__iexact=options["actor_email"]).first()
        try:
            result = seed_qa_starting_point(actor=actor)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, indent=2))
