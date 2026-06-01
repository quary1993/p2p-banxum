from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from backend.apps.accounts_auth.models import AccountStatus, AccountType, SensitiveAction, User
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
        SensitiveActionCodeCommand(user=investor, action=SensitiveAction.FX)
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
                raw_code=result.raw_code,
            )
        )


@pytest.mark.django_db
def test_sensitive_action_code_enforces_max_attempts(investor: User) -> None:
    result = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor,
            action=SensitiveAction.PRIMARY_INVESTMENT,
            max_attempts=2,
        )
    )
    wrong_code = "000000" if result.raw_code != "000000" else "111111"
    other_wrong_code = "222222" if result.raw_code != "222222" else "333333"

    with pytest.raises(InvalidOrExpiredCodeError):
        consume_sensitive_action_code(
            SensitiveActionCodeConsumeCommand(
                code_id=str(result.code_record.id),
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
                raw_code=other_wrong_code,
            )
        )
    with pytest.raises(TooManyCodeAttemptsError):
        consume_sensitive_action_code(
            SensitiveActionCodeConsumeCommand(
                code_id=str(result.code_record.id),
                raw_code=result.raw_code,
            )
        )


@pytest.mark.django_db
def test_expired_sensitive_action_code_is_rejected(investor: User) -> None:
    result = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor,
            action=SensitiveAction.SECONDARY_MARKET_PURCHASE,
            ttl=timedelta(seconds=-1),
        )
    )

    with pytest.raises(InvalidOrExpiredCodeError):
        consume_sensitive_action_code(
            SensitiveActionCodeConsumeCommand(
                code_id=str(result.code_record.id),
                raw_code=result.raw_code,
            )
        )


@pytest.mark.django_db
def test_sensitive_action_code_issue_enforces_cooldown(investor: User) -> None:
    issue_sensitive_action_code(
        SensitiveActionCodeCommand(user=investor, action=SensitiveAction.WITHDRAWAL)
    )

    with pytest.raises(SensitiveActionCodeThrottleError):
        issue_sensitive_action_code(
            SensitiveActionCodeCommand(user=investor, action=SensitiveAction.WITHDRAWAL)
        )


@pytest.mark.django_db
def test_sensitive_action_code_reissue_supersedes_prior_active_code(
    investor: User,
    settings: Any,
) -> None:
    settings.AUTH_SENSITIVE_CODE_COOLDOWN_SECONDS = 0
    first = issue_sensitive_action_code(
        SensitiveActionCodeCommand(user=investor, action=SensitiveAction.BANK_ACCOUNT_CHANGE)
    )
    second = issue_sensitive_action_code(
        SensitiveActionCodeCommand(user=investor, action=SensitiveAction.BANK_ACCOUNT_CHANGE)
    )

    first.code_record.refresh_from_db()
    assert first.code_record.superseded_at is not None

    with pytest.raises(InvalidOrExpiredCodeError):
        consume_sensitive_action_code(
            SensitiveActionCodeConsumeCommand(
                code_id=str(first.code_record.id),
                raw_code=first.raw_code,
            )
        )

    consumed = consume_sensitive_action_code(
        SensitiveActionCodeConsumeCommand(
            code_id=str(second.code_record.id),
            raw_code=second.raw_code,
        )
    )
    assert consumed.consumed_at is not None
