"""Newsletter "New projects by email": double opt-in, links, throttles, digest and cleanup."""

from __future__ import annotations

import json
import urllib.parse
from datetime import date, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from backend.apps.communications.models import (
    EmailDeliveryRecord,
    NewsletterDigestDelivery,
    NewsletterDigestRun,
    NewsletterDigestRunStatus,
    NewsletterSubscription,
    NewsletterSubscriptionStatus,
    PublicEnquiry,
)
from backend.apps.communications.newsletter import (
    NEWSLETTER_CONSENT_VERSION,
    TOKEN_PURPOSE_CONFIRM,
    TOKEN_PURPOSE_UNSUBSCRIBE,
    anonymise_old_newsletter_subscriptions,
    newsletter_token,
    render_newsletter_email,
    run_newsletter_new_projects_digest,
    token_hash,
)
from backend.apps.communications.public_forms import delete_expired_public_enquiries
from backend.apps.communications.services import (
    NEWSLETTER_CONFIRMATION_EMAIL_TOPIC,
    NEWSLETTER_NEW_PROJECTS_EMAIL_TOPIC,
    REDACTED_SECRET,
    dispatch_due_email_outbox_messages,
)
from backend.apps.communications.tests.conftest import ThrottleClock
from backend.apps.platform_core.models import Currency, OutboxMessage
from backend.apps.platform_core.models.events import OutboxStatus
from backend.apps.platform_core.models.scheduled_jobs import ScheduledJobRun, ScheduledJobRunStatus
from backend.apps.platform_core.services.scheduled_jobs import (
    DEFAULT_SCHEDULED_JOB_NAMES,
    NEWSLETTER_NEW_PROJECTS_JOB,
    PUBLIC_SITE_RETENTION_JOB,
    RunScheduledJobsCommand,
    run_scheduled_jobs,
)

SUBSCRIBE = "/api/v1/public/newsletter/subscribe/"
CONFIRM = "/api/v1/public/newsletter/confirm/"
UNSUBSCRIBE = "/api/v1/public/newsletter/unsubscribe/"
BASE_URL = "https://banxum.test"
ACCEPTED = {"detail": "Check your inbox to confirm."}
INVALID = {"detail": "This link is not valid or has expired.", "code": "invalid_token"}
ZURICH = ZoneInfo("Europe/Zurich")
BORROWER_NAME = "Secret Borrower Holding AG"

pytestmark = pytest.mark.usefixtures("throttle_clock")


def _subscribe(
    client: APIClient, email: str = "Reader@Example.test", *, ip: str = "203.0.113.50", **extra: Any
) -> Any:
    body = {"email": email, "source": "home", **extra}
    return client.post(SUBSCRIBE, body, format="json", REMOTE_ADDR=ip)


def _confirm_token(subscription: NewsletterSubscription) -> str:
    return newsletter_token(
        TOKEN_PURPOSE_CONFIRM, subscription.id, subscription.confirm_token_nonce
    )


def _unsubscribe_token(subscription: NewsletterSubscription) -> str:
    return newsletter_token(
        TOKEN_PURPOSE_UNSUBSCRIBE, subscription.id, subscription.unsubscribe_token_nonce
    )


def _confirmation_messages() -> Any:
    return OutboxMessage.objects.filter(topic=NEWSLETTER_CONFIRMATION_EMAIL_TOPIC)


def _age_confirmations(subscription: NewsletterSubscription, delta: timedelta) -> None:
    """Move the last confirmation send (and its queued emails) back in time."""

    NewsletterSubscription.objects.filter(pk=subscription.pk).update(
        confirmation_sent_at=cast(datetime, subscription.confirmation_sent_at) - delta
    )
    for message in _confirmation_messages():
        OutboxMessage.objects.filter(pk=message.pk).update(created_at=message.created_at - delta)


def _confirmed(email: str = "fan@example.test") -> NewsletterSubscription:
    client = APIClient()
    _subscribe(client, email, ip="198.51.100.200")
    subscription = NewsletterSubscription.objects.get(email=email)
    client.post(CONFIRM, {"token": _confirm_token(subscription)}, format="json")
    subscription.refresh_from_db()
    assert subscription.status == NewsletterSubscriptionStatus.CONFIRMED
    return subscription


# --- Subscribe ----------------------------------------------------------------------------


@pytest.mark.django_db
def test_subscribe_creates_a_pending_row_and_one_confirmation(api_client: APIClient) -> None:
    response = _subscribe(api_client)

    assert response.status_code == 202
    assert response.json() == ACCEPTED
    subscription = NewsletterSubscription.objects.get()
    assert subscription.email == "reader@example.test"
    assert subscription.status == NewsletterSubscriptionStatus.PENDING
    assert subscription.source == "home"
    assert subscription.consent_version == NEWSLETTER_CONSENT_VERSION
    assert subscription.ip_hash and "203.0.113.50" not in subscription.ip_hash
    assert subscription.confirmation_sent_at is not None
    expires = cast(datetime, subscription.confirm_token_expires_at)
    assert timedelta(days=6, hours=23) < expires - timezone.now() <= timedelta(days=7)
    # Only hashes of the link tokens are stored.
    confirm_token = _confirm_token(subscription)
    unsubscribe_token = _unsubscribe_token(subscription)
    assert subscription.confirm_token_hash == token_hash(confirm_token)
    assert subscription.unsubscribe_token_hash == token_hash(unsubscribe_token)
    stored = json.dumps(
        {k: str(v) for k, v in NewsletterSubscription.objects.values().get().items()}
    )
    assert confirm_token not in stored and unsubscribe_token not in stored
    message = _confirmation_messages().get()
    assert set(message.payload) == {"subscription_id", "template_key"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "source": "home"},
        {"email": "", "source": "home"},
        {"source": "home"},
        {"email": "a" * 250 + "@example.test", "source": "home"},
    ],
)
def test_malformed_email_is_a_400_on_email(api_client: APIClient, body: dict[str, Any]) -> None:
    response = api_client.post(SUBSCRIBE, body, format="json")

    assert response.status_code == 400
    assert "email" in response.json()
    assert NewsletterSubscription.objects.count() == 0


@pytest.mark.django_db
def test_unknown_source_is_refused(api_client: APIClient) -> None:
    response = api_client.post(
        SUBSCRIBE, {"email": "a@example.test", "source": "tv"}, format="json"
    )

    assert response.status_code == 400
    assert "source" in response.json()


@pytest.mark.django_db
def test_honeypot_answers_the_same_and_stores_nothing(api_client: APIClient) -> None:
    response = _subscribe(api_client, website="https://spam.test")

    assert response.status_code == 202
    assert response.json() == ACCEPTED
    assert NewsletterSubscription.objects.count() == 0
    assert OutboxMessage.objects.count() == 0


@pytest.mark.django_db
def test_confirmed_address_gets_the_same_answer_and_no_email(api_client: APIClient) -> None:
    _confirmed("fan@example.test")
    before = OutboxMessage.objects.count()

    response = _subscribe(api_client, "FAN@example.test")

    assert response.status_code == 202
    assert response.json() == ACCEPTED
    assert OutboxMessage.objects.count() == before


@pytest.mark.django_db
def test_pending_address_gets_the_confirmation_again_at_most_hourly_and_three_a_day(
    api_client: APIClient,
) -> None:
    ips = iter(f"192.0.2.{index}" for index in range(1, 50))
    _subscribe(api_client, ip=next(ips))
    subscription = NewsletterSubscription.objects.get()
    first_token = _confirm_token(subscription)

    assert _subscribe(api_client, ip=next(ips)).status_code == 202
    assert _confirmation_messages().count() == 1  # within the hour: nothing

    _age_confirmations(subscription, timedelta(minutes=61))
    assert _subscribe(api_client, ip=next(ips)).status_code == 202
    assert _confirmation_messages().count() == 2
    subscription.refresh_from_db()
    # The first link still works: the token is kept while it is valid.
    assert _confirm_token(subscription) == first_token

    _age_confirmations(subscription, timedelta(minutes=61))
    _subscribe(api_client, ip=next(ips))
    assert _confirmation_messages().count() == 3

    subscription.refresh_from_db()
    _age_confirmations(subscription, timedelta(minutes=61))
    _subscribe(api_client, ip=next(ips))
    assert _confirmation_messages().count() == 3  # third in 24 hours was the last

    subscription.refresh_from_db()
    _age_confirmations(subscription, timedelta(hours=24))
    _subscribe(api_client, ip=next(ips))
    assert _confirmation_messages().count() == 4


@pytest.mark.django_db
def test_an_expired_pending_link_is_replaced_on_resend(api_client: APIClient) -> None:
    _subscribe(api_client)
    subscription = NewsletterSubscription.objects.get()
    old_token = _confirm_token(subscription)
    NewsletterSubscription.objects.filter(pk=subscription.pk).update(
        confirm_token_expires_at=timezone.now() - timedelta(minutes=1)
    )
    _age_confirmations(subscription, timedelta(hours=2))

    _subscribe(api_client)

    subscription.refresh_from_db()
    assert _confirm_token(subscription) != old_token
    assert api_client.post(CONFIRM, {"token": old_token}, format="json").json() == INVALID
    ok = api_client.post(CONFIRM, {"token": _confirm_token(subscription)}, format="json")
    assert ok.json() == {"status": "confirmed"}


@pytest.mark.django_db
def test_unsubscribed_address_starts_a_new_double_opt_in(api_client: APIClient) -> None:
    subscription = _confirmed("back@example.test")
    old_unsubscribe = _unsubscribe_token(subscription)
    api_client.post(UNSUBSCRIBE, {"token": old_unsubscribe}, format="json")
    subscription.refresh_from_db()
    _age_confirmations(subscription, timedelta(hours=2))
    before = _confirmation_messages().count()

    assert _subscribe(api_client, "back@example.test", source="projects").status_code == 202

    subscription.refresh_from_db()
    assert subscription.status == NewsletterSubscriptionStatus.PENDING
    assert subscription.source == "projects"
    assert subscription.confirmed_at is None and subscription.unsubscribed_at is None
    assert _confirmation_messages().count() == before + 1
    assert _unsubscribe_token(subscription) != old_unsubscribe
    confirm = api_client.post(CONFIRM, {"token": _confirm_token(subscription)}, format="json")
    assert confirm.json() == {"status": "confirmed"}


# --- Confirm and unsubscribe --------------------------------------------------------------


@pytest.mark.django_db
def test_confirm_is_idempotent_and_refuses_bad_or_expired_links(api_client: APIClient) -> None:
    _subscribe(api_client)
    subscription = NewsletterSubscription.objects.get()
    token = _confirm_token(subscription)

    for _ in range(2):
        response = api_client.post(CONFIRM, {"token": token}, format="json")
        assert response.status_code == 200
        assert response.json() == {"status": "confirmed"}
    subscription.refresh_from_db()
    assert subscription.status == NewsletterSubscriptionStatus.CONFIRMED
    assert subscription.confirmed_at is not None

    for bad in [{"token": "x" * 43}, {"token": "short"}, {"token": "<script>"}, {}]:
        response = api_client.post(CONFIRM, bad, format="json")
        assert response.status_code == 400
        assert response.json() == INVALID
    # The unsubscribe token is not a confirm token.
    wrong = api_client.post(CONFIRM, {"token": _unsubscribe_token(subscription)}, format="json")
    assert wrong.json() == INVALID


@pytest.mark.django_db
def test_an_expired_confirm_link_fails(api_client: APIClient) -> None:
    _subscribe(api_client)
    subscription = NewsletterSubscription.objects.get()
    NewsletterSubscription.objects.filter(pk=subscription.pk).update(
        confirm_token_expires_at=timezone.now() - timedelta(seconds=1)
    )

    response = api_client.post(CONFIRM, {"token": _confirm_token(subscription)}, format="json")

    assert response.status_code == 400
    assert response.json() == INVALID
    subscription.refresh_from_db()
    assert subscription.status == NewsletterSubscriptionStatus.PENDING


@pytest.mark.django_db
def test_unsubscribe_is_idempotent(api_client: APIClient) -> None:
    subscription = _confirmed()
    token = _unsubscribe_token(subscription)

    for _ in range(2):
        response = api_client.post(UNSUBSCRIBE, {"token": token}, format="json")
        assert response.status_code == 200
        assert response.json() == {"status": "unsubscribed"}
    subscription.refresh_from_db()
    assert subscription.status == NewsletterSubscriptionStatus.UNSUBSCRIBED
    first_time = subscription.unsubscribed_at
    api_client.post(UNSUBSCRIBE, {"token": token}, format="json")
    subscription.refresh_from_db()
    assert subscription.unsubscribed_at == first_time
    assert subscription.confirm_token_hash == ""
    bad = api_client.post(UNSUBSCRIBE, {"token": "y" * 43}, format="json")
    assert bad.status_code == 400 and bad.json() == INVALID


@pytest.mark.django_db
def test_one_click_unsubscribe_post_with_query_token(api_client: APIClient) -> None:
    subscription = _confirmed()
    token = _unsubscribe_token(subscription)
    url = f"{UNSUBSCRIBE}?token={urllib.parse.quote(token)}"

    response = api_client.post(
        url,
        "List-Unsubscribe=One-Click",
        content_type="application/x-www-form-urlencoded",
    )

    assert response.status_code == 200
    assert response.json() == {"status": "unsubscribed"}
    subscription.refresh_from_db()
    assert subscription.status == NewsletterSubscriptionStatus.UNSUBSCRIBED
    # The multipart variant of RFC 8058 works as well, and repeating it is fine.
    again = api_client.post(url, {"List-Unsubscribe": "One-Click"}, format="multipart")
    assert again.status_code == 200
    assert api_client.get(url).status_code == 405


@pytest.mark.django_db
def test_a_pending_subscriber_can_unsubscribe_from_the_confirmation_email(
    api_client: APIClient,
) -> None:
    _subscribe(api_client)
    subscription = NewsletterSubscription.objects.get()

    response = api_client.post(
        UNSUBSCRIBE, {"token": _unsubscribe_token(subscription)}, format="json"
    )

    assert response.json() == {"status": "unsubscribed"}
    confirm = api_client.post(CONFIRM, {"token": _confirm_token(subscription)}, format="json")
    assert confirm.json() == INVALID


# --- Throttles ----------------------------------------------------------------------------

NEWSLETTER_THROTTLED = {"detail": "Too many requests. Please try again later.", "code": "throttled"}


@pytest.mark.django_db
def test_subscribe_five_per_ip_per_hour(
    api_client: APIClient, throttle_clock: ThrottleClock
) -> None:
    for index in range(5):
        assert _subscribe(api_client, f"h{index}@example.test").status_code == 202

    refused = _subscribe(api_client, "h6@example.test")
    assert refused.status_code == 429
    assert refused.json() == NEWSLETTER_THROTTLED
    assert int(refused["Retry-After"]) > 0
    assert not NewsletterSubscription.objects.filter(email="h6@example.test").exists()
    assert _subscribe(api_client, "h6@example.test", ip="198.51.100.1").status_code == 202
    throttle_clock.advance(60 * 60)
    assert _subscribe(api_client, "h7@example.test").status_code == 202


@pytest.mark.django_db
def test_subscribe_twenty_per_ip_per_day(
    api_client: APIClient, throttle_clock: ThrottleClock
) -> None:
    sent = 0
    for _hour in range(5):
        for _ in range(5):
            response = _subscribe(api_client, f"day{sent}@example.test")
            assert response.status_code == (202 if sent < 20 else 429), sent
            sent += 1
        throttle_clock.advance(60 * 60)

    assert NewsletterSubscription.objects.count() == 20


@pytest.mark.django_db
@override_settings(NEWSLETTER_CONFIRMATION_GLOBAL_DAILY_LIMIT=2)
def test_global_confirmation_email_cap_applies_to_every_address(api_client: APIClient) -> None:
    _confirmed("already@example.test")  # one confirmation email used
    assert _subscribe(api_client, "one@example.test", ip="10.2.0.1").status_code == 202

    # The cap is reached: every address gets the same 429, subscribed or not.
    for email, ip in [("two@example.test", "10.2.0.2"), ("already@example.test", "10.2.0.3")]:
        refused = _subscribe(api_client, email, ip=ip)
        assert refused.status_code == 429
        assert refused.json() == NEWSLETTER_THROTTLED
    assert not NewsletterSubscription.objects.filter(email="two@example.test").exists()
    assert _confirmation_messages().count() == 2


@pytest.mark.django_db
@override_settings(NEWSLETTER_CONFIRMATION_GLOBAL_DAILY_LIMIT=2)
def test_requests_that_send_no_confirmation_do_not_use_the_global_cap(
    api_client: APIClient,
) -> None:
    _subscribe(api_client, "pending@example.test", ip="10.3.0.1")
    for index in range(4):  # pending within the hour: no email sent
        assert (
            _subscribe(api_client, "pending@example.test", ip=f"10.3.1.{index}").status_code == 202
        )

    assert _subscribe(api_client, "second@example.test", ip="10.3.0.2").status_code == 202
    assert _confirmation_messages().count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize("url", [CONFIRM, UNSUBSCRIBE])
def test_confirm_and_unsubscribe_thirty_per_ip_per_hour(
    api_client: APIClient, throttle_clock: ThrottleClock, url: str
) -> None:
    for _ in range(30):
        response = api_client.post(url, {"token": "z" * 43}, format="json", REMOTE_ADDR="10.9.9.9")
        assert response.status_code == 400

    refused = api_client.post(url, {"token": "z" * 43}, format="json", REMOTE_ADDR="10.9.9.9")
    assert refused.status_code == 429
    assert refused.json()["code"] == "throttled"
    throttle_clock.advance(60 * 60)
    assert (
        api_client.post(url, {"token": "z" * 43}, format="json", REMOTE_ADDR="10.9.9.9").status_code
        == 400
    )


def test_default_newsletter_limits_match_the_brief(settings: Any) -> None:
    assert settings.NEWSLETTER_SUBSCRIBE_IP_HOURLY_LIMIT == 5
    assert settings.NEWSLETTER_SUBSCRIBE_IP_DAILY_LIMIT == 20
    assert settings.NEWSLETTER_CONFIRMATION_GLOBAL_DAILY_LIMIT == 500
    assert settings.NEWSLETTER_TOKEN_IP_HOURLY_LIMIT == 30


# --- Confirmation email -------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(PUBLIC_APP_BASE_URL=BASE_URL, COMMUNICATIONS_EMAIL_PROVIDER="mock")
def test_confirmation_email_content_and_redacted_record(api_client: APIClient) -> None:
    _subscribe(api_client)
    subscription = NewsletterSubscription.objects.get()
    confirm_token = _confirm_token(subscription)
    unsubscribe_token = _unsubscribe_token(subscription)

    rendered = render_newsletter_email(_confirmation_messages().get(), redact=False)

    confirm_url = f"{BASE_URL}/newsletter/confirm?token={confirm_token}"
    unsubscribe_url = f"{BASE_URL}/newsletter/unsubscribe?token={unsubscribe_token}"
    assert rendered.recipient_email == "reader@example.test"
    assert rendered.subject == "Confirm your email address"
    html = rendered.body_html
    assert "Confirm your email address" in html
    assert "Confirm my subscription" in html
    assert f'href="{confirm_url}"' in html
    assert (
        "You asked to get new projects by email. Once or twice a month, when new projects open. "
        "If you did not ask for this, ignore this email."
    ) in html
    assert unsubscribe_url in html
    assert "brand/banxum-email-logo.png" in html
    # Not an account email: the account-holder footer is replaced.
    assert "hold an active account" not in html
    assert confirm_url in rendered.body_text and unsubscribe_url in rendered.body_text

    assert dispatch_due_email_outbox_messages().sent_count == 1
    record = EmailDeliveryRecord.objects.get()
    assert record.topic == NEWSLETTER_CONFIRMATION_EMAIL_TOPIC
    assert record.recipient_email == "reader@example.test"
    for token in (confirm_token, unsubscribe_token):
        assert token not in record.body_html and token not in record.body_text
    assert f"token={REDACTED_SECRET}" in record.body_text or "token=%5B" in record.body_text


@pytest.mark.django_db
@override_settings(PUBLIC_APP_BASE_URL=BASE_URL, COMMUNICATIONS_EMAIL_PROVIDER="mock")
def test_confirmation_is_not_sent_once_the_address_left(api_client: APIClient) -> None:
    _subscribe(api_client)
    subscription = NewsletterSubscription.objects.get()
    api_client.post(UNSUBSCRIBE, {"token": _unsubscribe_token(subscription)}, format="json")

    result = dispatch_due_email_outbox_messages()

    assert result.sent_count == 0 and result.failed_count == 0
    assert EmailDeliveryRecord.objects.count() == 0
    assert _confirmation_messages().get().status == OutboxStatus.PROCESSED


@pytest.mark.django_db
def test_newsletter_emails_stay_out_of_the_investor_notification_centre(
    api_client: APIClient,
) -> None:
    _subscribe(api_client)

    message = _confirmation_messages().get()

    assert not message.topic.startswith("email.")
    assert "email" not in message.payload and "user_id" not in message.payload


# --- New-projects digest ------------------------------------------------------------------


def _admin() -> Model:
    return cast(
        Model,
        get_user_model().objects.create_user(
            email="newsletter-admin@example.test",
            full_name="Newsletter Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


def _published_loan(
    *,
    title: str,
    published_at: datetime,
    status: str = "published",
    principal_minor: int = 100_000_00,
    committed_minor: int = 0,
    funding_deadline: date | None = None,
    interest_rate_bps: int = 1000,
    term_months: int = 12,
    currency_code: str = "CHF",
) -> Model:
    admin = get_user_model().objects.filter(is_staff=True).first() or _admin()
    borrower = apps.get_model("entities", "BorrowerEntity").objects.create(
        legal_name=BORROWER_NAME,
        year_founded=2010,
        entity_type="swiss_company",
        kyb_status="approved",
        country="CH",
        created_by_admin_id=admin.pk,
    )
    deadline = funding_deadline or (published_at + timedelta(days=30)).date()
    return cast(
        Model,
        apps.get_model("loans", "Loan").objects.create(
            borrower=borrower,
            status=status,
            title=title,
            investor_summary="Summary.",
            purpose="bridge_financing",
            original_principal_minor=principal_minor,
            principal_minor=principal_minor,
            committed_principal_minor=committed_minor,
            currency=Currency.objects.get(code=currency_code),
            interest_rate_bps=interest_rate_bps,
            term_months=term_months,
            repayment_type="equal_installments",
            loan_start_date=deadline,
            funding_deadline=deadline,
            first_payment_date=date(2031, 2, 10),
            collateral_type="real_estate",
            collateral_value_minor=150_000_00,
            risk_rating="BBB",
            borrower_success_fee_bps=200,
            total_scheduled_principal_minor=principal_minor,
            total_scheduled_interest_minor=5_000_00,
            created_by_admin_id=admin.pk,
            published_at=published_at,
        ),
    )


def _pending(email: str) -> NewsletterSubscription:
    APIClient().post(SUBSCRIBE, {"email": email, "source": "home"}, format="json")
    return NewsletterSubscription.objects.get(email=email)


def _day(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 10, day, hour, 0, tzinfo=ZURICH)


def _digest_messages() -> Any:
    return OutboxMessage.objects.filter(topic=NEWSLETTER_NEW_PROJECTS_EMAIL_TOPIC)


@pytest.mark.django_db
def test_no_new_projects_means_no_email() -> None:
    _confirmed()
    _published_loan(title="Old project", published_at=_day(1))

    result = run_newsletter_new_projects_digest(as_of=_day(10))

    assert result.project_count == 0
    assert result.queued_count == 0
    assert _digest_messages().count() == 0
    run = NewsletterDigestRun.objects.get()
    assert run.status == NewsletterDigestRunStatus.COMPLETED
    assert run.window_start == _day(9)  # the first run looks back one day


@pytest.mark.django_db
@override_settings(PUBLIC_APP_BASE_URL=BASE_URL, COMMUNICATIONS_EMAIL_PROVIDER="mock")
def test_new_projects_send_one_email_per_confirmed_subscriber_only() -> None:
    first = _confirmed("first@example.test")
    second = _confirmed("second@example.test")
    _pending("pending@example.test")
    gone = _confirmed("gone@example.test")
    APIClient().post(UNSUBSCRIBE, {"token": _unsubscribe_token(gone)}, format="json")
    run_newsletter_new_projects_digest(as_of=_day(10))  # first run: nothing new
    loan_a = _published_loan(title="Hotel renovation Lucerne", published_at=_day(10, 15))
    loan_b = _published_loan(
        title="Machines for a bakery",
        published_at=_day(11, 9),
        interest_rate_bps=850,
        term_months=1,
        currency_code="EUR",
    )
    _published_loan(title="Draft", published_at=_day(10, 16), status="draft")
    _published_loan(title="Full already", published_at=_day(10, 17), committed_minor=100_000_00)
    _published_loan(
        title="Too late", published_at=_day(10, 18), funding_deadline=date(2026, 10, 10)
    )

    result = run_newsletter_new_projects_digest(as_of=_day(11))

    assert result.project_count == 2
    assert result.queued_count == 2
    messages = list(_digest_messages())
    assert {message.payload["subscription_id"] for message in messages} == {
        str(first.id),
        str(second.id),
    }
    run = NewsletterDigestRun.objects.get(run_date=date(2026, 10, 11))
    assert [project["loan_id"] for project in run.projects] == [str(loan_a.pk), str(loan_b.pk)]
    assert run.recipient_count == 2
    assert NewsletterDigestDelivery.objects.filter(run=run).count() == 2

    rendered = render_newsletter_email(messages[0], redact=False)
    assert rendered.subject == "2 new projects are open on BANXUM"
    html = rendered.body_html
    assert "Hotel renovation Lucerne" in html and "Machines for a bakery" in html
    assert "10.00% a year · 12 months · CHF" in html
    assert "8.50% a year · 1 month · EUR" in html
    assert f'href="{BASE_URL}/projects/{loan_a.pk}"' in html
    assert BORROWER_NAME not in html and BORROWER_NAME not in rendered.body_text
    for title in ("Draft", "Full already", "Too late"):
        assert title not in html
    subscriber = NewsletterSubscription.objects.get(id=messages[0].payload["subscription_id"])
    token = _unsubscribe_token(subscriber)
    assert f"{BASE_URL}/newsletter/unsubscribe?token={token}" in html
    headers = dict(rendered.headers)
    assert headers["List-Unsubscribe"] == f"<{BASE_URL}{UNSUBSCRIBE}?token={token}>"
    assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"

    dispatch_due_email_outbox_messages()
    records = EmailDeliveryRecord.objects.filter(topic=NEWSLETTER_NEW_PROJECTS_EMAIL_TOPIC)
    assert sorted(record.recipient_email for record in records) == [
        "first@example.test",
        "second@example.test",
    ]
    for record in records:
        assert token not in record.body_html and token not in record.body_text


@pytest.mark.django_db
def test_digest_is_not_sent_twice() -> None:
    _confirmed()
    run_newsletter_new_projects_digest(as_of=_day(10))
    _published_loan(title="Once only", published_at=_day(10, 14))

    first = run_newsletter_new_projects_digest(as_of=_day(11))
    again = run_newsletter_new_projects_digest(as_of=_day(11, 18))
    next_day = run_newsletter_new_projects_digest(as_of=_day(12))

    assert first.queued_count == 1
    assert again.already_completed is True and again.queued_count == 0
    assert next_day.project_count == 0
    assert _digest_messages().count() == 1


@pytest.mark.django_db
def test_an_interrupted_run_is_finished_without_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _confirmed("a@example.test")
    _confirmed("b@example.test")
    run_newsletter_new_projects_digest(as_of=_day(10))
    _published_loan(title="Resumed", published_at=_day(10, 14))
    from backend.apps.communications import newsletter

    real_queue = newsletter._queue_digest_email
    calls = {"count": 0}

    def crash_after_first(run: NewsletterDigestRun, subscription_id: Any) -> bool:
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("worker killed")
        return real_queue(run, subscription_id)

    monkeypatch.setattr(newsletter, "_queue_digest_email", crash_after_first)
    with pytest.raises(RuntimeError):
        run_newsletter_new_projects_digest(as_of=_day(11))
    monkeypatch.setattr(newsletter, "_queue_digest_email", real_queue)
    assert _digest_messages().count() == 1
    assert _digest_messages().get().payload["subscription_id"] == str(first.id)

    result = run_newsletter_new_projects_digest(as_of=_day(12))

    assert result.resumed_run_dates == (date(2026, 10, 11),)
    assert _digest_messages().count() == 2
    run = NewsletterDigestRun.objects.get(run_date=date(2026, 10, 11))
    assert run.status == NewsletterDigestRunStatus.COMPLETED
    assert run.recipient_count == 2


@pytest.mark.django_db
@override_settings(PUBLIC_APP_BASE_URL=BASE_URL, COMMUNICATIONS_EMAIL_PROVIDER="mock")
def test_digest_queued_before_unsubscribing_is_not_sent() -> None:
    subscription = _confirmed()
    run_newsletter_new_projects_digest(as_of=_day(10))
    _published_loan(title="Left before sending", published_at=_day(10, 14))
    run_newsletter_new_projects_digest(as_of=_day(11))
    APIClient().post(UNSUBSCRIBE, {"token": _unsubscribe_token(subscription)}, format="json")

    dispatch_due_email_outbox_messages()

    assert not EmailDeliveryRecord.objects.filter(
        topic=NEWSLETTER_NEW_PROJECTS_EMAIL_TOPIC
    ).exists()
    assert _digest_messages().get().status == OutboxStatus.PROCESSED


class _FakeSendGridResponse:
    status = 202
    headers = {"X-Message-Id": "sendgrid-1"}

    def __enter__(self) -> _FakeSendGridResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


@pytest.mark.django_db
def test_sendgrid_gets_the_one_click_unsubscribe_headers(
    monkeypatch: pytest.MonkeyPatch, settings: Any
) -> None:
    settings.PUBLIC_APP_BASE_URL = BASE_URL
    settings.COMMUNICATIONS_EMAIL_PROVIDER = "mock"
    subscription = _confirmed()
    run_newsletter_new_projects_digest(as_of=_day(10))
    _published_loan(title="Header check", published_at=_day(10, 14))
    run_newsletter_new_projects_digest(as_of=_day(11))
    OutboxMessage.objects.filter(topic=NEWSLETTER_CONFIRMATION_EMAIL_TOPIC).update(
        status=OutboxStatus.PROCESSED
    )
    settings.COMMUNICATIONS_EMAIL_PROVIDER = "sendgrid"
    settings.SENDGRID_API_KEY = "SG.test"
    settings.SENDGRID_FROM_EMAIL = "notifications@banxum.test"
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: int) -> _FakeSendGridResponse:
        captured["payload"] = json.loads(cast(bytes, request.data).decode("utf-8"))
        return _FakeSendGridResponse()

    monkeypatch.setattr("backend.apps.communications.services.urllib.request.urlopen", fake_urlopen)

    assert dispatch_due_email_outbox_messages().sent_count == 1

    token = _unsubscribe_token(subscription)
    assert captured["payload"]["headers"] == {
        "List-Unsubscribe": f"<{BASE_URL}{UNSUBSCRIBE}?token={token}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    assert "reply_to" not in captured["payload"]


@pytest.mark.django_db
def test_digest_runs_as_a_daily_scheduled_job_with_evidence() -> None:
    _confirmed()
    run_newsletter_new_projects_digest(as_of=_day(10))
    _published_loan(title="Scheduled", published_at=_day(10, 14))
    assert NEWSLETTER_NEW_PROJECTS_JOB in DEFAULT_SCHEDULED_JOB_NAMES
    assert PUBLIC_SITE_RETENTION_JOB in DEFAULT_SCHEDULED_JOB_NAMES

    # No admin actor is needed for these system jobs.
    command = RunScheduledJobsCommand(
        job_names=(NEWSLETTER_NEW_PROJECTS_JOB, PUBLIC_SITE_RETENTION_JOB), as_of=_day(11)
    )
    first = run_scheduled_jobs(command)
    second = run_scheduled_jobs(command)

    assert [result.status for result in first.results] == [ScheduledJobRunStatus.SUCCEEDED] * 2
    assert first.results[0].run_key == f"{NEWSLETTER_NEW_PROJECTS_JOB}:2026-10-11"
    assert first.results[0].summary["queued_count"] == 1
    assert [result.status for result in second.results] == [ScheduledJobRunStatus.SKIPPED] * 2
    run = ScheduledJobRun.objects.get(job_name=NEWSLETTER_NEW_PROJECTS_JOB)
    assert run.actor_user_id is None
    assert _digest_messages().count() == 1


# --- Retention ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_enquiries_are_deleted_after_24_months() -> None:
    old = PublicEnquiry.objects.create(
        kind="contact", reference="MSG-2024-0001", sender_email="old@example.test"
    )
    recent = PublicEnquiry.objects.create(
        kind="contact", reference="MSG-2024-0002", sender_email="new@example.test"
    )
    as_of = datetime(2026, 10, 15, 12, 0, tzinfo=ZURICH)
    PublicEnquiry.objects.filter(pk=old.pk).update(created_at=as_of - timedelta(days=731))
    PublicEnquiry.objects.filter(pk=recent.pk).update(created_at=as_of - timedelta(days=729))

    assert delete_expired_public_enquiries(as_of=as_of) == 1

    assert list(PublicEnquiry.objects.values_list("reference", flat=True)) == ["MSG-2024-0002"]


@pytest.mark.django_db
def test_unsubscribed_rows_are_anonymised_after_30_days(api_client: APIClient) -> None:
    old = _confirmed("old@example.test")
    recent = _confirmed("recent@example.test")
    kept = _confirmed("kept@example.test")
    for subscription in (old, recent):
        api_client.post(UNSUBSCRIBE, {"token": _unsubscribe_token(subscription)}, format="json")
    as_of = timezone.now()
    NewsletterSubscription.objects.filter(pk=old.pk).update(
        unsubscribed_at=as_of - timedelta(days=31)
    )
    NewsletterSubscription.objects.filter(pk=recent.pk).update(
        unsubscribed_at=as_of - timedelta(days=29)
    )
    old_token = _unsubscribe_token(old)

    result = anonymise_old_newsletter_subscriptions(as_of=as_of)

    assert result == {"unsubscribed_anonymised": 1, "unconfirmed_anonymised": 0}
    old.refresh_from_db()
    assert old.email is None and old.ip_hash == "" and old.anonymised_at is not None
    assert old.unsubscribe_token_nonce == "" and old.confirm_token_hash == ""
    recent.refresh_from_db()
    kept.refresh_from_db()
    assert recent.email == "recent@example.test" and kept.email == "kept@example.test"
    # A late click on an old link still answers "unsubscribed".
    late = api_client.post(UNSUBSCRIBE, {"token": old_token}, format="json")
    assert late.json() == {"status": "unsubscribed"}
    # The address may subscribe again from scratch.
    assert _subscribe(api_client, "old@example.test").status_code == 202
    assert NewsletterSubscription.objects.filter(email="old@example.test").count() == 1
    assert anonymise_old_newsletter_subscriptions(as_of=as_of)["unsubscribed_anonymised"] == 0


@pytest.mark.django_db
def test_never_confirmed_rows_are_anonymised_30_days_after_the_link_expired(
    api_client: APIClient,
) -> None:
    stale = _pending("stale@example.test")
    fresh = _pending("fresh@example.test")
    as_of = timezone.now()
    NewsletterSubscription.objects.filter(pk=stale.pk).update(
        confirm_token_expires_at=as_of - timedelta(days=31)
    )

    result = anonymise_old_newsletter_subscriptions(as_of=as_of)

    assert result["unconfirmed_anonymised"] == 1
    stale.refresh_from_db()
    fresh.refresh_from_db()
    assert stale.email is None and stale.unsubscribe_token_hash == ""
    assert fresh.email == "fresh@example.test"


@pytest.mark.django_db
def test_retention_job_summary() -> None:
    result = run_scheduled_jobs(
        RunScheduledJobsCommand(job_names=(PUBLIC_SITE_RETENTION_JOB,), as_of=_day(15))
    ).results[0]

    assert result.status == ScheduledJobRunStatus.SUCCEEDED
    assert result.summary["enquiries_deleted"] == 0
    assert result.summary["unsubscribed_anonymised"] == 0


@pytest.mark.django_db
def test_a_server_key_change_renews_the_link_hash_instead_of_failing(
    settings: Any, caplog: pytest.LogCaptureFixture
) -> None:
    settings.PUBLIC_APP_BASE_URL = BASE_URL
    subscription = _confirmed()
    run_newsletter_new_projects_digest(as_of=_day(10))
    _published_loan(title="After rotation", published_at=_day(10, 14))
    run_newsletter_new_projects_digest(as_of=_day(11))
    settings.SECRET_KEY = "rotated-secret-key-for-the-test-only-0123456789"

    rendered = render_newsletter_email(_digest_messages().get(), redact=False)

    subscription.refresh_from_db()
    new_token = _unsubscribe_token(subscription)
    assert subscription.unsubscribe_token_hash == token_hash(new_token)
    assert f"token={new_token}" in rendered.body_text
    assert any("server key change" in record.getMessage() for record in caplog.records)
    response = APIClient().post(UNSUBSCRIBE, {"token": new_token}, format="json")
    assert response.json() == {"status": "unsubscribed"}
