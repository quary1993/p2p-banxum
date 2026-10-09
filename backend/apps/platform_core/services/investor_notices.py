"""Transactional investor notices (plan 14, COMMS-DEC-001/003).

One business event creates one email outbox message. The communications module renders it
with the BANXUM email template at dispatch time, and the investor notification centre lists
the same message. Transactional notices are mandatory, so no preference is checked here.

Callers add a notice at the end of the successful service path, inside the same database
transaction: a rolled-back business change never leaves a notice behind. The idempotency key
names the business event, so a repeated or retried service call cannot create a second notice.

Notices never carry secrets: no login links, codes or full IBANs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

from django.apps import apps
from django.conf import settings

from backend.apps.platform_core.domain.money import format_amount_minor
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.models import Currency, OutboxMessage
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message

# Portal pages a notice can open (investor_portal NOTIFICATION_TARGET_TYPES) and their paths.
NOTICE_TARGET_PATHS = {
    "none": "/notifications",
    "loan": "/marketplace/{id}",
    "holding": "/portfolio/{id}",
    "portfolio": "/portfolio",
    "balances": "/balances",
    "secondary_market": "/secondary-market",
    "fx": "/fx",
}
_TARGETS_WITH_ID = frozenset({"loan", "holding"})

LOAN_STATUS_LATE = "late"
LOAN_STATUS_DEFAULTED = "defaulted"


@dataclass(frozen=True, slots=True)
class InvestorNotice:
    investor_user_id: str
    topic: str
    idempotency_key: str
    subject: str
    body_text: str
    template_key: str
    headline: str = ""
    notice_label: str = "Investor notice"
    status_label: str = "Information"
    status_tone: str = "info"
    data_rows: tuple[tuple[str, str], ...] = ()
    navigation_target: str = "none"
    navigation_target_id: str = ""
    action_label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def brand() -> str:
    return str(settings.PLATFORM_BRAND_NAME)


def notice_amount(amount_minor: int, currency: Any) -> str:
    """Amount text in the currency's own minor units, e.g. "CHF 25'000.00"."""
    code = str(getattr(currency, "code", currency)).upper()
    minor_units = getattr(currency, "minor_units", None)
    if minor_units is None:
        minor_units = (
            Currency.objects.filter(code=code).values_list("minor_units", flat=True).first()
        )
    return format_amount_minor(
        int(amount_minor), code, minor_units=2 if minor_units is None else int(minor_units)
    )


def notice_date(value: date | datetime) -> str:
    """Europe/Zurich business date text; datetimes come from the platform clock."""
    if isinstance(value, datetime):
        return business_date(value).isoformat()
    return value.isoformat()


def masked_iban(iban: str) -> str:
    compact = "".join(str(iban).split()).upper()
    return f"IBAN ending {compact[-4:]}" if len(compact) >= 4 else "IBAN on file"


def _uuid_text(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return ""


def _investor_email(investor_user_id: str) -> str:
    user_model = apps.get_model("accounts_auth", "User")
    user = user_model.objects.filter(id=investor_user_id).only("email").first()
    return str(getattr(user, "email", "")).strip().lower() if user is not None else ""


def _navigation(notice: InvestorNotice) -> tuple[str, str]:
    target = notice.navigation_target if notice.navigation_target in NOTICE_TARGET_PATHS else "none"
    target_id = _uuid_text(notice.navigation_target_id) if target in _TARGETS_WITH_ID else ""
    if target in _TARGETS_WITH_ID and not target_id:
        target = "portfolio" if target == "holding" else "none"
    return target, target_id


def investor_notice_payload(notice: InvestorNotice, *, email: str) -> dict[str, Any]:
    """Outbox payload in the shape the communications payload renderer reads."""
    target, target_id = _navigation(notice)
    base_url = str(getattr(settings, "PUBLIC_APP_BASE_URL", "") or "").rstrip("/")
    buttons: list[dict[str, str]] = []
    if base_url.startswith(("https://", "http://")):
        path = NOTICE_TARGET_PATHS[target].format(id=target_id)
        buttons.append(
            {"label": notice.action_label or f"Open {brand()}", "url": f"{base_url}{path}"}
        )
    return {
        "user_id": notice.investor_user_id,
        "email": email,
        "subject": notice.subject,
        "headline": notice.headline or notice.subject,
        "notice_label": notice.notice_label,
        "preheader": notice.body_text.split("\n", 1)[0][:180],
        "status_label": notice.status_label,
        "status_tone": notice.status_tone,
        "body_text": notice.body_text,
        "template_key": notice.template_key,
        "data_rows": [[label, value] for label, value in notice.data_rows if label and value],
        "buttons": buttons,
        "metadata": {
            **notice.metadata,
            "navigation_target": target,
            "navigation_target_id": target_id,
        },
    }


def enqueue_investor_notice(notice: InvestorNotice) -> OutboxMessage | None:
    """Queue the email and portal notice once per idempotency key."""
    email = _investor_email(notice.investor_user_id)
    if not email:
        return None
    return enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"notice:{notice.idempotency_key}",
            topic=notice.topic,
            payload=investor_notice_payload(notice, email=email),
        )
    )


def notify_loan_holders_of_status_change(
    *,
    loan: Any,
    new_status: str,
    as_of_date: date,
    days_past_due: int,
) -> int:
    """Tell the current holders of a Direct or LO loan that it is now Late or Defaulted.

    One notice per investor, loan, status and business date. Returns the notice count.
    """
    if new_status not in {LOAN_STATUS_LATE, LOAN_STATUS_DEFAULTED}:
        return 0
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holdings = (
        holding_model.objects.filter(
            loan_id=loan.pk, status="active", current_principal_minor__gt=0
        )
        .order_by("investor_user_id", "assignment_effective_at", "id")
        .values_list("investor_user_id", "id", "current_principal_minor")
    )
    by_investor: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for investor_user_id, holding_id, principal_minor in holdings:
        by_investor[str(investor_user_id)].append((str(holding_id), int(principal_minor)))
    currency = loan.currency
    title = str(loan.title)
    platform = brand()
    count = 0
    for investor_user_id, rows in by_investor.items():
        principal = notice_amount(sum(amount for _id, amount in rows), currency)
        if new_status == LOAN_STATUS_LATE:
            subject = f"Loan payment late: {title}"
            body = (
                f"The borrower of {title} has not paid an installment that was due "
                f"{days_past_due} days ago. The loan status is now Late.\n\n"
                f"{platform} is following up with the borrower. Payments to you from this loan "
                "can be late."
            )
            status_label, tone = ("Late payment", "warning")
        else:
            subject = f"Loan in default: {title}"
            body = (
                f"The borrower of {title} has not paid an installment for {days_past_due} days. "
                "The loan status is now Defaulted.\n\n"
                f"{platform} starts the recovery process. Recovery can take time, and you can "
                "get back less than the amount due."
            )
            status_label, tone = ("Default", "danger")
        enqueue_investor_notice(
            InvestorNotice(
                investor_user_id=investor_user_id,
                topic="email.loan_status_changed",
                idempotency_key=(
                    f"loan-status:{loan.pk}:{new_status}:{as_of_date.isoformat()}:"
                    f"{investor_user_id}"
                ),
                subject=subject,
                body_text=body,
                template_key=f"loans.status_{new_status}.v1",
                notice_label="Loan notice",
                status_label=status_label,
                status_tone=tone,
                data_rows=(
                    ("Loan", title),
                    ("New status", "Late" if new_status == LOAN_STATUS_LATE else "Defaulted"),
                    ("Days past due", str(days_past_due)),
                    ("Your current principal", principal),
                    ("Status date", notice_date(as_of_date)),
                ),
                navigation_target="holding",
                navigation_target_id=rows[0][0],
                action_label="View your investment",
                metadata={
                    "loan_id": str(loan.pk),
                    "holding_ids": [holding_id for holding_id, _amount in rows],
                    "new_status": new_status,
                    "days_past_due": days_past_due,
                    "as_of_date": as_of_date.isoformat(),
                    "currency": str(getattr(currency, "code", currency)),
                    "current_principal_minor": sum(amount for _id, amount in rows),
                },
            )
        )
        count += 1
    return count
