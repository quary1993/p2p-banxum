"""Deployment wiring for durable QA restore points."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_compose_shares_durable_qa_snapshot_storage() -> None:
    compose = yaml.safe_load((REPO_ROOT / "infra/deploy/docker-compose.yml").read_text())
    source = "${QA_DEV_MODE_SNAPSHOT_DIR:-qa_snapshot_data}:/app/qa-dev-snapshots"
    permission_source = "${QA_DEV_MODE_SNAPSHOT_DIR:-qa_snapshot_data}:/qa-dev-snapshots"
    backend = compose["services"]["backend"]
    permissions = compose["services"]["qa-snapshot-permissions"]

    assert backend["environment"]["QA_DEV_MODE_SNAPSHOT_DIR"] == "/app/qa-dev-snapshots"
    assert source in backend["volumes"]
    assert permission_source in permissions["volumes"]
    assert backend["depends_on"]["qa-snapshot-permissions"]["condition"] == (
        "service_completed_successfully"
    )
    assert "qa_snapshot_data" in compose["volumes"]


def test_reset_wrapper_verifies_the_shared_seed_before_restart() -> None:
    wrapper = (REPO_ROOT / "infra/deploy/reset_qa_environment.py").read_text()
    reset = wrapper.index('"backend/manage.py", "reset_qa_dataset"')
    verify = wrapper.index('"check_qa_restore_points"')
    restart = wrapper.index('run(["docker", "start", backend, frontend])')

    assert reset < verify < restart


def test_staging_seed_workflow_uses_private_inputs_and_guard_phrase() -> None:
    workflow = (REPO_ROOT / ".github/workflows/rebuild-staging-qa-seed.yml").read_text()

    assert "BANXUM_QA_RESET_ACTOR_EMAIL" in workflow
    assert "BANXUM_QA_REGRESSION_ACCOUNTS_JSON" in workflow
    assert 'test "$CONFIRMATION" = "REBUILD STAGING QA SEED"' in workflow
    assert "--environment staging" in workflow
    assert "--allow-production" not in workflow
