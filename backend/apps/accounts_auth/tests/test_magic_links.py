from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import Client

from backend.apps.accounts_auth.models import AccountStatus, AccountType, EmailLoginToken, User
from backend.apps.accounts_auth.services import (
    InvalidOrExpiredTokenError,
    MagicLinkConsumeCommand,
    MagicLinkRequestCommand,
    consume_magic_link,
    issue_magic_link,
)
from backend.apps.platform_core.models import OutboxMessage


@pytest.fixture
def investor() -> User:
    return User.objects.create_user(
        email="investor@example.test",
        full_name="Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.PENDING_KYC,
    )


@pytest.mark.django_db
def test_issue_magic_link_creates_single_use_token_and_email_outbox(investor: User) -> None:
    result = issue_magic_link(MagicLinkRequestCommand(email=investor.email))

    assert result.raw_token
    assert result.login_token.user_id == investor.id
    assert OutboxMessage.objects.filter(
        topic="email.magic_link_requested",
        idempotency_key=f"magic-link:{result.login_token.id}",
    ).exists()

    authenticated = consume_magic_link(MagicLinkConsumeCommand(raw_token=result.raw_token))

    assert authenticated.id == investor.id
    assert EmailLoginToken.objects.get(id=result.login_token.id).used_at is not None

    with pytest.raises(InvalidOrExpiredTokenError):
        consume_magic_link(MagicLinkConsumeCommand(raw_token=result.raw_token))


@pytest.mark.django_db
def test_expired_magic_link_is_rejected(investor: User) -> None:
    result = issue_magic_link(
        MagicLinkRequestCommand(email=investor.email, ttl=timedelta(seconds=-1))
    )

    with pytest.raises(InvalidOrExpiredTokenError):
        consume_magic_link(MagicLinkConsumeCommand(raw_token=result.raw_token))


@pytest.mark.django_db
def test_magic_link_request_api_does_not_reveal_account_existence(client: Client) -> None:
    response = client.post(
        "/api/v1/auth/magic-link/request/",
        data={"email": "missing@example.test"},
        content_type="application/json",
    )

    assert response.status_code == 202


@pytest.mark.django_db
def test_magic_link_consume_api_logs_in_session(client: Client, investor: User) -> None:
    result = issue_magic_link(MagicLinkRequestCommand(email=investor.email))

    response = client.post(
        "/api/v1/auth/magic-link/consume/",
        data={"token": result.raw_token},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == investor.email

    me_response = client.get("/api/v1/auth/me/")

    assert me_response.status_code == 200
    assert me_response.json()["user"]["email"] == investor.email
