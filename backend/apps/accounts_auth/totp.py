"""IP of Webby-Soft SRL. 18.5: time-based one-time passwords (RFC 6238, RFC 4226).

SHA-1, 6 digits, 30-second steps, one step of tolerance either side: the defaults of common
authenticator apps (for example Google Authenticator). The step of an accepted code is returned so
the caller can refuse the same or an older step again (replay).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
import urllib.parse

DIGITS = 6
STEP_SECONDS = 30
WINDOW_STEPS = 1
SECRET_BYTES = 20


def new_secret() -> str:
    """A random base32 secret (160 bits, no padding)."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode("ascii").rstrip("=")


def _secret_bytes(secret: str) -> bytes:
    cleaned = secret.replace(" ", "").upper()
    padding = "=" * (-len(cleaned) % 8)
    return base64.b32decode(cleaned + padding, casefold=True)


def code_at_step(secret: str, step: int) -> str:
    digest = hmac.new(_secret_bytes(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % (10**DIGITS):0{DIGITS}d}"


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def verify(
    secret: str, code: str, *, last_used_step: int = 0, now: float | None = None
) -> int | None:
    """The step of a valid, unused code, or None."""
    candidate = "".join(ch for ch in str(code) if ch.isdigit())
    if len(candidate) != DIGITS:
        return None
    step = current_step(now)
    for offset in range(-WINDOW_STEPS, WINDOW_STEPS + 1):
        checked = step + offset
        if checked <= last_used_step:
            continue
        if hmac.compare_digest(code_at_step(secret, checked), candidate):
            return checked
    return None


def provisioning_uri(*, secret: str, account_name: str, issuer: str) -> str:
    """The otpauth:// address that authenticator apps read from a QR code."""
    label = urllib.parse.quote(f"{issuer}:{account_name}")
    query = urllib.parse.urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": DIGITS,
            "period": STEP_SECONDS,
        }
    )
    return f"otpauth://totp/{label}?{query}"
