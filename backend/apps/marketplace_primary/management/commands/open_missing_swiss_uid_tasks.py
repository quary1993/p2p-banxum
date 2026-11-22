# IP of Webby-Soft SRL.
"""Audit S6-5: open one operations task per live Swiss financing without a valid borrower UID.

Such a financing (published before 18.9) takes no order, allocation, claim purchase, resale or
close until an admin records the UID from the borrower's commercial register entry.

    python backend/manage.py open_missing_swiss_uid_tasks --actor-email ops@example.com
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from backend.apps.marketplace_primary.creditor_regime import open_missing_uid_tasks
from backend.apps.platform_core.domain.access import is_admin_actor


class Command(BaseCommand):
    help = "Open an operations task for each Swiss financing whose borrower has no valid UID."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--actor-email", required=True)

    def handle(self, *args: Any, **options: Any) -> None:
        actor = get_user_model().objects.filter(email=options["actor_email"]).first()
        if actor is None or not is_admin_actor(actor):
            raise CommandError("The actor must be an active admin account.")
        loan_ids = open_missing_uid_tasks(actor=actor)
        self.stdout.write(f"Swiss financings without a valid UID: {len(loan_ids)}")
        for loan_id in loan_ids:
            self.stdout.write(f"  {loan_id}")
