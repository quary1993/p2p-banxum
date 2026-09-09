"""IP of Webby-Soft SRL. Guarded offline QA dataset maintenance command."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from backend.apps.platform_core.models import QaDatasetReset
from backend.apps.platform_core.services.qa_regression import RegressionAccounts
from backend.apps.platform_core.services.qa_reset import (
    ResetQaDatasetCommand,
    qa_reset_plan,
    reset_qa_dataset,
)


class Command(BaseCommand):
    help = (
        "Preview or explicitly rebuild the QA dataset, preserving accounts and activity histories."
    )

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--execute", action="store_true", help="Without this flag, only preview."
        )
        parser.add_argument("--actor-email", default="")
        parser.add_argument("--run-id", default="", help="UUID; reuse exactly for retry safety.")
        parser.add_argument("--expected-environment", default="")
        parser.add_argument("--confirm", default="")
        parser.add_argument("--backup-directory", default="")
        parser.add_argument("--maintenance-confirmed", action="store_true")
        parser.add_argument("--allow-production", action="store_true")
        parser.add_argument(
            "--regression-accounts",
            default="",
            help="Private JSON mapping: admin, user1, user2, user3 emails. Staging/local only.",
        )
        parser.add_argument(
            "--create-missing-investors",
            action="store_true",
            help="Create missing test investors; preserve existing identity checks.",
        )

    def handle(self, *args, **options):  # type: ignore[no-untyped-def]
        accounts = None
        try:
            if options["regression_accounts"]:
                data = json.loads(Path(options["regression_accounts"]).read_text())
                if (
                    not isinstance(data, dict)
                    or set(data) != {"admin", "user1", "user2", "user3"}
                    or not all(isinstance(value, str) for value in data.values())
                ):
                    raise ValueError(
                        "Account mapping must contain only admin/user1/user2/user3 email strings."
                    )
                accounts = RegressionAccounts(**data)
            plan = qa_reset_plan(
                regression_accounts=accounts,
                create_missing_investors=options["create_missing_investors"],
            )
        except (ValueError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        if not options["execute"]:
            result = plan
            if options["run_id"]:
                try:
                    previous = QaDatasetReset.objects.filter(pk=UUID(options["run_id"])).first()
                except ValueError as exc:
                    raise CommandError("Provide a valid reset UUID.") from exc
                result["already_completed"] = previous is not None
                if previous is not None:
                    expected = accounts.fingerprint() if accounts else None
                    if (
                        previous.summary.get("regression", {}).get("accounts_fingerprint")
                        != expected
                    ):
                        raise CommandError(
                            "This reset UUID already completed with another account profile."
                        )
                    result["completed_reset"] = previous.summary
            self.stdout.write(json.dumps(result, indent=2))
            return
        try:
            result = reset_qa_dataset(
                ResetQaDatasetCommand(
                    actor=get_user_model()
                    .objects.filter(email__iexact=options["actor_email"])
                    .first(),
                    reset_id=UUID(options["run_id"]),
                    expected_environment=options["expected_environment"],
                    confirmation=options["confirm"],
                    backup_directory=Path(options["backup_directory"]),
                    maintenance_confirmed=options["maintenance_confirmed"],
                    allow_production=options["allow_production"],
                    regression_accounts=accounts,
                    create_missing_investors=options["create_missing_investors"],
                )
            )
        except (ValueError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, indent=2))
