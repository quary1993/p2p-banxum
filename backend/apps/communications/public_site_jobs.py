"""Entry points of the public-site scheduled jobs (run by platform_core's job runner)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.apps.communications.newsletter import (
    anonymise_old_newsletter_subscriptions,
    run_newsletter_new_projects_digest,
)
from backend.apps.communications.public_forms import delete_expired_public_enquiries


def newsletter_new_projects_job(*, as_of: datetime) -> dict[str, Any]:
    result = run_newsletter_new_projects_digest(as_of=as_of)
    return {
        "run_id": result.run_id,
        "run_date": result.run_date.isoformat(),
        "window_start": result.window_start.isoformat(),
        "window_end": result.window_end.isoformat(),
        "project_count": result.project_count,
        "queued_count": result.queued_count,
        "already_completed": result.already_completed,
        "resumed_run_dates": [value.isoformat() for value in result.resumed_run_dates],
    }


def public_site_retention_job(*, as_of: datetime) -> dict[str, Any]:
    """Enquiries are deleted after 24 months; newsletter rows anonymised after 30 days."""

    deleted = delete_expired_public_enquiries(as_of=as_of)
    anonymised = anonymise_old_newsletter_subscriptions(as_of=as_of)
    return {"as_of": as_of.isoformat(), "enquiries_deleted": deleted, **anonymised}
