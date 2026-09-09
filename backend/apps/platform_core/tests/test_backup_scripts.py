from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[4] / "infra" / "deploy"


@pytest.fixture
def backup_env(tmp_path: Path) -> dict[str, str]:
    commands = {
        "flock": "pass",
        "docker": "print('archive' if 'pg_restore' not in sys.argv else '')",
        "sha256sum": """
import hashlib
if '--check' in sys.argv:
    digest, filename = Path(sys.argv[-1]).read_text().strip().split('  ', 1)
    sys.exit(0 if hashlib.sha256(Path(filename).read_bytes()).hexdigest() == digest else 1)
filename = sys.argv[-1]
print(hashlib.sha256(Path(filename).read_bytes()).hexdigest() + '  ' + filename)
""",
        "stat": """
p = Path(sys.argv[-1]).stat()
print(int(p.st_mtime) if sys.argv[-2] == '%Y' else p.st_size)
""",
        "xargs": """
paths = [Path(p.decode()) for p in sys.stdin.buffer.read().split(b'\\0') if p]
for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
    print(path)
""",
        "aws": """
remote = Path(os.environ['TEST_REMOTE'])
if os.environ.get('TEST_UPLOAD_FAIL') == 'true':
    sys.exit(1)
if sys.argv[1:3] == ['s3api', 'head-object']:
    key = sys.argv[sys.argv.index('--key') + 1]
    print((remote / Path(key).name).stat().st_size)
elif sys.argv[1:3] == ['s3', 'cp']:
    source, target = sys.argv[3:5]
    if source.startswith('s3://'):
        sys.stdout.write((remote / Path(source).name).read_text())
    else:
        (remote / Path(target).name).write_bytes(Path(source).read_bytes())
else:
    sys.exit(2)
""",
    }
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, body in commands.items():
        path = bindir / name
        path.write_text(f"#!{sys.executable}\nimport os, sys\nfrom pathlib import Path\n{body}\n")
        path.chmod(0o755)
    compose = tmp_path / "compose.yml"
    compose.touch()
    envfile = tmp_path / "env"
    envfile.touch()
    remote = tmp_path / "remote"
    remote.mkdir()
    return {
        **os.environ,
        "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        "BANXUM_COMPOSE_FILE": str(compose),
        "BANXUM_ENV_FILE": str(envfile),
        "BANXUM_COMPOSE_PROJECT": "banxum_test",
        "BANXUM_BACKUP_DIR": str(tmp_path / "backups"),
        "BANXUM_BACKUP_REQUIRE_OFFSITE": "true",
        "BANXUM_BACKUP_S3_URI": "s3://test/backup",
        "TEST_REMOTE": str(remote),
    }


def _run(script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPTS / script)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_backup_monitor_requires_completed_upload(backup_env: dict[str, str]) -> None:
    failed = _run("backup_postgres.sh", {**backup_env, "TEST_UPLOAD_FAIL": "true"})
    assert failed.returncode != 0
    result = _run("check_backup_freshness.sh", backup_env)
    assert result.returncode != 0
    assert "upload was not completed" in result.stderr


def test_backup_monitor_verifies_offsite_objects(backup_env: dict[str, str]) -> None:
    backup = _run("backup_postgres.sh", backup_env)
    assert backup.returncode == 0, backup.stderr
    result = _run("check_backup_freshness.sh", backup_env)
    assert result.returncode == 0, result.stderr
    remote_dump = next(Path(backup_env["TEST_REMOTE"]).glob("*.dump"))
    remote_dump.write_bytes(b"wrong size")
    assert _run("check_backup_freshness.sh", backup_env).returncode != 0
    remote_dump.unlink()
    assert _run("check_backup_freshness.sh", backup_env).returncode != 0


def test_backup_monitor_rejects_wrong_checksum(backup_env: dict[str, str]) -> None:
    assert _run("backup_postgres.sh", backup_env).returncode == 0
    next(Path(backup_env["TEST_REMOTE"]).glob("*.sha256")).write_text("wrong checksum")
    assert _run("check_backup_freshness.sh", backup_env).returncode != 0
