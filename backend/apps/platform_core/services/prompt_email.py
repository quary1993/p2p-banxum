"""IP of Webby-Soft SRL. Start delivery of requested email without blocking its HTTP response."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from functools import partial
from importlib import import_module
from threading import BoundedSemaphore

from django.conf import settings
from django.db import connections, transaction

from backend.apps.platform_core.services.qa_guard import QaEnvironmentBusy, qa_environment_guard

logger = logging.getLogger(__name__)

# Sign-up links, operation codes and PIN notices already have their own immediate dispatcher.
# Reminders, campaigns, digests and in-app-only notices stay on their existing schedule.
_PROMPT_TOPICS = frozenset(
    {
        "email.password_reset",
        "email.security_change",
        "email.security_new_sign_in",
        "marketing_email.newsletter_confirmation",
        "email.public_enquiry",
        "email.investor_support_request",
        "email.support_request_received",
        "email.deposit_reconciled",
        "email.primary_investment_confirmation",
        "email.primary_order_released",
        "email.originator_claim_purchase_confirmation",
        "email.secondary_market_purchase_confirmation",
        "email.secondary_market_sale_confirmation",
        "email.secondary_market_listing_status",
        "email.fx_exchange_confirmation",
        "email.withdrawal_status",
        "email.balance_return_failed",
        "email.payout_account_status",
        "email.compliance_review_opened",
        "email.compliance_more_information",
    }
)
# Threads start on first use. Bound both concurrent sends and queued work in each process.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="requested-mail")
_slots = BoundedSemaphore(16)
_from_request = ContextVar("banxum_prompt_email_request", default=False)


@contextmanager
def prompt_email_request() -> Iterator[None]:
    token = _from_request.set(True)
    try:
        yield
    finally:
        _from_request.reset(token)


def schedule_prompt_email(
    message_id: int, key: str, topic: str, *, template_key: object = None
) -> None:
    if not settings.COMMUNICATIONS_IMMEDIATE_AUTH_EMAILS:
        return
    # Offline imports and seeds keep their existing behaviour. A recovery link is issued
    # by the scheduled job, but is time-sensitive once its waiting period has ended.
    if not _from_request.get() and not (
        topic == "email.password_reset" and template_key == "security.assisted_recovery_link.v1"
    ):
        return
    if topic not in _PROMPT_TOPICS and not (
        topic == "email.operations_alert" and template_key == "ops.assisted_recovery_disputed.v1"
    ):
        return
    transaction.on_commit(partial(_submit, message_id, key), robust=True)


def _submit(message_id: int, key: str) -> None:
    if not _slots.acquire(blocking=False):
        return  # The scheduled sender still owns the durable outbox row.
    try:
        _executor.submit(_deliver, message_id, key)
    except RuntimeError:
        _slots.release()
        logger.warning("prompt_email_submission_unavailable")


def _deliver(message_id: int, key: str) -> None:
    try:
        communications = import_module("backend.apps.communications.services")
        with qa_environment_guard():
            communications.dispatch_email_outbox_message_now(message_id, expected_key=key)
    except QaEnvironmentBusy:
        pass  # A staging snapshot or restore holds the exclusive lock.
    except Exception:
        # Do not log provider exceptions: they may contain recipient data or a reset link.
        logger.warning("prompt_email_dispatch_unavailable")
    finally:
        try:
            connections.close_all()
        finally:
            _slots.release()
