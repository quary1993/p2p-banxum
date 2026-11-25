"""IP of Webby-Soft SRL. Read-only check of the emails to one address.

For support and QA ("I did not get the email"). It shows why an email was or was not sent: the
account and whether a password reset can be sent to it, the reset requests, the queued emails
(outbox), the delivery attempts with the provider answer, the email job and the configured
provider. It prints no secret: no token, no link and no email body. It changes nothing.

    manage.py check_email_delivery --email someone@example.com
"""

from __future__ import annotations

import re
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from backend.apps.platform_core.models.scheduled_jobs import ScheduledJobRun, ScheduledJobRunStatus
from backend.apps.platform_core.services.scheduled_jobs import EMAIL_OUTBOX_DISPATCH_JOB

# The investor sign-in reset (accounts_auth.two_factor.request_password_reset) sends only to these.
INVESTOR_ACCOUNT_TYPES = {"natural_person_lender", "legal_entity_lender_representative"}


def _when(value: Any) -> str:
    return value.isoformat(timespec="seconds") if value else "-"


def _safe_error(value: str) -> str:
    # Exceptions can contain provider responses, addresses and reset URLs.
    if re.fullmatch(
        r"(?:SendGrid|Twilio Email) (?:returned HTTP [1-5][0-9]{2}|provider is not configured"
        r"|request failed|returned an invalid response|response did not include an operation id)\.",
        value,
    ):
        return value
    return "Details withheld."


class Command(BaseCommand):
    help = "Show, without changing anything, why emails to one address were or were not sent."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("--email", required=True)
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--reset-only", action="store_true", help="Show only password resets.")

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        email = str(options["email"]).strip().lower()
        limit = max(1, int(options["limit"]))
        write = self.stdout.write

        write(f"Email provider: {settings.COMMUNICATIONS_EMAIL_PROVIDER}")
        if str(settings.COMMUNICATIONS_EMAIL_PROVIDER) in {"mock", "local"}:
            write("  This provider sends nothing outside the platform.")

        user_model = apps.get_model("accounts_auth", "User")
        user = user_model.objects.filter(email=email).first()
        write("")
        write("Account")
        if user is None:
            write("  No account uses this email address.")
            write(
                "  A password reset request sends nothing; the screen answers the same for every "
                "address (no account enumeration)."
            )
        else:
            account = user
            account_type = str(account.account_type)
            status = str(account.status)
            can_sign_in = account.can_login
            write(f"  Type: {account_type}; status: {status}; active: {account.is_active}")
            if account_type not in INVESTOR_ACCOUNT_TYPES:
                write(
                    "  Password reset: not sent. The investor reset is only for investor accounts; "
                    "this is a staff account."
                )
            elif not can_sign_in:
                write(
                    "  Password reset: not sent. The account cannot sign in (status or inactive)."
                )
            else:
                write("  Password reset: can be sent.")
            token_model = apps.get_model("accounts_auth", "PasswordResetToken")
            tokens = token_model.objects.filter(user=account)
            if options["reset_only"]:
                tokens = tokens.filter(purpose="password_reset")
            tokens = tokens.order_by("-created_at", "-pk")[:limit]
            write("")
            write("Reset requests (newest first)")
            if not tokens:
                write("  None.")
            for token in tokens:
                write(
                    f"  {_when(token.created_at)} {token.purpose}: "
                    f"expires {_when(token.expires_at)}, used {_when(token.used_at)}, "
                    f"replaced {_when(token.superseded_at)}"
                )

        outbox_model = apps.get_model("platform_core", "OutboxMessage")
        match = Q(payload__email=email)
        if user is not None:
            match |= Q(payload__user_id=str(user.pk))
        messages = outbox_model.objects.filter(match, topic__startswith="email.")
        if options["reset_only"]:
            messages = messages.filter(topic="email.password_reset")
        messages = messages.order_by("-created_at", "-pk")[:limit]
        write("")
        write("Queued emails (outbox, newest first)")
        if not messages:
            write("  None.")
        for message in messages:
            write(
                f"  {_when(message.created_at)} {message.topic}: {message.status}, "
                f"attempts {message.attempts}, next {_when(message.next_attempt_at)}, "
                f"processed {_when(message.processed_at)}"
            )
            if message.last_error:
                write(f"    Last error: {_safe_error(message.last_error)}")

        record_model = apps.get_model("communications", "EmailDeliveryRecord")
        records = record_model.objects.filter(recipient_email__iexact=email)
        if options["reset_only"]:
            records = records.filter(topic="email.password_reset")
        records = records.order_by("-created_at", "-attempt_number", "-pk")[:limit]
        write("")
        write("Delivery attempts (newest first)")
        if not records:
            write("  None.")
        for record in records:
            write(
                f"  {_when(record.created_at)} {record.topic}: {record.status} via "
                f"{record.provider}, attempt {record.attempt_number}, "
                f"sent {_when(record.sent_at)}, provider reference "
                f"{'present' if record.provider_message_id else 'absent'}"
            )
            if record.error:
                write(f"    Error: {_safe_error(record.error)}")

        last_run = ScheduledJobRun.objects.filter(job_name=EMAIL_OUTBOX_DISPATCH_JOB).first()
        last_success = ScheduledJobRun.objects.filter(
            job_name=EMAIL_OUTBOX_DISPATCH_JOB, status=ScheduledJobRunStatus.SUCCEEDED
        ).first()
        write("")
        write("Email job (email_outbox_dispatch)")
        if last_run is None:
            write("  No scheduled run recorded. Check the five-minute cron entry.")
        else:
            write(f"  Last run: {_when(last_run.started_at)} ({last_run.status})")
            write(f"  Last success: {_when(last_success.started_at if last_success else None)}")
            if last_run.error:
                write(f"  Error: {_safe_error(last_run.error)}")
