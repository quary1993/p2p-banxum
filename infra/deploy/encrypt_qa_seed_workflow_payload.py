#!/usr/bin/env python3
"""Create the private payload for the staging QA seed rebuild workflow."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def private_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if resolved.stat().st_mode & 0o077:
        raise RuntimeError(f"{label} must have private 0600 permissions.")
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor-email", required=True)
    parser.add_argument("--regression-accounts", required=True, type=Path)
    parser.add_argument("--deployment-key", required=True, type=Path)
    args = parser.parse_args()

    if "@" not in args.actor_email:
        raise RuntimeError("The QA reset actor must be an email address.")
    accounts_path = private_file(args.regression_accounts, "Regression account mapping")
    deployment_key = private_file(args.deployment_key, "Deployment key")
    accounts = json.loads(accounts_path.read_text(encoding="utf-8"))
    required = {"admin", "user1", "user2", "user3"}
    if (
        not isinstance(accounts, dict)
        or set(accounts) != required
        or not all(isinstance(value, str) and "@" in value for value in accounts.values())
    ):
        raise RuntimeError("Invalid QA regression account mapping.")

    key_lines = [
        line.rstrip("\r")
        for line in deployment_key.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not key_lines:
        raise RuntimeError("The deployment key is empty.")
    environment = os.environ.copy()
    environment["QA_SEED_PASSPHRASE"] = "\n".join(key_lines)
    payload = json.dumps(
        {"actor_email": args.actor_email, "accounts": accounts},
        separators=(",", ":"),
    ).encode()
    result = subprocess.run(
        [
            "openssl",
            "enc",
            "-aes-256-cbc",
            "-salt",
            "-pbkdf2",
            "-iter",
            "200000",
            "-a",
            "-A",
            "-pass",
            "env:QA_SEED_PASSPHRASE",
        ],
        check=True,
        input=payload,
        stdout=subprocess.PIPE,
        env=environment,
    )
    print(result.stdout.decode("ascii"))


if __name__ == "__main__":
    main()
