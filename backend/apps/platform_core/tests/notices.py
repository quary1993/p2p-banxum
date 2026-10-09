"""Test helpers for transactional investor notices (outbox messages + rendered emails)."""

from __future__ import annotations

import json
from importlib import import_module
from typing import Any

from django.db.models import Model

from backend.apps.platform_core.models import OutboxMessage


def investor_notices(investor: Model, topic: str) -> list[OutboxMessage]:
    return list(
        OutboxMessage.objects.filter(topic=topic, payload__user_id=str(investor.pk)).order_by("id")
    )


def only_notice(investor: Model, topic: str) -> OutboxMessage:
    notices = investor_notices(investor, topic)
    assert len(notices) == 1, [notice.payload.get("subject") for notice in notices]
    return notices[0]


def render_notice(message: OutboxMessage) -> Any:
    """Render through the real communications renderer (loaded by name: module boundaries)."""
    communications = import_module("backend.apps.communications.services")
    return communications.render_email_for_outbox_message(message)


def assert_renders_to(message: OutboxMessage, investor: Model, *texts: str) -> Any:
    rendered = render_notice(message)
    assert rendered.recipient_email == str(getattr(investor, "email", "")).lower()
    assert "<!DOCTYPE html>" in rendered.body_html
    assert rendered.subject == message.payload["subject"]
    assert rendered.body_text == message.payload["body_text"]
    for text in texts:
        # Data rows appear only in the HTML part, so the check reads the HTML email.
        assert text in rendered.body_html or text.replace("'", "&#x27;") in rendered.body_html, text
    return rendered


def payload_text(message: OutboxMessage) -> str:
    return json.dumps(message.payload, ensure_ascii=False)
