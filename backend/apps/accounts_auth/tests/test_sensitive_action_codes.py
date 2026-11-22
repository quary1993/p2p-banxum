from __future__ import annotations

import json
from datetime import timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.test import Client
from django.test.utils import override_settings
from django.utils import timezone

from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    SensitiveAction,
    SensitiveActionCode,
    User,
)
from backend.apps.accounts_auth.services import (
    InvalidOrExpiredCodeError,
    SensitiveActionCodeCommand,
    SensitiveActionCodeConsumeCommand,
    SensitiveActionCodeThrottleError,
    TooManyCodeAttemptsError,
    consume_sensitive_action_code,
    delivery_secret_for_sensitive_action_code,
    issue_sensitive_action_code,
)
from backend.apps.platform_core.models import AuditEvent, OutboxMessage

# 18.5: the operation each code is requested for (these tests check single use, attempts
# and expiry; the binding itself is tested in test_operation_binding_18_5.py).
OPERATIONS: dict[str, dict[str, object]] = {
    SensitiveAction.WITHDRAWAL: {
        "amount_minor": 500_00,
        "currency": "CHF",
        "iban": "CH5604835012345678009",
    },
    SensitiveAction.BANK_ACCOUNT_CHANGE: {"currency": "CHF", "iban": "CH5604835012345678009"},
    SensitiveAction.FX: {
        "amount_minor": 1_000_00,
        "source_currency": "CHF",
        "target_currency": "EUR",
    },
    SensitiveAction.PRIMARY_INVESTMENT: {
        "amount_minor": 1_000_00,
        "currency": "CHF",
        "loan_id": "7b1d4c1e-0000-4000-8000-000000000001",
    },
    SensitiveAction.SECONDARY_MARKET_PURCHASE: {
        "amount_minor": 1_000_00,
        "currency": "CHF",
        "listing_id": "7b1d4c1e-0000-4000-8000-000000000002",
    },
}


def _stored_fingerprint(code_id: object) -> str:
    """The fingerprint the code was issued with ("" for an unknown code)."""
    value = (
        SensitiveActionCode.objects.filter(id=str(code_id))
        .values_list("operation_fingerprint", flat=True)
        .first()
    )
    return str(value or "")


class _FakeSendGridResponse:
    status = 202
    headers = {"X-Message-Id": "sendgrid-sensitive-code"}

    def __enter__(self) -> _FakeSendGridResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b""


def _communications_services() -> Any:
    return import_module("backend.apps.communications.services")


def _email_delivery_record_model() -> Any:
    return apps.get_model("communications", "EmailDeliveryRecord")


@pytest.fixture
def investor() -> User:
    return User.objects.create_user(
        email="investor@example.test",
        full_name="Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.ACTIVE,
    )


@pytest.mark.django_db
def test_sensitive_action_code_is_single_use_and_emits_email_outbox(investor: User) -> None:
    result = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor, action=SensitiveAction.FX, operation=OPERATIONS[SensitiveAction.FX]
        )
    )

    assert result.raw_code.isdigit()
    assert len(result.raw_code) == 6
    outbox_message = OutboxMessage.objects.get(
        topic="email.sensitive_action_code_requested",
        idempotency_key=f"sensitive-action-code:{result.code_record.id}",
    )
    assert "code" not in outbox_message.payload
    assert outbox_message.payload["delivery_secret_ref"] == str(result.code_record.id)
    assert outbox_message.payload["secret_redacted"] is True
    result.code_record.refresh_from_db()
    assert result.raw_code not in result.code_record.encrypted_code
    assert delivery_secret_for_sensitive_action_code(result.code_record) == result.raw_code

    consumed = consume_sensitive_action_code(
        SensitiveActionCodeConsumeCommand(
            code_id=str(result.code_record.id),
            expected_operation_fingerprint=_stored_fingerprint(str(result.code_record.id)),
            raw_code=result.raw_code,
        )
    )

    assert consumed.consumed_at is not None
    assert AuditEvent.objects.filter(
        action="auth.sensitive_action_code_consumed",
        target_id=str(investor.id),
    ).exists()

    with pytest.raises(InvalidOrExpiredCodeError):
        consume_sensitive_action_code(
            SensitiveActionCodeConsumeCommand(
                code_id=str(result.code_record.id),
                expected_operation_fingerprint=_stored_fingerprint(str(result.code_record.id)),
                raw_code=result.raw_code,
            )
        )


@pytest.mark.django_db
def test_investor_cannot_receive_admin_login_code(investor: User) -> None:
    with pytest.raises(InvalidOrExpiredCodeError):
        issue_sensitive_action_code(
            SensitiveActionCodeCommand(user=investor, action=SensitiveAction.ADMIN_LOGIN)
        )

    assert OutboxMessage.objects.count() == 0


@pytest.mark.django_db
def test_sensitive_action_code_enforces_max_attempts(investor: User) -> None:
    result = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor,
            action=SensitiveAction.PRIMARY_INVESTMENT,
            operation=OPERATIONS[SensitiveAction.PRIMARY_INVESTMENT],
            max_attempts=2,
        )
    )
    wrong_code = "000000" if result.raw_code != "000000" else "111111"
    other_wrong_code = "222222" if result.raw_code != "222222" else "333333"

    with pytest.raises(InvalidOrExpiredCodeError):
        consume_sensitive_action_code(
            SensitiveActionCodeConsumeCommand(
                code_id=str(result.code_record.id),
                expected_operation_fingerprint=_stored_fingerprint(str(result.code_record.id)),
                raw_code=wrong_code,
            )
        )
    assert AuditEvent.objects.filter(
        action="auth.sensitive_action_code_failed",
        target_id=str(investor.id),
        metadata__reason="invalid_code",
    ).exists()
    with pytest.raises(TooManyCodeAttemptsError):
        consume_sensitive_action_code(
            SensitiveActionCodeConsumeCommand(
                code_id=str(result.code_record.id),
                expected_operation_fingerprint=_stored_fingerprint(str(result.code_record.id)),
                raw_code=other_wrong_code,
            )
        )
    with pytest.raises(TooManyCodeAttemptsError):
        consume_sensitive_action_code(
            SensitiveActionCodeConsumeCommand(
                code_id=str(result.code_record.id),
                expected_operation_fingerprint=_stored_fingerprint(str(result.code_record.id)),
                raw_code=result.raw_code,
            )
        )


@pytest.mark.django_db
def test_requested_sensitive_action_code_locks_after_three_wrong_attempts(
    client: Client,
    investor: User,
) -> None:
    client.force_login(investor)
    response = client.post(
        "/api/v1/auth/sensitive-action-code/request/",
        data={
            "action": SensitiveAction.WITHDRAWAL,
            "operation": OPERATIONS[SensitiveAction.WITHDRAWAL],
        },
        content_type="application/json",
    )
    assert response.status_code == 202
    code_record = SensitiveActionCode.objects.get(id=response.json()["code_id"])
    raw_code = delivery_secret_for_sensitive_action_code(code_record)
    wrong_code = "000000" if raw_code != "000000" else "111111"

    def attempt(value: str) -> None:
        consume_sensitive_action_code(
            SensitiveActionCodeConsumeCommand(
                code_id=str(code_record.id),
                expected_operation_fingerprint=_stored_fingerprint(str(code_record.id)),
                raw_code=value,
                expected_user=investor,
                expected_action=SensitiveAction.WITHDRAWAL,
            )
        )

    assert code_record.max_attempts == 3
    for _ in range(2):
        with pytest.raises(InvalidOrExpiredCodeError):
            attempt(wrong_code)
    with pytest.raises(TooManyCodeAttemptsError):
        attempt(wrong_code)
    # The limit holds even for the right code once three attempts were used.
    with pytest.raises(TooManyCodeAttemptsError):
        attempt(raw_code)
    code_record.refresh_from_db()
    assert code_record.attempts == 3
    assert code_record.consumed_at is None


@pytest.mark.django_db
@override_settings(AUTH_SENSITIVE_CODE_MAX_ATTEMPTS=5)
def test_sensitive_action_code_attempt_limit_follows_setting(investor: User) -> None:
    result = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor, action=SensitiveAction.FX, operation=OPERATIONS[SensitiveAction.FX]
        )
    )

    assert result.code_record.max_attempts == 5


@pytest.mark.django_db
def test_expired_sensitive_action_code_is_rejected(investor: User) -> None:
    result = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor,
            action=SensitiveAction.SECONDARY_MARKET_PURCHASE,
            operation=OPERATIONS[SensitiveAction.SECONDARY_MARKET_PURCHASE],
            ttl=timedelta(seconds=-1),
        )
    )

    with pytest.raises(InvalidOrExpiredCodeError):
        consume_sensitive_action_code(
            SensitiveActionCodeConsumeCommand(
                code_id=str(result.code_record.id),
                expected_operation_fingerprint=_stored_fingerprint(str(result.code_record.id)),
                raw_code=result.raw_code,
            )
        )


@pytest.mark.django_db
def test_sensitive_action_code_issue_enforces_cooldown(investor: User) -> None:
    issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor,
            action=SensitiveAction.WITHDRAWAL,
            operation=OPERATIONS[SensitiveAction.WITHDRAWAL],
        )
    )

    with pytest.raises(SensitiveActionCodeThrottleError):
        issue_sensitive_action_code(
            SensitiveActionCodeCommand(
                user=investor,
                action=SensitiveAction.WITHDRAWAL,
                operation=OPERATIONS[SensitiveAction.WITHDRAWAL],
            )
        )


@pytest.mark.django_db
def test_cooldown_is_measured_in_real_time_when_the_qa_clock_is_ahead(
    investor: User,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # QA testers could not get a new email code after moving the QA clock forward: the
    # QA-time created_at was in the future, so the cooldown lasted until the code expired.
    settings.AUTH_SENSITIVE_CODE_COOLDOWN_SECONDS = 60
    time_module = import_module("backend.apps.platform_core.domain.time")
    ahead = timezone.now() + timedelta(days=30)
    monkeypatch.setattr(time_module, "_qa_dev_mode_time_override", lambda: ahead)
    first = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor,
            action=SensitiveAction.WITHDRAWAL,
            operation=OPERATIONS[SensitiveAction.WITHDRAWAL],
        )
    )
    first.code_record.refresh_from_db()
    assert first.code_record.created_at > timezone.now() + timedelta(days=29)
    # Two real minutes pass.
    SensitiveActionCode.objects.filter(pk=first.code_record.pk).update(
        expires_at=first.code_record.expires_at - timedelta(minutes=2)
    )

    second = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor,
            action=SensitiveAction.WITHDRAWAL,
            operation=OPERATIONS[SensitiveAction.WITHDRAWAL],
        )
    )

    assert second.code_record.pk != first.code_record.pk
    with pytest.raises(SensitiveActionCodeThrottleError):
        issue_sensitive_action_code(
            SensitiveActionCodeCommand(
                user=investor,
                action=SensitiveAction.WITHDRAWAL,
                operation=OPERATIONS[SensitiveAction.WITHDRAWAL],
            )
        )


@pytest.mark.django_db
def test_sensitive_action_code_reissue_supersedes_prior_active_code(
    investor: User,
    settings: Any,
) -> None:
    settings.AUTH_SENSITIVE_CODE_COOLDOWN_SECONDS = 0
    first = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor,
            action=SensitiveAction.BANK_ACCOUNT_CHANGE,
            operation=OPERATIONS[SensitiveAction.BANK_ACCOUNT_CHANGE],
        )
    )
    second = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor,
            action=SensitiveAction.BANK_ACCOUNT_CHANGE,
            operation=OPERATIONS[SensitiveAction.BANK_ACCOUNT_CHANGE],
        )
    )

    first.code_record.refresh_from_db()
    assert first.code_record.superseded_at is not None

    with pytest.raises(InvalidOrExpiredCodeError):
        consume_sensitive_action_code(
            SensitiveActionCodeConsumeCommand(
                code_id=str(first.code_record.id),
                expected_operation_fingerprint=_stored_fingerprint(str(first.code_record.id)),
                raw_code=first.raw_code,
            )
        )

    consumed = consume_sensitive_action_code(
        SensitiveActionCodeConsumeCommand(
            code_id=str(second.code_record.id),
            expected_operation_fingerprint=_stored_fingerprint(str(second.code_record.id)),
            raw_code=second.raw_code,
        )
    )
    assert consumed.consumed_at is not None


@pytest.mark.django_db
def test_sensitive_action_code_request_api_issues_investor_money_code(
    client: Client,
    investor: User,
) -> None:
    client.force_login(investor)

    response = client.post(
        "/api/v1/auth/sensitive-action-code/request/",
        data={"action": SensitiveAction.FX, "operation": OPERATIONS[SensitiveAction.FX]},
        content_type="application/json",
    )

    assert response.status_code == 202
    body = response.json()
    assert body["action"] == SensitiveAction.FX
    assert body["status"] == "code_sent"
    assert body["code_id"]
    assert OutboxMessage.objects.filter(
        topic="email.sensitive_action_code_requested",
        payload__action=SensitiveAction.FX,
    ).exists()


@pytest.mark.django_db
@override_settings(
    COMMUNICATIONS_EMAIL_PROVIDER="sendgrid",
    SENDGRID_API_KEY="SG.test",
    SENDGRID_FROM_EMAIL="hq@banxum.com",
    SENDGRID_FROM_NAME="BANXUM",
    PUBLIC_APP_BASE_URL="https://app.banxum.test",
)
def test_sensitive_action_code_request_api_dispatches_via_mocked_sendgrid(
    client: Client,
    investor: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: int) -> _FakeSendGridResponse:
        captured["payload"] = json.loads(cast(bytes, request.data).decode("utf-8"))
        captured["authorization"] = dict(request.header_items())["Authorization"]
        return _FakeSendGridResponse()

    monkeypatch.setattr(
        "backend.apps.communications.services.urllib.request.urlopen",
        fake_urlopen,
    )
    client.force_login(investor)

    response = client.post(
        "/api/v1/auth/sensitive-action-code/request/",
        data={
            "action": SensitiveAction.WITHDRAWAL,
            "operation": OPERATIONS[SensitiveAction.WITHDRAWAL],
        },
        content_type="application/json",
    )
    dispatch_result = _communications_services().dispatch_due_email_outbox_messages()

    assert response.status_code == 202
    assert dispatch_result.sent_count == 1
    assert captured["authorization"] == "Bearer SG.test"
    assert captured["payload"]["personalizations"][0]["to"][0]["email"] == investor.email
    assert captured["payload"]["from"] == {"email": "hq@banxum.com", "name": "BANXUM"}
    assert captured["payload"]["tracking_settings"]["click_tracking"]["enable"] is False
    delivery = _email_delivery_record_model().objects.get(
        provider_message_id="sendgrid-sensitive-code"
    )
    assert delivery.status == "sent"
    assert delivery.template_key == "auth.withdrawal.code.v1"


@pytest.mark.django_db
def test_sensitive_action_code_request_api_rejects_admin_login_action(
    client: Client,
    investor: User,
) -> None:
    client.force_login(investor)

    response = client.post(
        "/api/v1/auth/sensitive-action-code/request/",
        data={"action": SensitiveAction.ADMIN_LOGIN},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert OutboxMessage.objects.filter(topic="email.sensitive_action_code_requested").count() == 0


@pytest.mark.django_db
def test_sensitive_action_code_request_api_enforces_issue_cooldown(
    client: Client,
    investor: User,
) -> None:
    client.force_login(investor)

    first = client.post(
        "/api/v1/auth/sensitive-action-code/request/",
        data={
            "action": SensitiveAction.WITHDRAWAL,
            "operation": OPERATIONS[SensitiveAction.WITHDRAWAL],
        },
        content_type="application/json",
    )
    second = client.post(
        "/api/v1/auth/sensitive-action-code/request/",
        data={
            "action": SensitiveAction.WITHDRAWAL,
            "operation": OPERATIONS[SensitiveAction.WITHDRAWAL],
        },
        content_type="application/json",
    )

    assert first.status_code == 202
    assert second.status_code == 429


@pytest.mark.django_db
def test_code_issuance_runs_under_the_account_lock_in_one_transaction(
    investor: User, monkeypatch: pytest.MonkeyPatch, row_locks_need_a_transaction: None
) -> None:
    """Audit S4-3: the caps, the cooldown, the supersession and the new code are one
    transaction, and the account's row is locked before any code is read. (The race itself is
    tested on PostgreSQL in test_postgres_auth_races.py.)"""
    from django.db import connection
    from django.db.models.query import QuerySet
    from django.test.utils import CaptureQueriesContext

    locked: list[str] = []
    checked = QuerySet.select_for_update

    def spy(self: Any, *args: Any, **kwargs: Any) -> Any:
        locked.append(self.model._meta.label)
        return checked(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "select_for_update", spy)
    with CaptureQueriesContext(connection) as queries:
        issue_sensitive_action_code(
            SensitiveActionCodeCommand(
                user=investor,
                action=SensitiveAction.WITHDRAWAL,
                operation=OPERATIONS[SensitiveAction.WITHDRAWAL],
            )
        )
    assert locked[0] == "accounts_auth.User"
    statements = [query["sql"] for query in queries]
    code_table = SensitiveActionCode._meta.db_table
    first_code_query = next(i for i, sql in enumerate(statements) if code_table in sql)
    lock_query = next(
        i for i, sql in enumerate(statements) if User._meta.db_table in sql and "SELECT" in sql
    )
    opened = next(i for i, sql in enumerate(statements) if sql.startswith("SAVEPOINT"))
    released = max(i for i, sql in enumerate(statements) if sql.startswith("RELEASE SAVEPOINT"))
    insert = next(
        i for i, sql in enumerate(statements) if sql.startswith("INSERT") and code_table in sql
    )
    assert opened < lock_query < first_code_query < insert < released


@pytest.mark.django_db
def test_a_code_for_changed_details_leaves_one_active_code(investor: User) -> None:
    """Audit S4-3: a new fingerprint supersedes the older code of the action; one stays."""
    first = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor,
            action=SensitiveAction.WITHDRAWAL,
            operation=OPERATIONS[SensitiveAction.WITHDRAWAL],
        )
    )
    changed = {**OPERATIONS[SensitiveAction.WITHDRAWAL], "amount_minor": 123_45}
    second = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor, action=SensitiveAction.WITHDRAWAL, operation=changed
        )
    )
    active = SensitiveActionCode.objects.filter(
        user=investor, consumed_at__isnull=True, superseded_at__isnull=True
    )
    assert [code.pk for code in active] == [second.code_record.pk]
    first.code_record.refresh_from_db()
    assert first.code_record.superseded_at is not None
