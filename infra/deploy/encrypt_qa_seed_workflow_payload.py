#!/usr/bin/env python3
"""Encrypt or decrypt the staging QA seed rebuild workflow payload."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"BANXUM-QA-SEED\x01"
ASSOCIATED_DATA = b"banxum-staging-qa-seed-v1"
KEY_INFO = b"banxum-staging-qa-seed-payload"
EPHEMERAL_KEY_BYTES = 32
SALT_BYTES = 16
NONCE_BYTES = 12


def private_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if resolved.stat().st_mode & 0o077:
        raise RuntimeError(f"{label} must have private 0600 permissions.")
    return resolved


def x25519_public_from_ed25519(key: ed25519.Ed25519PublicKey) -> x25519.X25519PublicKey:
    encoded = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    y = int.from_bytes(encoded, "little") & ((1 << 255) - 1)
    prime = (1 << 255) - 19
    if y >= prime or y == 1:
        raise RuntimeError("Invalid Ed25519 deployment public key.")
    montgomery_u = ((1 + y) * pow(1 - y, prime - 2, prime)) % prime
    return x25519.X25519PublicKey.from_public_bytes(montgomery_u.to_bytes(32, "little"))


def x25519_private_from_ed25519(key: ed25519.Ed25519PrivateKey) -> x25519.X25519PrivateKey:
    seed = key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    scalar = bytearray(hashlib.sha512(seed).digest()[:32])
    scalar[0] &= 248
    scalar[31] &= 127
    scalar[31] |= 64
    return x25519.X25519PrivateKey.from_private_bytes(bytes(scalar))


def derive_key(shared_secret: bytes, salt: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=KEY_INFO,
    ).derive(shared_secret)


def encrypt_payload(payload: bytes, public_key_path: Path) -> str:
    loaded = serialization.load_ssh_public_key(public_key_path.read_bytes())
    if not isinstance(loaded, ed25519.Ed25519PublicKey):
        raise RuntimeError("The deployment public key must be Ed25519.")
    recipient = x25519_public_from_ed25519(loaded)
    ephemeral = x25519.X25519PrivateKey.generate()
    ephemeral_public = ephemeral.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    key = derive_key(ephemeral.exchange(recipient), salt)
    ciphertext = AESGCM(key).encrypt(nonce, payload, ASSOCIATED_DATA)
    return base64.b64encode(MAGIC + ephemeral_public + salt + nonce + ciphertext).decode("ascii")


def decrypt_payload(encoded: bytes, private_key_path: Path) -> bytes:
    loaded = serialization.load_ssh_private_key(
        private_file(private_key_path, "Deployment key").read_bytes(), password=None
    )
    if not isinstance(loaded, ed25519.Ed25519PrivateKey):
        raise RuntimeError("The deployment private key must be Ed25519.")
    try:
        envelope = base64.b64decode(encoded.strip(), validate=True)
    except ValueError as exc:
        raise RuntimeError("Invalid encrypted QA seed payload encoding.") from exc
    header_bytes = len(MAGIC) + EPHEMERAL_KEY_BYTES + SALT_BYTES + NONCE_BYTES
    if len(envelope) <= header_bytes or not envelope.startswith(MAGIC):
        raise RuntimeError("Invalid encrypted QA seed payload envelope.")
    cursor = len(MAGIC)
    ephemeral_public = envelope[cursor : cursor + EPHEMERAL_KEY_BYTES]
    cursor += EPHEMERAL_KEY_BYTES
    salt = envelope[cursor : cursor + SALT_BYTES]
    cursor += SALT_BYTES
    nonce = envelope[cursor : cursor + NONCE_BYTES]
    cursor += NONCE_BYTES
    ciphertext = envelope[cursor:]
    recipient = x25519_private_from_ed25519(loaded)
    shared_secret = recipient.exchange(x25519.X25519PublicKey.from_public_bytes(ephemeral_public))
    return AESGCM(derive_key(shared_secret, salt)).decrypt(nonce, ciphertext, ASSOCIATED_DATA)


def encrypt_command(args: argparse.Namespace) -> None:
    if "@" not in args.actor_email:
        raise RuntimeError("The QA reset actor must be an email address.")
    accounts_path = private_file(args.regression_accounts, "Regression account mapping")
    accounts = json.loads(accounts_path.read_text(encoding="utf-8"))
    required = {"admin", "user1", "user2", "user3"}
    if (
        not isinstance(accounts, dict)
        or set(accounts) != required
        or not all(isinstance(value, str) and "@" in value for value in accounts.values())
    ):
        raise RuntimeError("Invalid QA regression account mapping.")
    payload = json.dumps(
        {"actor_email": args.actor_email, "accounts": accounts},
        separators=(",", ":"),
    ).encode()
    print(encrypt_payload(payload, args.deployment_public_key.expanduser().resolve(strict=True)))


def decrypt_command(args: argparse.Namespace) -> None:
    sys.stdout.buffer.write(decrypt_payload(sys.stdin.buffer.read(), args.deployment_key))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    encrypt = commands.add_parser("encrypt")
    encrypt.add_argument("--actor-email", required=True)
    encrypt.add_argument("--regression-accounts", required=True, type=Path)
    encrypt.add_argument("--deployment-public-key", required=True, type=Path)
    encrypt.set_defaults(handler=encrypt_command)
    decrypt = commands.add_parser("decrypt")
    decrypt.add_argument("--deployment-key", required=True, type=Path)
    decrypt.set_defaults(handler=decrypt_command)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
