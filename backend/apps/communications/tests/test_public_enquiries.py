"""Public site forms: validation, abuse guards, references and the one email to BANXUM."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from backend.apps.communications.models import (
    EmailDeliveryRecord,
    PublicEnquiry,
    PublicEnquiryDeliveryStatus,
    PublicEnquiryReferenceCounter,
)
from backend.apps.communications.public_forms import (
    allocate_public_enquiry_reference,
    public_ip_hash,
    render_public_enquiry_email,
)
from backend.apps.communications.services import (
    PUBLIC_ENQUIRY_EMAIL_TOPIC,
    REDACTED_SECRET,
    dispatch_due_email_outbox_messages,
)
from backend.apps.communications.tests.conftest import ThrottleClock
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.models.events import OutboxStatus

URL = "/api/v1/public/enquiries/"
YEAR = business_date(now_utc()).year
HQ = "enquiries@banxum.test"

COMPANY_FIELDS: dict[str, Any] = {
    "company_name": "Muster Bau AG",
    "country": "Switzerland",
    "company_number": "CHE-123.456.789",
    "amount": "250,000.00",
    "term": "24 months",
    "purpose": "Real estate",
    "security": "Mortgage note",
    "revenue": "1'200'000",
    "founded": "1998",
    "about": "Family firm since 1998.\nSecond line.",
    "contact_name": "Anna Muster",
    "role": "CFO",
    "email": "Anna.Muster@Example.test",
    "phone": "+41 44 123 45 67",
}
ORIGINATOR_FIELDS: dict[str, Any] = {
    "company_name": "Lease Partner GmbH",
    "country": "Germany",
    "licence": "BaFin 32 KWG",
    "product": "Invoices (factoring)",
    "loan_book": "12000000",
    "contact_name": "Max Mustermann",
    "email": "max@example.test",
}
CONTACT_FIELDS: dict[str, Any] = {
    "name": "Eva Example",
    "email": "eva@example.test",
    "topic": "Press",
    "message": "Hello, a question about BANXUM.",
}
FIELDS_BY_KIND = {
    "company": COMPANY_FIELDS,
    "originator": ORIGINATOR_FIELDS,
    "contact": CONTACT_FIELDS,
}
PREFIX_BY_KIND = {"company": "APP", "originator": "PAR", "contact": "MSG"}


def _body(kind: str = "contact", **field_overrides: Any) -> dict[str, Any]:
    fields = {**FIELDS_BY_KIND[kind], **field_overrides}
    return {"kind": kind, "fields": fields, "consent": True, "elapsed_ms": 9000, "website": ""}


def _post(
    client: APIClient, body: dict[str, Any], *, ip: str = "203.0.113.10", **extra: Any
) -> Any:
    return client.post(URL, body, format="json", REMOTE_ADDR=ip, **extra)


def _field_errors(response: Any) -> dict[str, Any]:
    assert response.status_code == 400, response.content
    return cast(dict[str, Any], response.json()["fields"])


# --- Happy path ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["company", "originator", "contact"])
def test_each_form_is_stored_and_queues_one_email(api_client: APIClient, kind: str) -> None:
    response = _post(api_client, _body(kind), HTTP_USER_AGENT="Mozilla/5.0 " + "x" * 400)

    assert response.status_code == 201, response.content
    reference = response.json()["reference"]
    assert reference == f"{PREFIX_BY_KIND[kind]}-{YEAR}-0001"
    enquiry = PublicEnquiry.objects.get()
    assert enquiry.kind == kind
    assert enquiry.reference == reference
    assert enquiry.sender_email == FIELDS_BY_KIND[kind]["email"].lower()
    assert enquiry.ip_hash == public_ip_hash("203.0.113.10")
    assert "203.0.113.10" not in json.dumps(enquiry.payload)
    assert len(enquiry.user_agent) == 255
    assert enquiry.delivery_status == PublicEnquiryDeliveryStatus.QUEUED
    message = OutboxMessage.objects.get()
    assert message.topic == PUBLIC_ENQUIRY_EMAIL_TOPIC
    assert enquiry.outbox_message_id == message.id
    # The queue holds references only, never the person's details.
    assert set(message.payload) == {"enquiry_id", "reference", "kind", "template_key"}


@pytest.mark.django_db
def test_values_are_trimmed_normalised_and_unknown_keys_dropped(api_client: APIClient) -> None:
    response = _post(
        api_client,
        _body(
            "company",
            company_name="  Muster\tBau\nAG  ",
            amount=" 250,000.00 ",
            revenue="",
            country=" Switzerland ",
            unexpected="dropped",
        ),
    )

    assert response.status_code == 201, response.content
    fields = PublicEnquiry.objects.get().payload["fields"]
    assert fields["company_name"] == "Muster Bau AG"
    assert fields["amount"] == "250000.00"
    assert fields["revenue"] == ""
    assert fields["country"] == "Switzerland"
    assert "unexpected" not in fields


@pytest.mark.django_db
def test_free_text_keeps_line_breaks_but_loses_other_control_characters(
    api_client: APIClient,
) -> None:
    message = "Line one\r\nLine\x00 two\x07‮\tend\x1b[31m"
    response = _post(api_client, _body("contact", message=message))

    assert response.status_code == 201, response.content
    stored = PublicEnquiry.objects.get().payload["fields"]["message"]
    assert stored == "Line one\nLine two end[31m"


# --- References ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_references_count_up_per_prefix_and_year() -> None:
    assert allocate_public_enquiry_reference("company") == f"APP-{YEAR}-0001"
    assert allocate_public_enquiry_reference("company") == f"APP-{YEAR}-0002"
    assert allocate_public_enquiry_reference("originator") == f"PAR-{YEAR}-0001"
    assert allocate_public_enquiry_reference("contact") == f"MSG-{YEAR}-0001"
    PublicEnquiryReferenceCounter.objects.filter(prefix="MSG").update(last_number=9999)
    assert allocate_public_enquiry_reference("contact") == f"MSG-{YEAR}-10000"
    counter = PublicEnquiryReferenceCounter.objects.get(prefix="APP", year=YEAR)
    assert counter.last_number == 2


@pytest.mark.django_db
def test_references_stay_unique_after_enquiries_are_deleted(api_client: APIClient) -> None:
    first = _post(api_client, _body("contact")).json()["reference"]
    PublicEnquiry.objects.all().delete()
    second = _post(api_client, _body("contact"), ip="203.0.113.11").json()["reference"]

    assert first == f"MSG-{YEAR}-0001"
    assert second == f"MSG-{YEAR}-0002"


# --- Validation ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("kind", "required"),
    [
        (
            "company",
            [
                "company_name",
                "country",
                "company_number",
                "amount",
                "term",
                "purpose",
                "security",
                "founded",
                "contact_name",
                "role",
                "email",
                "phone",
            ],
        ),
        (
            "originator",
            ["company_name", "country", "licence", "product", "loan_book", "contact_name", "email"],
        ),
        ("contact", ["name", "email", "topic", "message"]),
    ],
)
def test_required_fields_are_reported_under_fields(
    api_client: APIClient, kind: str, required: list[str]
) -> None:
    response = _post(api_client, {"kind": kind, "fields": {}, "consent": True})

    errors = _field_errors(response)
    assert sorted(errors) == sorted(required)
    assert PublicEnquiry.objects.count() == 0
    # Blank or whitespace-only values count as missing too.
    blank = {name: "   " for name in required}
    errors = _field_errors(_post(api_client, {"kind": kind, "fields": blank, "consent": True}))
    assert sorted(errors) == sorted(required)


@pytest.mark.django_db
def test_optional_company_fields_may_be_left_out(api_client: APIClient) -> None:
    fields = {k: v for k, v in COMPANY_FIELDS.items() if k not in {"revenue", "about"}}
    response = _post(api_client, {"kind": "company", "fields": fields, "consent": True})

    assert response.status_code == 201, response.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("kind", "field", "limit"),
    [
        ("company", "company_name", 200),
        ("company", "company_number", 200),
        ("company", "role", 200),
        ("originator", "licence", 200),
        ("contact", "name", 200),
        ("company", "about", 4000),
        ("contact", "message", 4000),
    ],
)
def test_text_length_limits(api_client: APIClient, kind: str, field: str, limit: int) -> None:
    ok = _post(api_client, _body(kind, **{field: "a" * limit}), ip="203.0.113.21")
    assert ok.status_code == 201, ok.content

    too_long = _post(api_client, _body(kind, **{field: "a" * (limit + 1)}), ip="203.0.113.22")
    assert field in _field_errors(too_long)


@pytest.mark.django_db
def test_email_and_phone_limits_and_format(api_client: APIClient) -> None:
    long_email = "a" * 64 + "@" + ".".join(["b" * 60, "c" * 60, "d" * 60, "eee"]) + ".test"
    assert len(long_email) == 256
    errors = _field_errors(_post(api_client, _body("contact", email=long_email)))
    assert "email" in errors
    errors = _field_errors(_post(api_client, _body("contact", email="not-an-email")))
    assert "email" in errors
    errors = _field_errors(_post(api_client, _body("company", phone="+41 " + "1" * 40)))
    assert "phone" in errors
    errors = _field_errors(_post(api_client, _body("company", phone="call me maybe")))
    assert "phone" in errors
    errors = _field_errors(_post(api_client, _body("company", phone="123")))
    assert "phone" in errors


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("kind", "field"),
    [
        ("company", "country"),
        ("company", "term"),
        ("company", "purpose"),
        ("company", "security"),
        ("originator", "country"),
        ("originator", "product"),
        ("contact", "topic"),
    ],
)
def test_select_values_must_be_listed_options(api_client: APIClient, kind: str, field: str) -> None:
    errors = _field_errors(_post(api_client, _body(kind, **{field: "Something else"})))

    assert field in errors


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("250000", "250000.00"),
        ("250,000.00", "250000.00"),
        ("250'000.5", "250000.50"),
        ("250 000", "250000.00"),
        ("0.01", "0.01"),
        ("1,000,000,000,000", "1000000000000.00"),
    ],
)
def test_amounts_accept_grouped_or_plain_decimals(
    api_client: APIClient, raw: str, stored: str
) -> None:
    response = _post(api_client, _body("company", amount=raw))

    assert response.status_code == 201, response.content
    assert PublicEnquiry.objects.get().payload["fields"]["amount"] == stored


@pytest.mark.django_db
@pytest.mark.parametrize(
    "raw",
    [
        "0",
        "0.00",
        "-5",
        "1.234",
        "250,50",
        "250.000,00",
        "25,0000",
        "1,000'000",
        "1000000000000.01",
        "1e6",
        "abc",
        "١٢٣",
    ],
)
def test_amounts_must_be_positive_two_decimals_and_capped(api_client: APIClient, raw: str) -> None:
    errors = _field_errors(_post(api_client, _body("company", amount=raw)))
    assert "amount" in errors
    errors = _field_errors(_post(api_client, _body("company", revenue=raw)))
    assert "revenue" in errors
    errors = _field_errors(_post(api_client, _body("originator", loan_book=raw)))
    assert "loan_book" in errors


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("founded", "ok"),
    [
        ("1800", True),
        (str(YEAR), True),
        (1998, True),
        ("1799", False),
        (str(YEAR + 1), False),
        ("98", False),
        ("19a8", False),
    ],
)
def test_founded_is_a_year_from_1800_to_this_year(
    api_client: APIClient, founded: Any, ok: bool
) -> None:
    response = _post(api_client, _body("company", founded=founded))

    if ok:
        assert response.status_code == 201, response.content
    else:
        assert "founded" in _field_errors(response)


@pytest.mark.django_db
@pytest.mark.parametrize("kind,field", [("company", "about"), ("contact", "message")])
def test_at_most_five_links_in_free_text(api_client: APIClient, kind: str, field: str) -> None:
    five = "see https://a.test and http://b.test, www.c.test, HTTPS://d.test www.e.test"
    assert _post(api_client, _body(kind, **{field: five})).status_code == 201

    six = five + " and http://f.test"
    errors = _field_errors(_post(api_client, _body(kind, **{field: six}), ip="203.0.113.30"))
    assert errors[field] == ["Please remove some links."]


@pytest.mark.django_db
@pytest.mark.parametrize("consent", [False, None, "no"])
def test_consent_must_be_true(api_client: APIClient, consent: Any) -> None:
    body = _body("contact")
    if consent is None:
        del body["consent"]
    else:
        body["consent"] = consent

    response = _post(api_client, body)

    assert response.status_code == 400
    assert "consent" in response.json()
    assert PublicEnquiry.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["", "loan", None, 3])
def test_unknown_kind_is_refused(api_client: APIClient, kind: Any) -> None:
    body = _body("contact")
    body["kind"] = kind

    response = _post(api_client, body)

    assert response.status_code == 400
    assert "kind" in response.json()


@pytest.mark.django_db
def test_body_over_32_kb_is_refused(api_client: APIClient) -> None:
    body = _body("contact", message="a" * 3000)
    body["padding"] = "x" * (32 * 1024)

    response = _post(api_client, body)

    assert response.status_code == 400
    assert response.json() == {"detail": "The form is too large.", "code": "too_large"}
    assert PublicEnquiry.objects.count() == 0
    assert OutboxMessage.objects.count() == 0


# --- Honeypot and timing -------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bot_fields",
    [
        {"website": "https://spam.test"},
        {"elapsed_ms": 2999},
        {"elapsed_ms": 0},
        {"elapsed_ms": "1500"},
    ],
)
def test_bots_get_a_believable_reference_and_nothing_happens(
    api_client: APIClient, caplog: pytest.LogCaptureFixture, bot_fields: dict[str, Any]
) -> None:
    allocate_public_enquiry_reference("company")  # real counter at APP-YEAR-0001
    body = {**_body("company"), **bot_fields}

    with caplog.at_level(logging.INFO, logger="backend.apps.communications.api.views"):
        response = _post(api_client, body)

    assert response.status_code == 201
    reference = response.json()["reference"]
    assert re.fullmatch(rf"APP-{YEAR}-000[2-4]", reference)
    assert PublicEnquiry.objects.count() == 0
    assert OutboxMessage.objects.count() == 0
    assert PublicEnquiryReferenceCounter.objects.get(prefix="APP").last_number == 1
    assert any("automated" in record.getMessage() for record in caplog.records)
    assert all(record.levelno == logging.INFO for record in caplog.records)


@pytest.mark.django_db
def test_bot_with_invalid_fields_still_gets_a_reference(api_client: APIClient) -> None:
    response = _post(api_client, {"kind": "contact", "fields": {}, "website": "x"})

    assert response.status_code == 201
    assert response.json()["reference"].startswith(f"MSG-{YEAR}-")
    assert PublicEnquiry.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("elapsed_ms", [3000, 60_000, None])
def test_humans_taking_three_seconds_or_more_are_accepted(
    api_client: APIClient, elapsed_ms: int | None
) -> None:
    body = _body("contact")
    if elapsed_ms is None:
        del body["elapsed_ms"]
    else:
        body["elapsed_ms"] = elapsed_ms

    assert _post(api_client, body).status_code == 201
    assert PublicEnquiry.objects.count() == 1


# --- Throttles ----------------------------------------------------------------------------

THROTTLED = {
    "detail": "Too many messages. Please try again later or write to us by email.",
    "code": "throttled",
}


@pytest.mark.django_db
def test_three_messages_per_ip_per_ten_minutes(
    api_client: APIClient, throttle_clock: ThrottleClock
) -> None:
    for index in range(3):
        response = _post(api_client, _body("contact", email=f"p{index}@example.test"))
        assert response.status_code == 201, response.content

    refused = _post(api_client, _body("contact", email="p4@example.test"))
    assert refused.status_code == 429
    assert refused.json() == THROTTLED
    assert int(refused["Retry-After"]) > 0
    assert PublicEnquiry.objects.count() == 3
    # Another IP is not affected; the same IP may send again in the next window.
    assert _post(api_client, _body("contact"), ip="198.51.100.7").status_code == 201
    throttle_clock.advance(10 * 60)
    assert _post(api_client, _body("contact", email="p5@example.test")).status_code == 201


@pytest.mark.django_db
def test_ten_messages_per_ip_per_day(api_client: APIClient, throttle_clock: ThrottleClock) -> None:
    sent = 0
    for _window in range(4):
        for _ in range(3):
            response = _post(api_client, _body("contact", email=f"d{sent}@example.test"))
            if sent < 10:
                assert response.status_code == 201, (sent, response.content)
            else:
                assert response.status_code == 429
                assert response.json() == THROTTLED
            sent += 1
        throttle_clock.advance(10 * 60)

    assert PublicEnquiry.objects.count() == 10
    throttle_clock.advance(24 * 60 * 60)
    assert _post(api_client, _body("contact", email="next-day@example.test")).status_code == 201


@pytest.mark.django_db
def test_three_messages_per_sender_email_per_day(api_client: APIClient) -> None:
    for index in range(3):
        response = _post(
            api_client, _body("contact", email="Same@Example.test"), ip=f"10.0.0.{index}"
        )
        assert response.status_code == 201

    refused = _post(api_client, _body("contact", email="same@example.test"), ip="10.0.0.9")
    assert refused.status_code == 429
    assert refused.json() == THROTTLED
    assert (
        _post(api_client, _body("contact", email="other@example.test"), ip="10.0.0.9").status_code
        == 201
    )


@pytest.mark.django_db
@override_settings(PUBLIC_ENQUIRY_GLOBAL_DAILY_LIMIT=4)
def test_global_daily_limit(api_client: APIClient) -> None:
    for index in range(4):
        response = _post(
            api_client, _body("contact", email=f"g{index}@example.test"), ip=f"10.1.0.{index}"
        )
        assert response.status_code == 201

    refused = _post(api_client, _body("contact", email="g9@example.test"), ip="10.1.0.9")
    assert refused.status_code == 429
    assert refused.json() == THROTTLED
    assert PublicEnquiry.objects.count() == 4


def test_default_limits_match_the_brief(settings: Any) -> None:
    assert settings.PUBLIC_ENQUIRY_IP_10_MINUTE_LIMIT == 3
    assert settings.PUBLIC_ENQUIRY_IP_DAILY_LIMIT == 10
    assert settings.PUBLIC_ENQUIRY_EMAIL_DAILY_LIMIT == 3
    assert settings.PUBLIC_ENQUIRY_GLOBAL_DAILY_LIMIT == 200
    assert settings.PUBLIC_ENQUIRY_EMAIL == "hq@banxum.com"


@pytest.mark.django_db
def test_rejected_forms_do_not_use_up_the_ip_budget(api_client: APIClient) -> None:
    for _ in range(5):
        assert _post(api_client, _body("contact", email="broken")).status_code == 400

    for index in range(3):
        assert (
            _post(api_client, _body("contact", email=f"ok{index}@example.test")).status_code == 201
        )


@pytest.mark.django_db
def test_bot_submissions_use_up_the_ip_budget(api_client: APIClient) -> None:
    for _ in range(3):
        assert _post(api_client, {**_body("contact"), "website": "x"}).status_code == 201

    assert _post(api_client, _body("contact")).status_code == 429
    assert PublicEnquiry.objects.count() == 0


# --- The email ----------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(
    PUBLIC_ENQUIRY_EMAIL=HQ,
    COMMUNICATIONS_EMAIL_PROVIDER="mock",
    PUBLIC_APP_BASE_URL="https://banxum.test",
)
def test_the_email_goes_to_the_setting_only_and_shows_every_field(api_client: APIClient) -> None:
    reference = _post(api_client, _body("company")).json()["reference"]
    message = OutboxMessage.objects.get()

    rendered = render_public_enquiry_email(message, redact=False)

    assert rendered.recipient_email == HQ
    assert rendered.subject == f"New company application {reference}"
    assert rendered.reply_to == "anna.muster@example.test"
    for label, value in [
        ("Company name", "Muster Bau AG"),
        ("Country", "Switzerland"),
        ("Company number", "CHE-123.456.789"),
        ("Amount", "250,000.00"),
        ("Term", "24 months"),
        ("Purpose", "Real estate"),
        ("Security", "Mortgage note"),
        ("Annual revenue", "1,200,000.00"),
        ("Founded", "1998"),
        ("Contact name", "Anna Muster"),
        ("Role", "CFO"),
        ("Email", "Anna.Muster@Example.test"),
        ("Phone", "+41 44 123 45 67"),
    ]:
        assert label in rendered.body_html
        assert value in rendered.body_html
        assert f"{label}: {value}" in rendered.body_text
    assert "Family firm since 1998.<br>Second line." in rendered.body_html
    assert "About the company:\n  Family firm since 1998.\n  Second line." in rendered.body_text
    assert "<!DOCTYPE html>" in rendered.body_html
    assert "brand/banxum-email-logo.png" in rendered.body_html

    result = dispatch_due_email_outbox_messages()

    assert result.sent_count == 1
    record = EmailDeliveryRecord.objects.get()
    assert record.recipient_email == HQ
    assert record.subject == f"New company application {reference}"
    # Exactly one email, and never one to the person who filled the form.
    assert EmailDeliveryRecord.objects.filter(recipient_email__icontains="muster").count() == 0
    assert OutboxMessage.objects.count() == 1
    enquiry = PublicEnquiry.objects.get()
    assert enquiry.delivery_status == PublicEnquiryDeliveryStatus.SENT


@pytest.mark.django_db
@override_settings(PUBLIC_ENQUIRY_EMAIL=HQ, PUBLIC_APP_BASE_URL="https://banxum.test")
@pytest.mark.parametrize(
    ("kind", "subject"),
    [
        ("company", "New company application"),
        ("originator", "New loan originator request"),
        ("contact", "New contact message"),
    ],
)
def test_subject_is_fixed_text_and_reference_only(
    api_client: APIClient, kind: str, subject: str
) -> None:
    hostile = "Evil\r\nBcc: victim@example.test"
    name_field = "name" if kind == "contact" else "company_name"
    reference = _post(api_client, _body(kind, **{name_field: hostile})).json()["reference"]

    rendered = render_public_enquiry_email(OutboxMessage.objects.get(), redact=False)

    assert rendered.subject == f"{subject} {reference}"
    assert "\n" not in rendered.subject and "\r" not in rendered.subject


@pytest.mark.django_db
@override_settings(PUBLIC_ENQUIRY_EMAIL=HQ, PUBLIC_APP_BASE_URL="https://banxum.test")
def test_typed_values_are_escaped_and_never_made_into_links(api_client: APIClient) -> None:
    _post(
        api_client,
        _body(
            "contact",
            name='<script>alert("x")</script>',
            message='Click <a href="https://evil.test">here</a> or https://phish.test/login',
        ),
    )

    html = render_public_enquiry_email(OutboxMessage.objects.get(), redact=False).body_html

    assert "<script>" not in html
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html
    assert 'href="https://evil.test"' not in html
    assert 'href="https://phish.test' not in html
    assert "https://phish.test/login" in html


@pytest.mark.django_db
@override_settings(
    PUBLIC_ENQUIRY_EMAIL=HQ,
    COMMUNICATIONS_EMAIL_PROVIDER="mock",
    PUBLIC_APP_BASE_URL="https://banxum.test",
)
def test_the_stored_copy_keeps_no_personal_details(api_client: APIClient) -> None:
    _post(api_client, _body("company"))

    dispatch_due_email_outbox_messages()

    record = EmailDeliveryRecord.objects.get()
    for secret in ("Muster Bau AG", "anna.muster@example.test", "+41 44 123 45 67", "Family firm"):
        assert secret not in record.body_html
        assert secret not in record.body_text
    assert REDACTED_SECRET in record.body_html
    assert record.metadata["details_redacted_in_record"] is True
    assert record.metadata["reference"] == PublicEnquiry.objects.get().reference


@pytest.mark.django_db
@override_settings(PUBLIC_ENQUIRY_EMAIL=HQ, PUBLIC_APP_BASE_URL="https://banxum.test")
def test_reply_to_is_left_out_when_the_address_is_not_safe(api_client: APIClient) -> None:
    _post(api_client, _body("contact"))
    enquiry = PublicEnquiry.objects.get()
    PublicEnquiry.objects.filter(pk=enquiry.pk).update(sender_email="a@example.test\r\nBcc: x@y.z")

    rendered = render_public_enquiry_email(OutboxMessage.objects.get(), redact=False)

    assert rendered.reply_to == ""
    assert "eva@example.test" in rendered.body_text


class _FakeProviderResponse:
    status = 202
    headers = {"X-Message-Id": "sendgrid-message-1"}

    def __enter__(self) -> _FakeProviderResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"operationId": "comms_operation_1"}'


@pytest.mark.django_db
@pytest.mark.parametrize("provider", ["sendgrid", "twilio_email"])
def test_reply_to_is_set_only_where_the_provider_supports_it(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch, settings: Any, provider: str
) -> None:
    settings.PUBLIC_ENQUIRY_EMAIL = HQ
    settings.PUBLIC_APP_BASE_URL = "https://banxum.test"
    settings.SENDGRID_API_KEY = "SG.test"
    settings.SENDGRID_FROM_EMAIL = "notifications@banxum.test"
    settings.TWILIO_EMAIL_API_KEY_SID = "SK-test"
    settings.TWILIO_EMAIL_API_KEY_SECRET = "secret"
    settings.TWILIO_EMAIL_FROM_EMAIL = "notifications@banxum.test"
    settings.COMMUNICATIONS_EMAIL_PROVIDER = provider
    _post(api_client, _body("contact"))
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: int) -> _FakeProviderResponse:
        captured["payload"] = json.loads(cast(bytes, request.data).decode("utf-8"))
        return _FakeProviderResponse()

    monkeypatch.setattr("backend.apps.communications.services.urllib.request.urlopen", fake_urlopen)

    assert dispatch_due_email_outbox_messages().sent_count == 1

    payload = captured["payload"]
    if provider == "sendgrid":
        assert payload["reply_to"] == {"email": "eva@example.test"}
        assert payload["personalizations"][0]["to"] == [{"email": HQ}]
    else:
        assert "reply_to" not in json.dumps(payload).lower().replace("-", "_")
        assert payload["to"] == [{"address": HQ}]
        # Without Reply-To the address is still in the body.
        assert "eva@example.test" in payload["content"]["text"]


@pytest.mark.django_db
@override_settings(
    PUBLIC_ENQUIRY_EMAIL=HQ,
    COMMUNICATIONS_EMAIL_PROVIDER="sendgrid",
    SENDGRID_API_KEY="",
    PUBLIC_APP_BASE_URL="https://banxum.test",
)
def test_failed_sends_retry_and_show_on_the_enquiry(api_client: APIClient) -> None:
    _post(api_client, _body("contact"))

    dispatch_due_email_outbox_messages()

    enquiry = PublicEnquiry.objects.get()
    assert enquiry.delivery_status == PublicEnquiryDeliveryStatus.RETRYING
    message = OutboxMessage.objects.get()
    assert message.status == OutboxStatus.PENDING
    OutboxMessage.objects.filter(pk=message.pk).update(attempts=99, next_attempt_at=None)
    dispatch_due_email_outbox_messages()
    enquiry.refresh_from_db()
    assert enquiry.delivery_status == PublicEnquiryDeliveryStatus.FAILED


@pytest.mark.django_db
@override_settings(PUBLIC_ENQUIRY_EMAIL=HQ, PUBLIC_APP_BASE_URL="https://banxum.test")
def test_email_of_a_deleted_enquiry_is_not_rendered(api_client: APIClient) -> None:
    _post(api_client, _body("contact"))
    message = OutboxMessage.objects.get()
    PublicEnquiry.objects.all().delete()

    with pytest.raises(Exception, match="no longer exists"):
        render_public_enquiry_email(message, redact=False)


@pytest.mark.django_db
def test_endpoint_needs_no_session_or_csrf(api_client: APIClient) -> None:
    client = APIClient(enforce_csrf_checks=True)

    response = client.post(URL, _body("contact"), format="json", REMOTE_ADDR="192.0.2.1")

    assert response.status_code == 201


def test_ip_hash_is_keyed_and_stable() -> None:
    assert public_ip_hash("203.0.113.10") == public_ip_hash("203.0.113.10")
    assert public_ip_hash("203.0.113.10") != public_ip_hash("203.0.113.11")
    import hashlib

    assert public_ip_hash("203.0.113.10") != hashlib.sha256(b"203.0.113.10").hexdigest()
    assert public_ip_hash("") == ""


def test_months_before_clamps_to_month_end() -> None:
    from backend.apps.communications.public_forms import months_before

    value = datetime(2026, 2, 28, 10, 0, tzinfo=UTC)
    assert months_before(value, 24) == datetime(2024, 2, 28, 10, 0, tzinfo=UTC)
    value = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)
    assert months_before(value, 6) == datetime(2026, 2, 28, 10, 0, tzinfo=UTC)
    assert months_before(value, 24) - timedelta(days=1) < datetime(2024, 8, 31, tzinfo=UTC)
