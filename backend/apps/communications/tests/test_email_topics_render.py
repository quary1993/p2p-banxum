"""Every email topic produced anywhere in the backend must render with the real renderer.

The test finds each producer call (``topic="email.…"``) in the source, rebuilds the payload
shape that producer writes (dict literal, local payload builder, local enqueue helper or the
shared investor-notice builder), fills it with sample values and renders it. A producer whose
payload keys the renderer cannot read (round 1: Smart Invest wrote ``body`` instead of
``body_text``) fails here instead of ending as a dead letter in production.
"""

from __future__ import annotations

import ast
import uuid
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import override_settings

from backend.apps.communications.services import render_email_for_outbox_message
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.services.investor_notices import (
    InvestorNotice,
    investor_notice_payload,
)

APPS_ROOT = Path(__file__).resolve().parents[2]
RECIPIENT = "render-check@example.test"
# Topics with a dedicated renderer that resolves a short-lived secret at dispatch time.
SECRET_TOPICS = frozenset({"email.magic_link_requested", "email.sensitive_action_code_requested"})


@dataclass(frozen=True)
class ProducerSite:
    topic: str
    location: str
    payload_keys: tuple[str, ...] | None
    shared_notice: bool = False


def _dict_keys(node: ast.AST) -> tuple[str, ...] | None:
    if not isinstance(node, ast.Dict):
        return None
    return tuple(
        key.value
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    )


def _returned_dict_keys(function: ast.FunctionDef) -> tuple[str, ...] | None:
    for node in ast.walk(function):
        if isinstance(node, ast.Return) and node.value is not None:
            keys = _dict_keys(node.value)
            if keys is not None:
                return keys
    return None


def _outbox_payload_keys(call: ast.Call, functions: dict[str, ast.FunctionDef]) -> Any:
    payload = next((kw.value for kw in call.keywords if kw.arg == "payload"), None)
    if payload is None:
        return None
    keys = _dict_keys(payload)
    if keys is not None:
        return keys
    if isinstance(payload, ast.Call) and isinstance(payload.func, ast.Name):
        builder = functions.get(payload.func.id)
        if builder is not None:
            return _returned_dict_keys(builder)
    return None


def _helper_payload_keys(helper: ast.FunctionDef, functions: dict[str, ast.FunctionDef]) -> Any:
    for node in ast.walk(helper):
        if isinstance(node, ast.Call) and any(kw.arg == "payload" for kw in node.keywords):
            return _outbox_payload_keys(node, functions)
    return None


def _producer_sites() -> list[ProducerSite]:
    sites: list[ProducerSite] = []
    for path in sorted(APPS_ROOT.rglob("*.py")):
        if "tests" in path.parts or "migrations" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            topic = next((kw.value for kw in node.keywords if kw.arg == "topic"), None)
            if not (
                isinstance(topic, ast.Constant)
                and isinstance(topic.value, str)
                and topic.value.startswith("email.")
            ):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else ""
            location = f"{path.relative_to(APPS_ROOT)}:{node.lineno}"
            if name == "InvestorNotice":
                sites.append(ProducerSite(topic.value, location, None, shared_notice=True))
            elif name in functions:
                keys = _helper_payload_keys(functions[name], functions)
                sites.append(ProducerSite(topic.value, location, keys))
            else:
                sites.append(
                    ProducerSite(topic.value, location, _outbox_payload_keys(node, functions))
                )
    return sites


def _sample_value(key: str) -> Any:
    if key in {"email", "recipient_email", "to_email"}:
        return RECIPIENT
    if key == "data_rows":
        return [["Amount", "CHF 1'000.00"], ["Date", "2026-10-09"]]
    if key == "buttons":
        return [{"label": "Open BANXUM", "url": "https://app.banxum.test/balances"}]
    if key == "metadata":
        return {"loan_id": str(uuid.uuid4())}
    if key == "action_url":
        return "https://app.banxum.test/smart-invest"
    if key == "status_tone":
        return "info"
    return f"Sample {key.replace('_', ' ')}"


def _secret_topic_message(topic: str, user: Model) -> OutboxMessage:
    auth = import_module("backend.apps.accounts_auth.services")
    if topic == "email.magic_link_requested":
        auth.issue_magic_link(auth.MagicLinkRequestCommand(email=cast(Any, user).email))
    else:
        auth.issue_sensitive_action_code(
            auth.SensitiveActionCodeCommand(user=user, action="withdrawal")
        )
    return OutboxMessage.objects.filter(topic=topic).latest("id")


def test_the_source_scan_finds_the_known_producers() -> None:
    topics = {site.topic for site in _producer_sites()}
    # A broken scan would silently test nothing.
    assert {
        "email.magic_link_requested",
        "email.repayment_distribution_credited",
        "email.smart_invest_opportunity_match",
        "email.loan_defaulted",
        "email.deposit_reconciled",
        "email.withdrawal_status",
        "email.loan_status_changed",
    } <= topics


@pytest.mark.django_db
@override_settings(
    COMMUNICATIONS_EMAIL_PROVIDER="mock",
    COMMUNICATIONS_IMMEDIATE_AUTH_EMAILS=False,
    PUBLIC_APP_BASE_URL="https://app.banxum.test",
)
def test_every_email_topic_in_the_codebase_renders() -> None:
    user = get_user_model().objects.create_user(
        email=RECIPIENT,
        full_name="Render Check",
        account_type="natural_person_lender",
        status="active",
    )
    failures: list[str] = []
    checked: set[str] = set()
    for site in _producer_sites():
        if site.topic in SECRET_TOPICS:
            message = _secret_topic_message(site.topic, cast(Model, user))
        elif site.shared_notice:
            payload = investor_notice_payload(
                InvestorNotice(
                    investor_user_id=str(user.pk),
                    topic=site.topic,
                    idempotency_key="render-check",
                    subject="Sample subject",
                    body_text="Sample body.\n\nSecond paragraph.",
                    template_key="render.check.v1",
                    data_rows=(("Amount", "CHF 1.00"),),
                    navigation_target="balances",
                ),
                email=RECIPIENT,
            )
            message = OutboxMessage(topic=site.topic, payload=payload)
        elif site.payload_keys is None:
            failures.append(f"{site.location} {site.topic}: payload shape cannot be read")
            continue
        else:
            payload = {key: _sample_value(key) for key in site.payload_keys}
            message = OutboxMessage(topic=site.topic, payload=payload)
        try:
            rendered = render_email_for_outbox_message(message)
        except Exception as exc:  # noqa: BLE001 - every failure is reported with its site.
            failures.append(f"{site.location} {site.topic}: {exc}")
            continue
        if not (
            rendered.subject and rendered.body_text and "<!DOCTYPE html>" in rendered.body_html
        ):
            failures.append(f"{site.location} {site.topic}: rendered an empty email")
        if rendered.recipient_email != RECIPIENT:
            failures.append(f"{site.location} {site.topic}: wrong recipient")
        checked.add(site.topic)

    assert not failures, "\n".join(failures)
    assert len(checked) >= 25


def test_a_payload_with_the_wrong_body_key_is_reported() -> None:
    # The round-1 Smart Invest defect: `body` instead of `body_text`.
    message = OutboxMessage(
        topic="email.example_notice",
        payload={"email": RECIPIENT, "subject": "Example", "body": "Text"},
    )
    with pytest.raises(Exception, match="no renderable template"):
        render_email_for_outbox_message(message)
