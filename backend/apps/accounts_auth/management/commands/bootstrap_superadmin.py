from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from backend.apps.accounts_auth.services import (
    SuperadminBootstrapError,
    bootstrap_env_superadmin,
)


class Command(BaseCommand):
    help = "Create, update, or disable the environment-managed superadmin account."

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        try:
            result = bootstrap_env_superadmin()
        except SuperadminBootstrapError as exc:
            raise CommandError(str(exc)) from exc

        if result.user is None:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Environment-managed superadmin disabled; "
                    f"{len(result.disabled_user_ids)} account(s) locked."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Environment-managed superadmin {result.action}: {result.user.email}"
            )
        )
