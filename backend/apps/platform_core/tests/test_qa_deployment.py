"""Deployment wiring for durable QA restore points."""

import json
import subprocess
import sys
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
    reset = wrapper.index('"--maintenance-confirmed"')
    verify = wrapper.index('"check_qa_restore_points"')
    restart = wrapper.index('run(["docker", "start", backend, frontend])')

    assert reset < verify < restart
    assert "cat > /tmp/qa-regression-accounts.json" in wrapper
    assert "/qa-regression-accounts.json:ro" not in wrapper
    assert '"--verified-backup-path"' in wrapper
    assert '"--verified-backup-sha256"' in wrapper
    assert "/qa-reset-backups" not in wrapper


def test_staging_seed_workflow_uses_private_inputs_and_guard_phrase() -> None:
    workflow = (REPO_ROOT / ".github/workflows/rebuild-staging-qa-seed.yml").read_text()

    assert "encrypted_seed_payload" in workflow
    assert "encrypt_qa_seed_workflow_payload.py decrypt" in workflow
    assert "actor_email" in workflow
    assert "accounts" in workflow
    assert 'test "$CONFIRMATION" = "REBUILD STAGING QA SEED"' in workflow
    assert "--environment staging" in workflow
    assert "--allow-production" not in workflow


def test_qa_seed_payload_public_key_encryption_round_trip(tmp_path: Path) -> None:
    private_key = tmp_path / "deploy-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)],
        check=True,
    )
    accounts = tmp_path / "accounts.json"
    account_values = {
        "admin": "admin@example.invalid",
        "user1": "user1@example.invalid",
        "user2": "user2@example.invalid",
        "user3": "user3@example.invalid",
    }
    accounts.write_text(json.dumps(account_values), encoding="utf-8")
    accounts.chmod(0o600)
    helper = REPO_ROOT / "infra/deploy/encrypt_qa_seed_workflow_payload.py"
    encrypted = subprocess.check_output(
        [
            sys.executable,
            str(helper),
            "encrypt",
            "--actor-email",
            "superadmin@example.invalid",
            "--regression-accounts",
            str(accounts),
            "--deployment-public-key",
            f"{private_key}.pub",
        ]
    )
    decrypted = subprocess.check_output(
        [
            sys.executable,
            str(helper),
            "decrypt",
            "--deployment-key",
            str(private_key),
        ],
        input=encrypted,
    )

    assert json.loads(decrypted) == {
        "actor_email": "superadmin@example.invalid",
        "accounts": account_values,
    }
