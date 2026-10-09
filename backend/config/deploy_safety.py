"""Start-up guards for every environment except ``local``.

Settings fail closed outside local development: a staging or production process
refuses to start with the development secret key or without its own secrets for
login-link encryption and digest peppering (audit A-51 / SECCODE-07). The checks
are plain functions so the settings module and tests can call them directly.
"""

# IP of Webby-Soft SRL.

from __future__ import annotations

import base64
import binascii

from django.core.exceptions import ImproperlyConfigured

DEV_SECRET_KEY = "unsafe-local-dev-key-change-me"
INSECURE_SECRET_KEY_PREFIXES = ("unsafe-", "django-insecure-", "change-me", "changeme")
MIN_SECRET_KEY_LENGTH = 50
MIN_SECRET_KEY_UNIQUE_CHARACTERS = 5
MIN_DIGEST_PEPPER_LENGTH = 32


def secret_key_problem(secret_key: str) -> str:
    """Return why ``secret_key`` is unsafe outside local development, or ``""``."""

    value = secret_key.strip()
    if not value:
        return "DJANGO_SECRET_KEY is not set."
    if value == DEV_SECRET_KEY or value.lower().startswith(INSECURE_SECRET_KEY_PREFIXES):
        return "DJANGO_SECRET_KEY is a development placeholder."
    if len(value) < MIN_SECRET_KEY_LENGTH:
        return f"DJANGO_SECRET_KEY must have at least {MIN_SECRET_KEY_LENGTH} characters."
    if len(set(value)) < MIN_SECRET_KEY_UNIQUE_CHARACTERS:
        return "DJANGO_SECRET_KEY is not random enough."
    return ""


def delivery_key_problem(key: str) -> str:
    """Return why the login-secret encryption key is unusable, or ``""``.

    The key must be a Fernet key: 32 random bytes in URL-safe base64 (44 characters).
    """

    value = key.strip()
    if not value:
        return "AUTH_DELIVERY_SECRET_ENCRYPTION_KEY is not set."
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
    except (binascii.Error, ValueError, UnicodeEncodeError):
        return "AUTH_DELIVERY_SECRET_ENCRYPTION_KEY is not URL-safe base64."
    if len(raw) != 32:
        return "AUTH_DELIVERY_SECRET_ENCRYPTION_KEY must encode exactly 32 bytes (a Fernet key)."
    return ""


def digest_pepper_problem(pepper: str) -> str:
    """Return why the login-secret digest pepper is unsafe, or ``""``."""

    value = pepper.strip()
    if not value:
        return "AUTH_SECRET_DIGEST_PEPPER is not set."
    if len(value) < MIN_DIGEST_PEPPER_LENGTH:
        return (
            f"AUTH_SECRET_DIGEST_PEPPER must have at least {MIN_DIGEST_PEPPER_LENGTH} characters."
        )
    return ""


def non_local_secret_problems(
    *,
    secret_key: str,
    delivery_key: str,
    digest_pepper: str,
) -> list[str]:
    problems = [
        secret_key_problem(secret_key),
        delivery_key_problem(delivery_key),
        digest_pepper_problem(digest_pepper),
    ]
    if digest_pepper.strip() and digest_pepper.strip() == secret_key.strip():
        problems.append("AUTH_SECRET_DIGEST_PEPPER must differ from DJANGO_SECRET_KEY.")
    return [problem for problem in problems if problem]


def require_non_local_secrets(
    *,
    environment: str,
    secret_key: str,
    delivery_key: str,
    digest_pepper: str,
) -> None:
    """Refuse to start outside local development without real secrets."""

    if environment == "local":
        return
    problems = non_local_secret_problems(
        secret_key=secret_key,
        delivery_key=delivery_key,
        digest_pepper=digest_pepper,
    )
    if problems:
        raise ImproperlyConfigured(
            f"ENVIRONMENT={environment} refuses to start: "
            + " ".join(problems)
            + " See .env.example for how to generate each value."
        )
