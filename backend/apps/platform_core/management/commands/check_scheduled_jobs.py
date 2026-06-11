from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from backend.apps.platform_core.models.scheduled_jobs import (
    ScheduledJobRun,
    ScheduledJobRunStatus,
)


def _running_timeout_minutes() -> int:
    return max(1, int(getattr(settings, "SCHEDULED_JOBS_RUNNING_TIMEOUT_MINUTES", 120)))


def _run_label(job_run: ScheduledJobRun) -> str:
    return (
        f"{job_run.job_name} run_key={job_run.run_key} "
        f"run_id={job_run.id} started_at={job_run.started_at.isoformat()}"
    )


class Command(BaseCommand):
    help = "Fail if BANXUM scheduled jobs have failed or stale running evidence."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--running-timeout-minutes",
            type=int,
            default=None,
            help=(
                "Override the stale RUNNING threshold. Defaults to "
                "SCHEDULED_JOBS_RUNNING_TIMEOUT_MINUTES."
            ),
        )
        parser.add_argument(
            "--job",
            action="append",
            default=None,
            help="Optional job name filter. Pass multiple times to check a subset.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Maximum failed/stale runs to print per category.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        timeout_minutes = options.get("running_timeout_minutes") or _running_timeout_minutes()
        timeout_minutes = max(1, int(timeout_minutes))
        limit = max(1, int(options.get("limit") or 20))
        job_names = tuple(str(job_name) for job_name in options.get("job") or ())
        cutoff = timezone.now() - timedelta(minutes=timeout_minutes)

        runs = ScheduledJobRun.objects.all()
        if job_names:
            runs = runs.filter(job_name__in=job_names)

        failed = list(
            runs.filter(status=ScheduledJobRunStatus.FAILED)
            .order_by("-started_at", "-id")[:limit]
        )
        stale_running = list(
            runs.filter(
                status=ScheduledJobRunStatus.RUNNING,
                started_at__lte=cutoff,
            ).order_by("started_at", "id")[:limit]
        )

        if not failed and not stale_running:
            scope = ", ".join(job_names) if job_names else "all jobs"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Scheduled job monitor OK for {scope}; "
                    f"stale RUNNING threshold={timeout_minutes} minutes."
                )
            )
            return

        lines: list[str] = []
        if failed:
            lines.append(f"FAILED runs ({len(failed)} shown):")
            lines.extend(f"  - {_run_label(job_run)} error={job_run.error}" for job_run in failed)
        if stale_running:
            lines.append(f"Stale RUNNING runs ({len(stale_running)} shown):")
            lines.extend(f"  - {_run_label(job_run)}" for job_run in stale_running)

        message = "\n".join(lines)
        self.stdout.write(self.style.ERROR(message))
        raise CommandError("Scheduled job monitor found failed or stale runs.")
