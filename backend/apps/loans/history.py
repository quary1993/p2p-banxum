"""IP of Webby-Soft SRL. One loan's history for the admin console.

The loan's own events (status changes, publication, funding, the U33 late/default days, contract
termination, Coming soon) and the audit entries recorded against the loan that have no loan event
(securities, credit checks and monitoring, recovery stages, originator claim events), newest first,
with the email of the person who acted.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.apps import apps

from backend.apps.loans.models import Loan
from backend.apps.platform_core.models import AuditEvent

# Audit actions that repeat a loan event: the loan event is shown instead.
MIRRORED_AUDIT_ACTIONS = frozenset(
    {
        "loan.created",
        "loan.updated",
        "loan.published",
        "loan.funding_closed",
        "loan.funding_close_failed",
        "loan.funding_cancelled",
        "loan.servicing_status_changed",
        "loan.coming_soon_announced",
        "loan.coming_soon_withdrawn",
        "servicing.loan_status_thresholds_changed",
        "servicing.loan_contract_terminated",
    }
)
HISTORY_LIMIT = 500


def _actor_labels(actor_ids: set[str]) -> dict[str, str]:
    """User id -> email (loaded by name: loans does not import accounts_auth)."""
    ids = {actor_id for actor_id in actor_ids if actor_id}
    if not ids:
        return {}
    valid: list[uuid.UUID] = []
    for actor_id in ids:
        try:
            valid.append(uuid.UUID(actor_id))
        except ValueError:
            continue  # A system actor id is not a user id.
    user_model = apps.get_model("accounts_auth", "User")
    return {
        str(user_id): str(email)
        for user_id, email in user_model.objects.filter(pk__in=valid).values_list("pk", "email")
    }


def loan_history(loan: Loan) -> list[dict[str, Any]]:
    events = list(loan.events.all().order_by("-occurred_at", "-id")[:HISTORY_LIMIT])
    audits = list(
        AuditEvent.objects.filter(target_type="Loan", target_id=str(loan.pk))
        .exclude(action__in=MIRRORED_AUDIT_ACTIONS)
        .order_by("-occurred_at", "-id")[:HISTORY_LIMIT]
    )
    labels = _actor_labels(
        {str(event.actor_user_id) for event in events} | {str(audit.actor_id) for audit in audits}
    )
    entries: list[dict[str, Any]] = [
        {
            "id": str(event.id),
            "kind": "event",
            "code": event.event_type,
            "occurred_at": event.occurred_at,
            "actor": labels.get(str(event.actor_user_id), event.actor_account_type or "system"),
            "previous_status": event.previous_status,
            "new_status": event.new_status,
            "note": event.note,
            "details": event.metadata if isinstance(event.metadata, dict) else {},
        }
        for event in events
    ]
    entries.extend(
        {
            "id": str(audit.id),
            "kind": "change",
            "code": audit.action,
            "occurred_at": audit.occurred_at,
            "actor": labels.get(str(audit.actor_id), audit.actor_type or "system"),
            "previous_status": "",
            "new_status": "",
            "note": "",
            "details": audit.metadata if isinstance(audit.metadata, dict) else {},
        }
        for audit in audits
    )
    entries.sort(key=lambda entry: entry["occurred_at"], reverse=True)
    return entries[:HISTORY_LIMIT]
