from __future__ import annotations

from datetime import datetime, time

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.timezone import make_aware

from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.services.scheduled_jobs import (
    ALL_SCHEDULED_JOB_NAMES,
    RunScheduledJobsCommand,
    ScheduledJobValidationError,
    run_scheduled_jobs,
)


def _parse_as_of(value: str) -> datetime:
    parsed_datetime = parse_datetime(value)
    if parsed_datetime is not None:
        if parsed_datetime.tzinfo is None:
            return make_aware(parsed_datetime, business_timezone())
        return parsed_datetime
    parsed_date = parse_date(value)
    if parsed_date is None:
        raise CommandError("--as-of must be an ISO datetime or YYYY-MM-DD date.")
    return datetime.combine(parsed_date, time(hour=12), tzinfo=business_timezone())


class Command(BaseCommand):
    help = "Run BANXUM scheduled jobs with durable run evidence and idempotency."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--job",
            action="append",
            choices=sorted(ALL_SCHEDULED_JOB_NAMES),
            help="Job to run. Pass multiple times to run a subset. Defaults to all jobs.",
        )
        parser.add_argument(
            "--as-of",
            default="",
            help="ISO datetime or YYYY-MM-DD date used for business-date jobs.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Bypass period idempotency by creating a one-off forced run key.",
        )
        parser.add_argument(
            "--email-limit",
            type=int,
            default=None,
            help="Maximum email outbox messages to dispatch in this run.",
        )
        parser.add_argument(
            "--balance-currency",
            default=None,
            help="Optional currency filter for the balance ageing scan.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Run balance_ageing_scan without side effects. "
                "Only valid with --job balance_ageing_scan."
            ),
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        as_of_value = str(options.get("as_of") or "").strip()
        as_of = _parse_as_of(as_of_value) if as_of_value else None
        try:
            result = run_scheduled_jobs(
                RunScheduledJobsCommand(
                    job_names=tuple(options.get("job") or ()),
                    as_of=as_of,
                    force=bool(options.get("force")),
                    email_limit=options.get("email_limit"),
                    balance_currency=options.get("balance_currency"),
                    dry_run=bool(options.get("dry_run")),
                )
            )
        except ScheduledJobValidationError as exc:
            raise CommandError(str(exc)) from exc

        failed: list[str] = []
        for job_result in result.results:
            style = self.style.SUCCESS
            if job_result.status == "failed":
                style = self.style.ERROR
                failed.append(job_result.job_name)
            elif job_result.status == "skipped":
                style = self.style.WARNING
            self.stdout.write(
                style(
                    f"{job_result.job_name}: {job_result.status} "
                    f"(run_key={job_result.run_key}, run_id={job_result.run_id})"
                )
            )
            if job_result.error:
                self.stdout.write(self.style.ERROR(f"  error: {job_result.error}"))

        if failed:
            raise CommandError(f"Scheduled job(s) failed: {', '.join(failed)}")
