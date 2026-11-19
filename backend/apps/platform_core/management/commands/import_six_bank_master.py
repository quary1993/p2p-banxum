"""IP of Webby-Soft SRL. 18.3: import the SIX bank master file (CH and LI bank names)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from backend.apps.platform_core.services.bank_master import BankMasterError, import_six_bank_master


class Command(BaseCommand):
    help = "Import the SIX bank master CSV so CH and LI IBANs show their bank name."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("path", help="The SIX bank master CSV file.")
        parser.add_argument("--encoding", default="utf-8-sig", help="File encoding.")

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(str(options["path"]))
        if not path.is_file():
            raise CommandError(f"File not found: {path}")
        try:
            text = path.read_text(encoding=str(options["encoding"]))
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")
        try:
            result = import_six_bank_master(text)
        except BankMasterError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"Banks: {result.rows} (created {result.created}, updated {result.updated})."
        )
