"""IP of Webby-Soft SRL. Currency exchange switched off by ``fx.enabled`` (2026-10-16, row 6)."""

from __future__ import annotations

from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.fx.models import FxExchange, FxQuote
from backend.apps.fx.services import (
    ExecuteFxQuoteCommand,
    FxDisabledError,
    PreviewFxQuoteCommand,
    execute_fx_quote,
    fx_enabled,
    issue_fx_quote,
    preview_fx_quote,
)
from backend.apps.fx.tests.factories import set_fx_enabled
from backend.apps.fx.tests.test_fx import (
    _approve_financial_access,
    _as_of,
    _deposit,
    _provider_rate,
    _quote_command,
    _sensitive_code_payload,
)
from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.models import AuditEvent, PlatformSetting, PlatformSettingVersion

DISABLED = {"detail": "Currency exchange is not available at the moment.", "code": "fx_disabled"}


@pytest.fixture
def fx_admin() -> Model:
    return cast(
        Model,
        get_user_model().objects.create_user(
            email="fx-switch-admin@example.test",
            password="AdminPass123!",
            full_name="FX Switch Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def fx_investor() -> Model:
    return cast(
        Model,
        get_user_model().objects.create_user(
            email="fx-switch-investor@example.test",
            full_name="FX Switch Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )


@pytest.mark.django_db
def test_fx_is_off_without_a_setting_row() -> None:
    PlatformSetting.objects.filter(key="fx.enabled").delete()
    assert fx_enabled() is False
    set_fx_enabled(True)
    assert fx_enabled() is True


@pytest.mark.django_db
def test_fx_endpoints_refuse_when_off_and_work_again_when_on(
    fx_admin: Model,
    fx_investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approve_financial_access(fx_investor)
    today = timezone.localtime(timezone.now(), business_timezone()).date()
    lot = _deposit(
        fx_admin,
        fx_investor,
        amount_minor=10_000_00,
        value_date=today,
        idempotency_key="fx-switch-deposit",
    )
    client = Client()
    client.force_login(cast(Any, fx_investor))
    quote_body: dict[str, str | int] = {
        "source_currency": "CHF",
        "target_currency": "EUR",
        "source_amount_minor": 1_000_00,
    }
    # A quote issued while FX was on.
    issued = client.post(
        "/api/v1/fx/quotes/",
        data={**quote_body, "idempotency_key": "fx-switch-quote"},
        content_type="application/json",
    )
    assert issued.status_code == 201
    quote_id = issued.json()["id"]

    set_fx_enabled(False)
    views = import_module("backend.apps.fx.api.views")

    def provider_must_not_be_called(**_kwargs: Any) -> Any:
        raise AssertionError("No FX rate is fetched while FX is off.")

    monkeypatch.setattr(views, "configured_provider_rate", provider_must_not_be_called)
    preview = client.get("/api/v1/fx/quote-preview/", data=quote_body)
    assert preview.status_code == 409
    assert preview.json() == DISABLED
    new_quote = client.post(
        "/api/v1/fx/quotes/",
        data={**quote_body, "idempotency_key": "fx-switch-quote-2"},
        content_type="application/json",
    )
    assert new_quote.status_code == 409
    assert new_quote.json() == DISABLED
    code = _sensitive_code_payload(fx_investor, "fx")
    refused = client.post(
        f"/api/v1/fx/quotes/{quote_id}/execute/",
        data={"idempotency_key": "fx-switch-execute", **code},
        content_type="application/json",
    )
    assert refused.status_code == 409
    assert refused.json() == DISABLED
    assert FxQuote.objects.count() == 1
    assert FxExchange.objects.count() == 0
    cast(Any, lot).refresh_from_db()
    assert cast(Any, lot).available_amount_minor == 10_000_00
    monkeypatch.undo()

    # Switched on again: the same quote executes with the same, unused email code.
    set_fx_enabled(True)
    executed = client.post(
        f"/api/v1/fx/quotes/{quote_id}/execute/",
        data={"idempotency_key": "fx-switch-execute", **code},
        content_type="application/json",
    )
    assert executed.status_code == 201
    assert FxExchange.objects.count() == 1

    # Off again: past exchanges stay readable for the investor and for operations.
    set_fx_enabled(False)
    history = client.get("/api/v1/investor/portal/fx/")
    assert history.status_code == 200
    assert [row["id"] for row in history.json()["exchanges"]] == [executed.json()["id"]]
    activity = client.get("/api/v1/investor/portal/activity/")
    assert activity.status_code == 200
    assert any(entry["activity_type"] == "fx_exchange" for entry in activity.json()["entries"])
    client.logout()
    client.force_login(cast(Any, fx_admin))
    report = client.get(
        "/api/v1/fx/admin/delta-report/",
        data={"start_date": today.isoformat(), "end_date": today.isoformat()},
    )
    assert report.status_code == 200
    assert report.json()["exchange_count"] == 1


@pytest.mark.django_db
def test_fx_services_refuse_when_off_but_replay_a_completed_exchange(
    fx_admin: Model,
    fx_investor: Model,
) -> None:
    _approve_financial_access(fx_investor)
    _deposit(fx_admin, fx_investor, amount_minor=10_000_00, idempotency_key="fx-switch-svc")
    as_of = _as_of()
    quote = issue_fx_quote(
        _quote_command(fx_investor, amount_minor=1_000_00, idempotency_key="fx-svc-q", as_of=as_of)
    )
    execute = ExecuteFxQuoteCommand(
        actor=fx_investor,
        quote_id=str(quote.id),
        idempotency_key="fx-svc-execute",
        as_of=as_of,
        **_sensitive_code_payload(fx_investor, "fx"),
    )
    exchange = execute_fx_quote(execute)

    set_fx_enabled(False)
    with pytest.raises(FxDisabledError, match="not available at the moment"):
        preview_fx_quote(
            PreviewFxQuoteCommand(
                actor=fx_investor,
                source_currency="CHF",
                target_currency="EUR",
                source_amount_minor=1_000_00,
                provider_rate=_provider_rate(as_of=as_of),
                as_of=as_of,
            )
        )
    with pytest.raises(FxDisabledError):
        issue_fx_quote(
            _quote_command(fx_investor, amount_minor=500_00, idempotency_key="fx-q2", as_of=as_of)
        )
    # The retry of an exchange that already went through still answers with it.
    assert execute_fx_quote(execute).id == exchange.id
    assert FxQuote.objects.count() == 1
    assert FxExchange.objects.count() == 1


def _record_fx_switched_off() -> Any:
    migration = import_module("backend.apps.fx.migrations.0007_record_fx_switched_off")
    return migration.record_fx_switched_off


@pytest.mark.django_db
def test_fx_switch_migration_records_the_decision_on_seeded_deployments() -> None:
    record = _record_fx_switched_off()
    PlatformSetting.objects.filter(key="fx.enabled").delete()

    # A fresh database: nothing to record, the seed creates the row later.
    record(apps, None)
    assert not PlatformSetting.objects.filter(key="fx.enabled").exists()

    # A seeded deployment without the row gets it (off), with a version and an audit event.
    PlatformSetting.objects.create(key="platform.brand_name", value="BANXUM")
    record(apps, None)
    record(apps, None)
    setting = PlatformSetting.objects.get(key="fx.enabled")
    assert setting.value is False
    assert setting.value_type == "boolean"
    versions = list(PlatformSettingVersion.objects.filter(key="fx.enabled"))
    assert len(versions) == 1
    assert versions[0].changed_by_type == "system"
    assert "Owner decision 2026-10-16" in versions[0].reason
    audit = AuditEvent.objects.get(target_id="fx.enabled")
    assert audit.action == "platform_setting.created"
    assert audit.actor_type == "system"

    # A row someone already set is left alone.
    PlatformSetting.objects.filter(key="fx.enabled").update(value=True)
    record(apps, None)
    assert PlatformSetting.objects.get(key="fx.enabled").value is True
    assert PlatformSettingVersion.objects.filter(key="fx.enabled").count() == 1
