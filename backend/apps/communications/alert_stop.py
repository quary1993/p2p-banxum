"""IP of Webby-Soft SRL. Q14 (2026-11-13): one-click "Stop these alerts" links in alert emails.

Alerts the investor asked for can be stopped from the email, without signing in:

- Smart Invest match: stops the Smart Invest emails (the in-app setting and the matching stay);
- "Tell me when it opens": stops the request for that project;
- "Save for later" reminder: stops the reminder emails for that project (the saved item and the
  in-app reminders stay).

The link carries a token signed with the server secret (``django.core.signing``): the investor,
the kind of alert and the project. Nothing is stored for it; stopping is idempotent and can only
switch an alert off. The stored copy of an email has "[redacted]" in place of the token. The
public page calls the stop endpoint with a POST when it opens, so link scanners that only fetch
the page do not stop anything.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from importlib import import_module
from typing import Any

from django.apps import apps
from django.core import signing

ALERT_STOP_SALT = "banxum.alert-stop.v1"
# Old emails keep working for a year; after that the investor uses the settings.
ALERT_STOP_MAX_AGE_SECONDS = 400 * 24 * 60 * 60
KIND_SMART_INVEST = "smart_invest"
KIND_OPENING_ALERT = "opening_alert"
KIND_SAVED_REMINDER = "saved_reminder"
ALERT_STOP_KINDS = frozenset({KIND_SMART_INVEST, KIND_OPENING_ALERT, KIND_SAVED_REMINDER})
STOP_LINK_LABEL = "Stop these alerts"


class AlertStopTokenError(ValueError):
    """The link is not valid (unknown, changed or too old)."""


@dataclass(frozen=True, slots=True)
class AlertStopResult:
    kind: str
    loan_id: str | None
    loan_title: str
    message: str


def alert_stop_token(*, user_id: str, kind: str, loan_id: str | None = None) -> str:
    if kind not in ALERT_STOP_KINDS:
        raise ValueError(f"Unknown alert kind: {kind}")
    payload = {"u": str(user_id), "k": kind}
    if loan_id:
        payload["l"] = str(loan_id)
    return signing.dumps(payload, salt=ALERT_STOP_SALT, compress=True)


def alert_stop_url(*, base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/alerts/stop?token={urllib.parse.quote(token, safe='')}"


def _read_token(token: object) -> dict[str, str]:
    if not isinstance(token, str) or not token or len(token) > 512:
        raise AlertStopTokenError("This link is not valid.")
    try:
        payload = signing.loads(token, salt=ALERT_STOP_SALT, max_age=ALERT_STOP_MAX_AGE_SECONDS)
    except signing.BadSignature as exc:
        raise AlertStopTokenError("This link is not valid or is too old.") from exc
    if not isinstance(payload, dict) or payload.get("k") not in ALERT_STOP_KINDS:
        raise AlertStopTokenError("This link is not valid.")
    if not payload.get("u"):
        raise AlertStopTokenError("This link is not valid.")
    if payload["k"] != KIND_SMART_INVEST and not payload.get("l"):
        raise AlertStopTokenError("This link is not valid.")
    return {key: str(value) for key, value in payload.items()}


def _loan_title(loan_id: str | None) -> str:
    if not loan_id:
        return ""
    title = (
        apps.get_model("loans", "Loan")
        .objects.filter(pk=loan_id)
        .values_list("title", flat=True)
        .first()
    )
    return str(title or "")


def stop_alerts(token: object) -> AlertStopResult:
    """Switch the alert of the link off and say exactly what stopped (repeating is fine)."""
    payload = _read_token(token)
    kind = payload["k"]
    user_id = payload["u"]
    loan_id = payload.get("l")
    title = _loan_title(loan_id)
    if kind == KIND_SMART_INVEST:
        import_module("backend.apps.smart_invest.services").stop_smart_invest_emails(
            investor_user_id=user_id
        )
        message = (
            "Smart Invest emails are stopped. Your preferences, the in-app alerts and your "
            "matches stay. You can switch the emails on again in Smart Invest."
        )
    elif kind == KIND_OPENING_ALERT:
        import_module("backend.apps.marketplace_primary.services").stop_loan_opening_alert(
            investor_user_id=user_id, loan_id=str(loan_id)
        )
        message = (
            f"You will not get an email when {title or 'this opportunity'} opens. "
            "You can ask again on the opportunity page."
        )
    else:
        import_module(
            "backend.apps.marketplace_primary.saved_opportunities"
        ).stop_saved_reminder_emails(investor_user_id=user_id, loan_id=str(loan_id))
        message = (
            f"Reminder emails for {title or 'this saved opportunity'} are stopped. "
            "The opportunity stays saved and the reminders still show in the platform."
        )
    return AlertStopResult(kind=kind, loan_id=loan_id, loan_title=title, message=message)


def stop_link_from_payload(
    payload: dict[str, Any], *, base_url: str, redact: bool
) -> tuple[str, str] | None:
    """The (label, URL) of an email whose payload asks for a stop link, or None."""
    stop = payload.get("stop_alerts")
    user_id = str(payload.get("user_id") or "")
    if not isinstance(stop, dict) or not user_id or stop.get("kind") not in ALERT_STOP_KINDS:
        return None
    token = (
        "[redacted]"
        if redact
        else alert_stop_token(
            user_id=user_id, kind=str(stop["kind"]), loan_id=str(stop.get("loan_id") or "") or None
        )
    )
    return STOP_LINK_LABEL, alert_stop_url(base_url=base_url, token=token)
