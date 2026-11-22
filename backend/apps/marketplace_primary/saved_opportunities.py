"""IP of Webby-Soft SRL. U33-DEC-18: Save for later and the closing reminders.

An investor saves an open opportunity, with or without an amount they chose. Saving reserves
no money or place, accepts no agreement and does not keep the opportunity open. On return the
platform checks the opportunity again (still open, the minimum, the amount still available);
an amount that no longer fits is explained, never changed.

Reminders: 7, 3 and 1 day before the funding deadline, as an email that is also listed in the
investor's notifications. Only milestones after the day of saving; one reminder per milestone,
investor, loan and deadline; none after the item is removed or the opportunity is no longer
open; a new deadline schedules them again. When a run finds several milestones due (a missed
run), it sends the latest one only. Marketing choices and the Smart Invest pause do not apply.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, cast

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Model

from backend.apps.marketplace_primary import services as primary
from backend.apps.marketplace_primary.models import (
    SavedOpportunity,
    SavedOpportunityReminder,
    SavedOpportunityReminderStatus,
)
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.money import format_amount_minor
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models.events import OutboxStatus
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message

REMINDER_DAYS_BEFORE = (7, 3, 1)
SAVED_REMINDER_TOPIC = "email.saved_opportunity_closing"


def _open_payloads(*, viewer_user_id: str | None, today: date) -> dict[str, dict[str, Any]]:
    """Open opportunities by loan id: published, deadline not passed, money still needed."""
    payloads = primary.list_open_marketplace_loans(limit=10_000, viewer_user_id=viewer_user_id)
    open_by_id: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        deadline = payload.get("funding_deadline")
        if isinstance(deadline, str):
            deadline = date.fromisoformat(deadline)
        if deadline is not None and deadline < today:
            continue
        if primary.marketplace_payload_has_capacity(payload):
            open_by_id[str(payload["loan_id"])] = payload
    return open_by_id


def _available_minor(payload: dict[str, Any]) -> int:
    available = payload.get("fillable_amount_minor")
    if available is None:
        available = payload.get("remaining_capacity_minor", 0)
    return int(available or 0)


def _amount_check(amount_minor: int | None, payload: dict[str, Any] | None) -> str:
    """ "closed", "none" (no amount), "below_minimum", "above_available" or "ok"."""
    if payload is None:
        return "closed"
    if amount_minor is None:
        return "none"
    if amount_minor < int(payload.get("minimum_investment_minor") or 0):
        return "below_minimum"
    if amount_minor > _available_minor(payload):
        return "above_available"
    return "ok"


def _saved_payload(saved: SavedOpportunity, payload: dict[str, Any] | None) -> dict[str, Any]:
    loan = cast(Any, saved.loan)
    return {
        "loan_id": str(loan.id),
        "title": str(payload["title"] if payload else loan.title),
        "product_type": str(loan.product_type),
        "currency": str(payload["currency"] if payload else loan.currency_id),
        "borrower_display_name": (payload or {}).get("borrower_display_name")
        or getattr(getattr(loan, "borrower", None), "legal_name", None),
        "collateral_type": str(loan.collateral_type),
        "amount_minor": saved.amount_minor,
        "saved_at": saved.created_at,
        "updated_at": saved.updated_at,
        "is_open": payload is not None,
        "funding_deadline": (payload or {}).get("funding_deadline", loan.funding_deadline),
        "minimum_investment_minor": (
            int(payload.get("minimum_investment_minor") or 0) if payload else None
        ),
        "available_minor": _available_minor(payload) if payload else None,
        "amount_check": _amount_check(saved.amount_minor, payload),
    }


def list_saved_opportunities(*, actor: Model) -> list[dict[str, Any]]:
    """The investor's saved opportunities, each checked again now.

    C05 (2026-11-13): "Closing soonest" orders the saved group, as on the opportunities page:
    open items by funding deadline (then the newest saved first); items no longer open last.
    """
    primary._require_investor_financial_access(actor)
    saved = list(
        SavedOpportunity.objects.filter(investor_user_id=actor.pk).select_related(
            "loan", "loan__borrower"
        )
    )
    if not saved:
        return []
    open_by_id = _open_payloads(viewer_user_id=str(actor.pk), today=business_date(now_utc()))
    payloads = [_saved_payload(item, open_by_id.get(str(item.loan_id))) for item in saved]
    payloads.sort(key=lambda item: item["saved_at"], reverse=True)
    payloads.sort(
        key=lambda item: (
            not item["is_open"],
            str(item.get("funding_deadline") or "9999-12-31") if item["is_open"] else "",
        )
    )
    return payloads


def save_opportunity(*, actor: Model, loan_id: str, amount_minor: int | None) -> dict[str, Any]:
    """Save (or change) an open opportunity, with an amount the investor chose or none."""
    primary._require_investor_financial_access(actor)
    open_by_id = _open_payloads(viewer_user_id=str(actor.pk), today=business_date(now_utc()))
    payload = open_by_id.get(str(loan_id))
    if payload is None:
        raise primary.MarketplacePrimaryValidationError(
            "This opportunity is not open for investment. It cannot be saved."
        )
    if amount_minor is not None:
        currency = str(payload["currency"])
        minimum = int(payload.get("minimum_investment_minor") or 0)
        available = _available_minor(payload)
        if amount_minor <= 0:
            raise primary.MarketplacePrimaryValidationError("Enter an investment amount.")
        if amount_minor < minimum:
            raise primary.MarketplacePrimaryValidationError(
                f"The minimum investment is {format_amount_minor(minimum, currency)}."
            )
        if amount_minor > available:
            raise primary.MarketplacePrimaryValidationError(
                f"Only {format_amount_minor(available, currency)} is available to invest."
            )
    with transaction.atomic():
        saved, _created = SavedOpportunity.objects.select_for_update().get_or_create(
            loan_id=loan_id, investor_user_id=actor.pk, defaults={"amount_minor": amount_minor}
        )
        if saved.amount_minor != amount_minor:
            saved.amount_minor = amount_minor
            saved.save(update_fields=["amount_minor", "updated_at"])
    saved = SavedOpportunity.objects.select_related("loan", "loan__borrower").get(pk=saved.pk)
    return _saved_payload(saved, payload)


def remove_saved_opportunity(*, actor: Model, loan_id: str) -> None:
    """Remove a saved opportunity; its reminders stop. Removing twice is not an error."""
    primary._require_investor_financial_access(actor)
    SavedOpportunity.objects.filter(loan_id=loan_id, investor_user_id=actor.pk).delete()


def _closing_phrase(days_left: int) -> str:
    if days_left <= 0:
        return "today"
    if days_left == 1:
        return "tomorrow"
    return f"in {days_left} days"


def _reminder_payload(
    *, user: Any, saved: SavedOpportunity, payload: dict[str, Any], deadline: date, days_left: int
) -> dict[str, Any]:
    title = str(payload["title"])
    currency = str(payload["currency"])
    phrase = _closing_phrase(days_left)
    loan_id = str(saved.loan_id)
    rows = [["Funding closes", f"{deadline.day} {deadline.strftime('%b %Y')}"]]
    if saved.amount_minor is not None:
        rows.append(["Your saved amount", f"{format_amount_minor(saved.amount_minor, currency)}"])
    return {
        "user_id": str(user.pk),
        "email": str(user.email),
        "subject": f"Funding closes {phrase}: {title}",
        "notice_label": "Saved opportunity",
        "headline": f"Funding closes {phrase}",
        "status_label": "Saved for later",
        "status_tone": "info",
        "body_text": (
            f"You saved {title} for later. Funding closes {phrase}. Nothing is reserved for "
            "you: review the opportunity and confirm your investment if you still want to invest."
        ),
        "data_rows": rows,
        "buttons": [
            {
                "label": "Continue review",
                "url": f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/marketplace/{loan_id}",
            }
        ],
        "loan_id": loan_id,
        # Q14: the email carries a one-click "Stop these alerts" link.
        "stop_alerts": {"kind": "saved_reminder", "loan_id": loan_id},
        "template_key": "marketplace.saved_opportunity_closing.v1",
        "fine_print": (
            "You get this because you saved this opportunity. Remove it to stop the reminders."
        ),
    }


# Q14: the in-app reminder of an investor who stopped the reminder emails (never emailed).
SAVED_REMINDER_IN_APP_TOPIC = "notice.saved_opportunity_closing"


def stop_saved_reminder_emails(*, investor_user_id: str, loan_id: str) -> bool:
    """Q14: "Stop these alerts" in a reminder email stops the reminder emails for that project.

    The saved item and the in-app reminders stay. Returns True when it changed.
    """
    changed = SavedOpportunity.objects.filter(
        loan_id=loan_id, investor_user_id=investor_user_id, email_reminders_stopped_at__isnull=True
    ).update(email_reminders_stopped_at=now_utc())
    if changed:
        record_audit_event(
            AuditCommand(
                actor=ActorRef("investor", str(investor_user_id)),
                action="marketplace.saved_reminder_emails_stopped",
                target_type="Loan",
                target_id=str(loan_id),
                metadata={"decision": "Q14", "source": "email_stop_link"},
            )
        )
    return bool(changed)


def send_saved_opportunity_reminders(*, as_of: datetime) -> dict[str, Any]:
    """Daily: the 7, 3 and 1 day reminders of saved opportunities that are still open."""
    today = business_date(as_of)
    open_by_id = _open_payloads(viewer_user_id=None, today=today)
    sent = 0
    skipped = 0
    user_model = primary._model("accounts_auth", "User")
    saved_items = SavedOpportunity.objects.filter(loan_id__in=list(open_by_id)).select_related(
        "loan"
    )
    for saved in saved_items:
        payload = open_by_id[str(saved.loan_id)]
        deadline = payload.get("funding_deadline")
        if isinstance(deadline, str):
            deadline = date.fromisoformat(deadline)
        if deadline is None:
            continue
        saved_on = business_date(saved.created_at)
        days_left = (deadline - today).days
        # Milestones whose day has come, and that fall after the day of saving.
        due = [
            days
            for days in REMINDER_DAYS_BEFORE
            if days_left <= days and (deadline.toordinal() - days) > saved_on.toordinal()
        ]
        if not due:
            continue
        done = set(
            SavedOpportunityReminder.objects.filter(
                loan_id=saved.loan_id,
                investor_user_id=saved.investor_user_id,
                funding_deadline=deadline,
            ).values_list("days_before", flat=True)
        )
        pending = [days for days in due if days not in done]
        if not pending:
            continue
        latest = min(pending)
        user = user_model.objects.filter(pk=saved.investor_user_id, is_active=True).first()
        try:
            with transaction.atomic():
                for days in pending:
                    if days == latest:
                        continue
                    SavedOpportunityReminder.objects.create(
                        loan_id=saved.loan_id,
                        investor_user_id=saved.investor_user_id,
                        funding_deadline=deadline,
                        days_before=days,
                        status=SavedOpportunityReminderStatus.SKIPPED,
                    )
                    skipped += 1
                if user is None:
                    continue
                reminder = SavedOpportunityReminder.objects.create(
                    loan_id=saved.loan_id,
                    investor_user_id=saved.investor_user_id,
                    funding_deadline=deadline,
                    days_before=latest,
                    status=SavedOpportunityReminderStatus.SENT,
                )
                emails_stopped = saved.email_reminders_stopped_at is not None
                message = enqueue_outbox_message(
                    OutboxCommand(
                        idempotency_key=f"saved-opportunity-reminder:{reminder.id}",
                        # Q14: after "Stop these alerts" the reminder is in-app only.
                        topic=(
                            SAVED_REMINDER_IN_APP_TOPIC
                            if emails_stopped
                            else "email.saved_opportunity_closing"
                        ),
                        payload=_reminder_payload(
                            user=user,
                            saved=saved,
                            payload=payload,
                            deadline=deadline,
                            days_left=days_left,
                        ),
                    )
                )
                if emails_stopped:
                    # Not an email topic, so no sender picks it up: done once it is listed.
                    type(message).objects.filter(pk=message.pk).update(
                        status=OutboxStatus.PROCESSED, processed_at=now_utc()
                    )
                SavedOpportunityReminder.objects.filter(pk=reminder.pk).update(
                    outbox_message=message
                )
                sent += 1
        except IntegrityError:
            # A run at the same time recorded this milestone first.
            continue
    return {"as_of": today.isoformat(), "reminders_sent": sent, "milestones_skipped": skipped}
