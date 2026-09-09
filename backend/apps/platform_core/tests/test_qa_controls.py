"""IP of Webby-Soft SRL. QA-only permissions, independent restore points and sessions."""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from backend.apps.platform_core.services.qa_dev_mode import (
    CreateQaSnapshotCommand,
    EnableQaDevModeCommand,
    RevertQaDevModeCommand,
    create_qa_snapshot,
    enable_qa_dev_mode,
    get_qa_dev_mode_state,
    revert_qa_dev_mode,
    serialize_qa_dev_mode_state,
)
from backend.apps.platform_core.services.qa_restore_points import read_restore_points


@pytest.fixture(autouse=True)
def qa_settings(settings: Any, tmp_path: Any) -> None:
    settings.ENVIRONMENT = "staging"
    settings.IS_PRODUCTION = False
    settings.QA_DEV_MODE_ALLOWED = True
    settings.QA_DEV_MODE_SNAPSHOT_DIR = str(tmp_path)


def admin(email: str = "qa-admin@example.test") -> Any:
    return get_user_model().objects.create_user(
        email=email,
        full_name="Seed admin",
        account_type="admin",
        status="active",
        is_staff=True,
        is_superuser=False,
        is_active=True,
    )


@pytest.mark.django_db
def test_seed_and_manual_snapshot_remain_independently_repeatable(
    django_capture_on_commit_callbacks: Any,
) -> None:
    actor = admin()
    with django_capture_on_commit_callbacks(execute=True):
        enable_qa_dev_mode(EnableQaDevModeCommand(actor=actor, repeatable_seed_snapshot=True))
    seed_time = get_qa_dev_mode_state().current_time
    state = serialize_qa_dev_mode_state(get_qa_dev_mode_state())
    assert state["has_seed"] and not state["has_snapshot"]
    assert state["default_restore_target"] == "seed"
    actor.full_name = "Discard this change"
    actor.save(update_fields=["full_name"])
    assert (
        revert_qa_dev_mode(RevertQaDevModeCommand(actor=actor, confirmation="REVERT QA DB"))
        == "seed"
    )
    actor.refresh_from_db()
    assert actor.full_name == "Seed admin"
    actor.full_name = "Manual checkpoint"
    actor.save(update_fields=["full_name"])
    with django_capture_on_commit_callbacks(execute=True):
        create_qa_snapshot(CreateQaSnapshotCommand(actor=actor))
    points = read_restore_points()
    assert points["seed"]["path"] != points["snapshot"]["path"]
    for target, expected in (
        ("auto", "Manual checkpoint"),
        ("seed", "Seed admin"),
        ("snapshot", "Manual checkpoint"),
        ("seed", "Seed admin"),
    ):
        actor.full_name = "Later changes"
        actor.save(update_fields=["full_name"])
        revert_qa_dev_mode(
            RevertQaDevModeCommand(actor=actor, confirmation="REVERT QA DB", target=target)
        )
        actor.refresh_from_db()
        assert actor.full_name == expected
        assert get_qa_dev_mode_state().current_time == seed_time
        assert read_restore_points() == points


@pytest.mark.django_db
def test_restore_keeps_only_calling_admin_session(django_capture_on_commit_callbacks: Any) -> None:
    actor = admin()
    other = admin("qa-other@example.test")
    caller, another = Client(), Client()
    caller.force_login(actor)
    another.force_login(other)
    with django_capture_on_commit_callbacks(execute=True):
        enable_qa_dev_mode(EnableQaDevModeCommand(actor=actor, repeatable_seed_snapshot=True))
    original_cookie = caller.cookies["sessionid"].value
    response = caller.post(
        "/api/v1/qa/dev-mode/revert/",
        {"confirmation": "REVERT QA DB"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["requires_login"] is False
    assert response.json()["restored_target"] == "seed"
    assert caller.cookies["sessionid"].value != original_cookie
    assert caller.get("/api/v1/qa/dev-mode/").status_code == 200
    assert another.get("/api/v1/auth/me/").status_code == 403
    assert caller.get("/api/v1/auth/me/").json()["user"]["account_type"] == "admin"


@pytest.mark.django_db
def test_restore_requires_login_when_credentials_changed(
    django_capture_on_commit_callbacks: Any,
) -> None:
    actor = admin()
    with django_capture_on_commit_callbacks(execute=True):
        enable_qa_dev_mode(EnableQaDevModeCommand(actor=actor, repeatable_seed_snapshot=True))
    actor.set_password("test-only-new-password")
    actor.save(update_fields=["password"])
    caller = Client()
    caller.force_login(actor)
    response = caller.post(
        "/api/v1/qa/dev-mode/revert/",
        {"confirmation": "REVERT QA DB"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["requires_login"] is True
    assert caller.get("/api/v1/auth/me/").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("account_type", ["admin", "superadmin"])
def test_production_never_exposes_qa_controls(settings: Any, account_type: str) -> None:
    actor = admin()
    actor.account_type = account_type
    actor.is_superuser = account_type == "superadmin"
    actor.save(update_fields=["account_type", "is_superuser"])
    caller = Client()
    caller.force_login(actor)
    settings.ENVIRONMENT = "production"
    # Even a misconfigured explicit opt-in must not bypass the environment guard.
    settings.QA_DEV_MODE_ALLOWED = True
    assert caller.get("/api/v1/auth/me/").json()["qa_controls_available"] is False
    assert caller.get("/api/v1/qa/dev-mode/").status_code == 404
    for endpoint in ("enable", "snapshot", "advance", "revert"):
        assert (
            caller.post(
                f"/api/v1/qa/dev-mode/{endpoint}/", {}, content_type="application/json"
            ).status_code
            == 404
        )


@pytest.mark.django_db
def test_investors_and_restricted_admins_cannot_use_qa() -> None:
    actor = admin()
    caller = Client()
    caller.force_login(actor)
    assert caller.get("/api/v1/auth/me/").json()["qa_controls_available"] is True
    for account_type, status in (("admin", "restricted"), ("natural_person_lender", "active")):
        actor.account_type, actor.status = account_type, status
        actor.save(update_fields=["account_type", "status"])
        assert caller.get("/api/v1/qa/dev-mode/").status_code == 403
