from __future__ import annotations

import sys

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Generate a Django password hash for environment-managed admin credentials."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("password", nargs="?", help="Plaintext password to hash.")
        parser.add_argument(
            "--stdin",
            action="store_true",
            help="Read the plaintext password from stdin instead of an argument.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        password = str(options.get("password") or "")
        if options.get("stdin"):
            password = sys.stdin.readline().rstrip("\n")
        if not password:
            raise CommandError("Provide a password argument or pass --stdin.")

        self.stdout.write(make_password(password))
