from __future__ import annotations

from django.core.management.base import BaseCommand

from backend.apps.communications.services import (
    DispatchEmailOutboxCommand,
    dispatch_due_email_outbox_messages,
)


class Command(BaseCommand):
    help = "Dispatch due email outbox messages through the configured email provider."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        result = dispatch_due_email_outbox_messages(
            DispatchEmailOutboxCommand(limit=options["limit"])
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Processed "
                f"{result.processed_count} email outbox messages "
                f"({result.sent_count} sent, {result.failed_count} failed, "
                f"{result.dead_letter_count} dead-lettered, {result.skipped_count} skipped)."
            )
        )
