#!/usr/bin/env python3
"""IP of Webby-Soft SRL. Explicit host-side QA reset with downtime and private backups."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from uuid import UUID


def run(args: list[str], **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def container_config(name: str) -> dict:
    return json.loads(subprocess.check_output(["docker", "inspect", name]))[0]


def health(port: int, environment: str) -> None:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/v1/health/",
        headers={"X-Forwarded-Proto": "https"},
    )
    for _attempt in range(30):
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.load(response)
            if payload.get("status") == "ok" and payload.get("environment") == environment:
                return
        except (OSError, ValueError):
            pass
        time.sleep(2)
    raise RuntimeError(f"{environment} did not return a healthy backend response.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", required=True, choices=("staging", "production"))
    parser.add_argument("--actor-email", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--allow-production", action="store_true")
    args = parser.parse_args()
    environment = args.environment
    project = "banxum_prod" if environment == "production" else "banxum_staging"
    backend = f"{project}-backend-1"
    frontend = f"{project}-frontend-1"
    postgres = f"{project}-postgres-1"
    app_dir = Path(f"/opt/banxum/{environment}/app")
    backup_dir = app_dir.parent / "backups"
    port = 8082 if environment == "production" else 8081
    config = container_config(backend)
    env = dict(item.split("=", 1) for item in config["Config"]["Env"] if "=" in item)
    if env.get("ENVIRONMENT") != environment:
        raise RuntimeError("Backend container environment does not match target.")
    if not args.execute:
        run(
            ["docker", "exec", backend, ".venv/bin/python", "backend/manage.py", "reset_qa_dataset"]
        )
        return
    run_id = UUID(args.run_id)
    required = f"RESET QA DATA {environment} {env.get('PUBLIC_APP_BASE_URL', '').rstrip('/')}"
    if args.confirm != required or not args.actor_email:
        raise RuntimeError("Provide the exact confirmation from the preview and an admin actor.")
    if environment == "production" and not args.allow_production:
        raise RuntimeError("Production requires --allow-production.")
    for name in (backend, frontend):
        if not container_config(name)["State"]["Running"]:
            raise RuntimeError(f"{name} must be running before starting the maintenance wrapper.")
    health(port, environment)
    prior = json.loads(
        subprocess.check_output(
            [
                "docker",
                "exec",
                backend,
                ".venv/bin/python",
                "backend/manage.py",
                "reset_qa_dataset",
                "--run-id",
                str(run_id),
            ]
        )
    )
    if prior["already_completed"]:
        print(json.dumps({"already_completed": True, "result": prior["completed_reset"]}))
        return
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if backup_dir.is_symlink() or backup_dir.stat().st_mode & 0o077:
        raise RuntimeError("Backup directory must have private 0700 permissions.")
    db_config = container_config(postgres)
    db_env = dict(item.split("=", 1) for item in db_config["Config"]["Env"] if "=" in item)
    compose = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--env-file",
        "infra/deploy/.env",
        "-f",
        "infra/deploy/docker-compose.yml",
    ]
    dump_path = backup_dir / f"pre-qa-reset-{run_id}.dump"
    if dump_path.exists():
        raise RuntimeError(
            "An unfinished attempt already has a backup for this UUID. Inspect its logs and "
            "QaDatasetReset before starting a new attempt with a new UUID; keep the old backup."
        )
    maintenance_started = False
    try:
        maintenance_started = True
        # Stop only this application's writer and frontend, never the database or other projects.
        run(["docker", "stop", "--time", "30", frontend, backend])
        if not dump_path.exists():
            with dump_path.open("xb") as output:
                os.chmod(dump_path, 0o600)
                run(
                    [
                        "docker",
                        "exec",
                        postgres,
                        "pg_dump",
                        "-U",
                        db_env["POSTGRES_USER"],
                        "-d",
                        db_env["POSTGRES_DB"],
                        "-Fc",
                    ],
                    stdout=output,
                )
        with dump_path.open("rb") as source:
            toc = subprocess.check_output(
                ["docker", "exec", "-i", postgres, "pg_restore", "--list"], stdin=source
            )
        if b"accounts_auth_user" not in toc or b"platform_core_auditevent" not in toc:
            raise RuntimeError("Database backup validation did not find protected tables.")
        verification_db = f"qa_restore_{run_id.hex}"
        db_user = db_env["POSTGRES_USER"]
        run(["docker", "exec", postgres, "createdb", "-U", db_user, verification_db])
        try:
            with dump_path.open("rb") as source:
                run(
                    [
                        "docker",
                        "exec",
                        "-i",
                        postgres,
                        "pg_restore",
                        "--exit-on-error",
                        "--no-owner",
                        "-U",
                        db_user,
                        "-d",
                        verification_db,
                    ],
                    stdin=source,
                )
            counts_query = (
                "SELECT (SELECT count(*) FROM accounts_auth_user), "
                "(SELECT count(*) FROM platform_core_auditevent)"
            )
            expected = subprocess.check_output(
                [
                    "docker",
                    "exec",
                    postgres,
                    "psql",
                    "-U",
                    db_user,
                    "-d",
                    db_env["POSTGRES_DB"],
                    "-Atc",
                    counts_query,
                ]
            )
            restored = subprocess.check_output(
                [
                    "docker",
                    "exec",
                    postgres,
                    "psql",
                    "-U",
                    db_user,
                    "-d",
                    verification_db,
                    "-Atc",
                    counts_query,
                ]
            )
            if expected != restored:
                raise RuntimeError("Restored backup account/audit counts do not match the source.")
        finally:
            run(["docker", "exec", postgres, "dropdb", "-U", db_user, verification_db])
        digest = hashlib.sha256(dump_path.read_bytes()).hexdigest()
        print(json.dumps({"backup": str(dump_path), "sha256": digest}), flush=True)
        command = compose + [
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "-e",
            "QA_DATA_RESET_ALLOWED=true",
            "-v",
            f"{backup_dir}:/qa-reset-backups",
            "--entrypoint",
            ".venv/bin/python",
            "backend",
            "backend/manage.py",
            "reset_qa_dataset",
            "--execute",
            "--actor-email",
            args.actor_email,
            "--run-id",
            str(run_id),
            "--expected-environment",
            environment,
            "--confirm",
            args.confirm,
            "--backup-directory",
            "/qa-reset-backups",
            "--maintenance-confirmed",
        ]
        if environment == "production":
            command.append("--allow-production")
        run(command, cwd=app_dir)
    finally:
        if maintenance_started:
            run(["docker", "start", backend, frontend])
            health(port, environment)
    print(json.dumps({"environment": environment, "reset_id": str(run_id), "health": "ok"}))


if __name__ == "__main__":
    main()
