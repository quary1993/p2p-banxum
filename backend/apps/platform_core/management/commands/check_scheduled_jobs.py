from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from backend.apps.platform_core.models.scheduled_jobs import (
    ScheduledJobRun,
    ScheduledJobRunStatus,
)
from backend.apps.platform_core.services.qa_dev_mode import qa_time_override_from_db
from backend.apps.platform_core.services.scheduled_jobs import (
    ALL_SCHEDULED_JOB_NAMES,
    DEFAULT_SCHEDULED_JOB_NAMES,
    EMAIL_OUTBOX_DISPATCH_JOB,
)


def _running_timeout_minutes() -> int:
    return max(1, int(getattr(settings, "SCHEDULED_JOBS_RUNNING_TIMEOUT_MINUTES", 120)))


def _run_label(job_run: ScheduledJobRun) -> str:
    return (
        f"{job_run.job_name} run_key={job_run.run_key} "
        f"run_id={job_run.id} started_at={job_run.started_at.isoformat()}"
    )


class Command(BaseCommand):
    help = "Fail if required BANXUM jobs are missing, overdue, failed, or stuck."

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
        job_names = tuple(dict.fromkeys(options.get("job") or DEFAULT_SCHEDULED_JOB_NAMES))
        unknown = set(job_names) - ALL_SCHEDULED_JOB_NAMES
        if unknown:
            raise CommandError(f"Unknown scheduled job(s): {', '.join(sorted(unknown))}.")
        now = timezone.now()
        qa_now = qa_time_override_from_db()
        cutoff = now - timedelta(minutes=timeout_minutes)

        runs = ScheduledJobRun.objects.all()
        if job_names:
            runs = runs.filter(job_name__in=job_names)

        failed = list(
            runs.filter(status=ScheduledJobRunStatus.FAILED).order_by("-started_at", "-id")[:limit]
        )
        stale_running = list(
            runs.filter(
                status=ScheduledJobRunStatus.RUNNING,
                started_at__lte=cutoff,
            ).order_by("started_at", "id")[:limit]
        )

        coverage_errors: list[str] = []
        for job_name in job_names:
            max_age_minutes = max(
                1,
                int(getattr(settings, "SCHEDULED_JOBS_EMAIL_MAX_AGE_MINUTES", 5))
                if job_name == EMAIL_OUTBOX_DISPATCH_JOB
                else int(getattr(settings, "SCHEDULED_JOBS_DAILY_MAX_AGE_MINUTES", 1800)),
            )
            success = (
                runs.filter(job_name=job_name, status=ScheduledJobRunStatus.SUCCEEDED)
                .filter(Q(summary__dry_run=False) | Q(summary__dry_run__isnull=True))
                .order_by("-finished_at", "-scheduled_for", "-id")
                .first()
            )
            if success is None:
                coverage_errors.append(f"{job_name}: no successful non-dry-run execution.")
                continue
            freshness_cutoff = now - timedelta(minutes=max_age_minutes)
            period_now = qa_now if qa_now is not None else now
            period_cutoff = period_now - timedelta(minutes=max_age_minutes)
            # A paused QA business date does not make a completed daily scan stale.
            # Email delivery and stuck-run timing must still follow wall time.
            check_runtime_age = qa_now is None or job_name == EMAIL_OUTBOX_DISPATCH_JOB
            check_period_age = qa_now is None or job_name != EMAIL_OUTBOX_DISPATCH_JOB
            if (
                success.finished_at is None
                or (check_runtime_age and success.finished_at < freshness_cutoff)
                or (check_period_age and success.scheduled_for < period_cutoff)
            ):
                coverage_errors.append(
                    f"{job_name}: successful execution is overdue "
                    f"(maximum age {max_age_minutes} minutes)."
                )
            elif (
                check_period_age and success.scheduled_for > period_now + timedelta(minutes=5)
            ) or success.finished_at > now + timedelta(minutes=5):
                coverage_errors.append(f"{job_name}: execution is dated in the future.")

        if not failed and not stale_running and not coverage_errors:
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
        if coverage_errors:
            lines.append("Missing or overdue job coverage:")
            lines.extend(f"  - {error}" for error in coverage_errors)

        message = "\n".join(lines)
        self.stdout.write(self.style.ERROR(message))
        raise CommandError("Scheduled job monitor found failed or stale runs, or missing coverage.")
