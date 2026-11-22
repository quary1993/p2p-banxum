"""IP of Webby-Soft SRL. 18.5 (D1, E-05): the password rules, following NIST SP 800-63B-4.

12 to 128 characters, no forced mix of character types, no forced periodic change. Refused: a
very common password (Django's list of about 20,000) and a password found in known data breaches
(Have I Been Pwned range API: only the first 5 characters of the SHA-1 hash leave the server;
k-anonymity). When the breach service cannot be reached, the common list still applies and the
event is logged.
"""

from __future__ import annotations

import hashlib
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.contrib.auth.password_validation import CommonPasswordValidator
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

MIN_LENGTH = 12
MAX_LENGTH = 128
HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/"


class PasswordPolicyError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _breach_count(password: str) -> int | None:
    """Times the password appears in known breaches, or None when the service is unavailable."""
    if not bool(getattr(settings, "AUTH_PASSWORD_BREACH_CHECK_ENABLED", True)):
        return 0
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()  # noqa: S324 - HIBP API
    prefix, suffix = digest[:5], digest[5:]
    request = urllib.request.Request(
        HIBP_RANGE_URL + prefix,
        headers={"Add-Padding": "true", "User-Agent": "Banxum password check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:  # noqa: S310 - fixed URL
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        logger.warning("password_breach_check_unavailable")
        return None
    for line in body.splitlines():
        candidate, _, count = line.partition(":")
        if candidate.strip().upper() == suffix:
            try:
                return int(count.strip() or "0")
            except ValueError:
                return 1
    return 0


def validate_new_password(password: str, *, email: str = "") -> None:
    if len(password) < MIN_LENGTH:
        raise PasswordPolicyError(
            f"Use at least {MIN_LENGTH} characters.", code="password_too_short"
        )
    if len(password) > MAX_LENGTH:
        raise PasswordPolicyError(f"Use at most {MAX_LENGTH} characters.", code="password_too_long")
    if email and password.strip().lower() == email.strip().lower():
        raise PasswordPolicyError("Do not use your email address.", code="password_is_email")
    try:
        CommonPasswordValidator().validate(password)
    except ValidationError as exc:
        raise PasswordPolicyError(
            "This password is too common. Choose another one.", code="password_common"
        ) from exc
    count = _breach_count(password)
    if count:
        raise PasswordPolicyError(
            "This password appears in known data breaches. Choose another one.",
            code="password_breached",
        )


class PlatformPasswordValidator:
    """Audit S4-5: the same rules for every Django password path (admin creation,
    ``createsuperuser``, forms). It is the only entry of ``AUTH_PASSWORD_VALIDATORS``, so no
    path can use other rules, such as a forced mix of character types."""

    def validate(self, password: str, user: object | None = None) -> None:
        try:
            validate_new_password(password, email=str(getattr(user, "email", "") or ""))
        except PasswordPolicyError as exc:
            raise ValidationError(str(exc), code=exc.code) from exc

    def get_help_text(self) -> str:
        return (
            f"Use {MIN_LENGTH} to {MAX_LENGTH} characters. Very common passwords and "
            "passwords from known data breaches are refused."
        )
