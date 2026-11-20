"""IP of Webby-Soft SRL. 18.4 (F17): the CHF and EUR settlement calendars.

Each year is preloaded from the rule list and kept in the database; operations add or remove
days and confirm the year in the admin. A year without stored rows uses the rule list, so the
platform never stops when a calendar is missing; the daily check preloads the current and the next
year and opens an operations task while the next year is not confirmed (from 1 November).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from importlib import import_module
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Model

from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.settlement_calendar import (
    SETTLEMENT_CURRENCIES,
    SettlementDays,
    rule_holidays,
)
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import SettlementCalendarYear, SettlementHoliday
from backend.apps.platform_core.models.settlement_calendar import SettlementHolidaySource
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message

# From this day of the year (MM-DD) the next year's calendar must be confirmed.
NEXT_YEAR_CONFIRMATION_FROM = (11, 1)
CALENDAR_TASK_RELATED_TYPE = "SettlementCalendarYear"


class SettlementCalendarError(RuntimeError):
    pass


class SettlementCalendarAuthorizationError(SettlementCalendarError):
    pass


class SettlementCalendarValidationError(SettlementCalendarError):
    pass


def _currency(value: str) -> str:
    code = str(value or "").strip().upper()
    if code not in SETTLEMENT_CURRENCIES:
        raise SettlementCalendarValidationError(
            f"There is no settlement calendar for {value or 'this currency'}. Use CHF or EUR."
        )
    return code


def _stored_holidays(currency: str, year: int) -> frozenset[date] | None:
    """Active closed days of a stored year, or None when the year was never preloaded."""
    if not SettlementCalendarYear.objects.filter(currency=currency, year=year).exists():
        return None
    return frozenset(
        SettlementHoliday.objects.filter(
            currency=currency, date__year=year, is_active=True
        ).values_list("date", flat=True)
    )


def settlement_calendar(currency: str) -> SettlementDays:
    """The settlement days of a currency: stored years, else the rule list (lazy per year)."""
    code = _currency(currency)

    def holidays_for_year(year: int) -> frozenset[date]:
        stored = _stored_holidays(code, year)
        if stored is not None:
            return stored
        return frozenset(rule_holidays(code, year))

    return SettlementDays(holidays_for_year)


class SettlementCalendars:
    """One calendar per currency, built once per operation (a scan, a balance summary)."""

    def __init__(self) -> None:
        self._calendars: dict[str, SettlementDays] = {}

    def for_currency(self, currency: str) -> SettlementDays | None:
        code = str(currency or "").upper()
        if code not in SETTLEMENT_CURRENCIES:
            return None
        if code not in self._calendars:
            self._calendars[code] = settlement_calendar(code)
        return self._calendars[code]


def _require_admin(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise SettlementCalendarAuthorizationError(
            "Only an active admin can manage the settlement calendars."
        )


@transaction.atomic
def ensure_calendar_year(
    currency: str, year: int, *, actor: ActorRef | None = None
) -> tuple[SettlementCalendarYear, bool]:
    """Preload a year from the rule list when it is not stored yet. Returns (year, created)."""
    code = _currency(currency)
    if not 2000 <= year <= 2100:
        raise SettlementCalendarValidationError("Choose a year between 2000 and 2100.")
    existing = SettlementCalendarYear.objects.filter(currency=code, year=year).first()
    if existing is not None:
        return existing, False
    actor_ref = actor or ActorRef.system()
    preloaded_at = now_utc()
    try:
        with transaction.atomic():
            calendar_year = SettlementCalendarYear.objects.create(
                currency=code,
                year=year,
                preloaded_at=preloaded_at,
                preloaded_by=f"{actor_ref.actor_type}:{actor_ref.actor_id}",
            )
    except IntegrityError:
        return SettlementCalendarYear.objects.get(currency=code, year=year), False
    for holiday_date, name in rule_holidays(code, year).items():
        SettlementHoliday.objects.get_or_create(
            currency=code,
            date=holiday_date,
            defaults={
                "name": name,
                "source": SettlementHolidaySource.RULE,
                "created_by": f"{actor_ref.actor_type}:{actor_ref.actor_id}",
            },
        )
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="settlement_calendar.preloaded",
            target_type="SettlementCalendarYear",
            target_id=str(calendar_year.id),
            metadata={"currency": code, "year": year},
        )
    )
    return calendar_year, True


def calendar_year_payload(currency: str, year: int) -> dict[str, Any]:
    code = _currency(currency)
    calendar_year = SettlementCalendarYear.objects.filter(currency=code, year=year).first()
    rows = SettlementHoliday.objects.filter(currency=code, date__year=year).order_by("date")
    return {
        "currency": code,
        "year": year,
        "stored": calendar_year is not None,
        "preloaded_at": calendar_year.preloaded_at if calendar_year else None,
        "confirmed_at": calendar_year.confirmed_at if calendar_year else None,
        "confirmed_by_admin_id": (
            str(calendar_year.confirmed_by_admin_id)
            if calendar_year and calendar_year.confirmed_by_admin_id
            else None
        ),
        "confirmation_note": calendar_year.confirmation_note if calendar_year else "",
        "revision": calendar_year.revision if calendar_year else 0,
        # Audit S3-4: a day changed after the year was confirmed; confirm it again.
        "reconfirmation_needed_since": (
            calendar_year.reconfirmation_needed_since if calendar_year else None
        ),
        "days": [
            {
                "id": str(row.id),
                "date": row.date,
                "name": row.name,
                "origin": row.source,
                "is_active": row.is_active,
                "removal_reason": row.removal_reason,
            }
            for row in rows
        ]
        if calendar_year is not None
        else [
            {
                "id": "",
                "date": holiday_date,
                "name": name,
                "origin": SettlementHolidaySource.RULE,
                "is_active": True,
                "removal_reason": "",
            }
            for holiday_date, name in rule_holidays(code, year).items()
        ],
    }


@dataclass(frozen=True, slots=True)
class AddSettlementHolidayCommand:
    actor: Model
    currency: str
    date: date
    name: str


@dataclass(frozen=True, slots=True)
class RemoveSettlementHolidayCommand:
    actor: Model
    currency: str
    date: date
    reason: str


@dataclass(frozen=True, slots=True)
class ConfirmSettlementCalendarYearCommand:
    actor: Model
    currency: str
    year: int
    note: str = ""


@transaction.atomic
def add_settlement_holiday(command: AddSettlementHolidayCommand) -> dict[str, Any]:
    _require_admin(command.actor)
    code = _currency(command.currency)
    name = command.name.strip()
    if not name:
        raise SettlementCalendarValidationError("Give the name of the closed day.")
    if command.date.weekday() >= 5:
        raise SettlementCalendarValidationError(
            "Saturdays and Sundays are never settlement days; there is nothing to add."
        )
    actor_ref = actor_ref_for_user(command.actor)
    ensure_calendar_year(code, command.date.year, actor=actor_ref)
    row = (
        SettlementHoliday.objects.select_for_update()
        .filter(currency=code, date=command.date)
        .first()
    )
    if row is not None and row.is_active:
        raise SettlementCalendarValidationError(
            f"{command.date.isoformat()} is already a closed day ({row.name})."
        )
    if row is None:
        row = SettlementHoliday.objects.create(
            currency=code,
            date=command.date,
            name=name,
            source=SettlementHolidaySource.ADMIN,
            created_by=f"{actor_ref.actor_type}:{actor_ref.actor_id}",
        )
    else:
        row.is_active = True
        row.name = name
        row.removed_at = None
        row.removed_by_admin_id = None
        row.removal_reason = ""
        row.save(
            update_fields=[
                "is_active",
                "name",
                "removed_at",
                "removed_by_admin_id",
                "removal_reason",
                "updated_at",
            ]
        )
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="settlement_calendar.day_closed",
            target_type="SettlementHoliday",
            target_id=str(row.id),
            metadata={"currency": code, "date": command.date.isoformat(), "name": name},
        )
    )
    _calendar_year_changed(
        actor=command.actor,
        currency=code,
        year=command.date.year,
        change=f"{command.date.isoformat()} closed ({name})",
    )
    return calendar_year_payload(code, command.date.year)


@transaction.atomic
def remove_settlement_holiday(command: RemoveSettlementHolidayCommand) -> dict[str, Any]:
    _require_admin(command.actor)
    code = _currency(command.currency)
    reason = command.reason.strip()
    if not reason:
        raise SettlementCalendarValidationError("Give the reason why this day is open.")
    actor_ref = actor_ref_for_user(command.actor)
    ensure_calendar_year(code, command.date.year, actor=actor_ref)
    row = (
        SettlementHoliday.objects.select_for_update()
        .filter(currency=code, date=command.date, is_active=True)
        .first()
    )
    if row is None:
        raise SettlementCalendarValidationError(
            f"{command.date.isoformat()} is not a closed day in the {code} calendar."
        )
    row.is_active = False
    row.removed_at = now_utc()
    row.removed_by_admin_id = command.actor.pk
    row.removal_reason = reason
    row.save(
        update_fields=[
            "is_active",
            "removed_at",
            "removed_by_admin_id",
            "removal_reason",
            "updated_at",
        ]
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="settlement_calendar.day_opened",
            target_type="SettlementHoliday",
            target_id=str(row.id),
            metadata={"currency": code, "date": command.date.isoformat(), "reason": reason},
        )
    )
    _calendar_year_changed(
        actor=command.actor,
        currency=code,
        year=command.date.year,
        change=f"{command.date.isoformat()} opened ({reason})",
    )
    return calendar_year_payload(code, command.date.year)


def _calendar_year_changed(*, actor: Model, currency: str, year: int, change: str) -> None:
    """Audit S3-4: a changed day gives the year a new revision. A confirmation was given for
    the days as they were, so it is cleared and the confirmation task opens again."""
    calendar_year = SettlementCalendarYear.objects.select_for_update().get(
        currency=currency, year=year
    )
    was_confirmed = calendar_year.confirmed_at is not None
    calendar_year.revision += 1
    update_fields = ["revision", "updated_at"]
    if was_confirmed:
        previous = {
            "confirmed_at": calendar_year.confirmed_at.isoformat()
            if calendar_year.confirmed_at
            else "",
            "confirmed_by_admin_id": str(calendar_year.confirmed_by_admin_id or ""),
            "confirmation_note": calendar_year.confirmation_note,
        }
        calendar_year.confirmed_at = None
        calendar_year.confirmed_by_admin_id = None
        calendar_year.confirmation_note = ""
        calendar_year.reconfirmation_needed_since = now_utc()
        update_fields += [
            "confirmed_at",
            "confirmed_by_admin_id",
            "confirmation_note",
            "reconfirmation_needed_since",
        ]
    calendar_year.save(update_fields=update_fields)
    if not was_confirmed:
        return
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="settlement_calendar.confirmation_cleared",
            target_type="SettlementCalendarYear",
            target_id=str(calendar_year.id),
            metadata={
                "currency": currency,
                "year": year,
                "revision": calendar_year.revision,
                "change": change,
                "previous_confirmation": previous,
            },
        )
    )
    _open_calendar_alert(actor=actor, calendar_year=calendar_year, change=change)


def calendar_year_is_confirmed(task_object_id: str) -> bool:
    """For the confirmation task ("CHF:2027"): True when its year is confirmed. An id that
    names no stored year blocks nothing."""
    currency, _, year = str(task_object_id).partition(":")
    if not year.isdigit():
        return True
    calendar_year = SettlementCalendarYear.objects.filter(
        currency=currency.upper(), year=int(year)
    ).first()
    return calendar_year is None or calendar_year.confirmed_at is not None


@transaction.atomic
def confirm_settlement_calendar_year(
    command: ConfirmSettlementCalendarYearCommand,
) -> dict[str, Any]:
    _require_admin(command.actor)
    code = _currency(command.currency)
    actor_ref = actor_ref_for_user(command.actor)
    calendar_year, _created = ensure_calendar_year(code, command.year, actor=actor_ref)
    calendar_year = SettlementCalendarYear.objects.select_for_update().get(id=calendar_year.id)
    calendar_year.confirmed_at = now_utc()
    calendar_year.confirmed_by_admin_id = command.actor.pk
    calendar_year.confirmation_note = command.note.strip()
    calendar_year.reconfirmation_needed_since = None
    calendar_year.save(
        update_fields=[
            "confirmed_at",
            "confirmed_by_admin_id",
            "confirmation_note",
            "reconfirmation_needed_since",
            "updated_at",
        ]
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="settlement_calendar.confirmed",
            target_type="SettlementCalendarYear",
            target_id=str(calendar_year.id),
            metadata={
                "currency": code,
                "year": command.year,
                "note": command.note.strip(),
                "revision": calendar_year.revision,
            },
        )
    )
    admin_ops: Any = import_module("backend.apps.admin_ops.services")
    admin_ops.resolve_related_admin_task(
        actor=command.actor,
        related_object_type=CALENDAR_TASK_RELATED_TYPE,
        related_object_id=f"{code}:{command.year}",
        completion_note="The settlement calendar was confirmed.",
    )
    return calendar_year_payload(code, command.year)


def check_settlement_calendars(*, actor: Model, as_of: datetime) -> dict[str, Any]:
    """Daily: preload this year and the next. Alert from 1 November while next year is not
    confirmed, and at any time while a year waits to be confirmed again after a change."""
    today = business_date(as_of)
    actor_ref = actor_ref_for_user(actor)
    preloaded: list[str] = []
    alerts: list[str] = []
    for code in SETTLEMENT_CURRENCIES:
        for year in (today.year, today.year + 1):
            calendar_year, created = ensure_calendar_year(code, year, actor=actor_ref)
            if created:
                preloaded.append(f"{code}:{year}")
            if calendar_year.confirmed_at is not None:
                continue
            next_year_due = (
                year == today.year + 1 and (today.month, today.day) >= NEXT_YEAR_CONFIRMATION_FROM
            )
            if not next_year_due and calendar_year.reconfirmation_needed_since is None:
                continue
            if _open_calendar_alert(actor=actor, calendar_year=calendar_year):
                alerts.append(f"{code}:{year}")
    return {"as_of_date": today.isoformat(), "preloaded": preloaded, "alerts": alerts}


def _open_calendar_alert(
    *, actor: Model, calendar_year: SettlementCalendarYear, change: str = ""
) -> bool:
    """One operations task per currency and year, open while the year is not confirmed, and one
    email per revision of the year. True when the task was opened (new, or opened again)."""
    currency, year = str(calendar_year.currency), int(calendar_year.year)
    admin_ops: Any = import_module("backend.apps.admin_ops.services")
    changed = calendar_year.reconfirmation_needed_since is not None
    notes = (
        (
            f"The {currency} settlement calendar for {year} changed after it was confirmed"
            + (f" ({change})" if change else "")
            + ". Check the year again and confirm it. "
            if changed
            else f"The {currency} settlement calendar for {year} is preloaded from the rule "
            "list but not confirmed. "
        )
        + "Check it against the bank and the published calendar "
        f"({'SIX SIC' if currency == 'CHF' else 'TARGET'}), change any day in Settlement "
        "calendars, then confirm the year. Return dates and due dates use it. This task "
        "closes when the year is confirmed."
    )
    task, opened = admin_ops.ensure_related_admin_task(
        actor=actor,
        task_type="settlement_calendar",
        related_object_type=CALENDAR_TASK_RELATED_TYPE,
        related_object_id=f"{currency}:{year}",
        title=f"Confirm the {currency} settlement calendar for {year}",
        priority="high",
        notes=notes,
        # Audit S3-4: a task closed while the year is not confirmed opens again.
        reopen_closed=True,
    )
    if not opened:
        return False
    revision = int(calendar_year.revision)
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=(
                f"email:settlement-calendar-unconfirmed:{currency}:{year}"
                + (f":r{revision}" if revision else "")
            ),
            topic="email.operations_alert",
            payload={
                "email": str(getattr(settings, "OPERATIONS_ALERT_EMAIL", "") or "hq@banxum.com"),
                "subject": f"Confirm the {currency} settlement calendar for {year}",
                "notice_label": "Operations alert",
                "headline": "A settlement calendar is not confirmed",
                "status_label": "Action needed",
                "status_tone": "warning",
                "body_text": (
                    (
                        f"The {currency} settlement calendar for {year} changed after it was "
                        "confirmed, so it is not confirmed now. The platform uses the stored "
                        "days. "
                        if changed
                        else f"The {currency} settlement calendar for {year} is not confirmed. "
                        "The platform uses the preloaded rule days until then. "
                    )
                    + "Check the days and confirm the year in the admin console (Settlement "
                    "calendars)."
                ),
                "template_key": "ops.settlement_calendar_unconfirmed.v1",
                "data_rows": [["Currency", currency], ["Year", str(year)]],
                "metadata": {
                    "currency": currency,
                    "year": year,
                    "revision": revision,
                    "admin_task_id": str(task.id),
                },
            },
        )
    )
    return True
