"""Settings fail closed outside local development (audit 2026-10-09, A-51 / A-52).

Before: staging defaulted to DEBUG on, insecure cookies and no HTTPS redirect/HSTS,
the secret key fell back to the development key, the login-secret encryption key and
pepper fell back to the secret key, and the Django admin could be mounted.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from django.core.checks import run_checks
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from backend.config.deploy_safety import DEV_SECRET_KEY, require_non_local_secrets
from backend.config.error_reporting import SettingsMaskingExceptionReporterFilter

REPO_ROOT = Path(__file__).resolve().parents[4]
GOOD_SECRET_KEY = "k" + "x7Qp2Lm9Zr4Tb8Wn1Vc6Yd3Hf5Jg0Ks" * 2
GOOD_DELIVERY_KEY = Fernet.generate_key().decode("ascii")
GOOD_PEPPER = "pepper-" + "a1b2c3d4e5f6g7h8i9j0" * 2

PROBE = """
import json
import django
django.setup()
from django.conf import settings
from django.urls import Resolver404, resolve
try:
    resolve("/admin/django/login/")
    admin_mounted = True
except Resolver404:
    admin_mounted = False
print(json.dumps({
    "DEBUG": settings.DEBUG,
    "SESSION_COOKIE_SECURE": settings.SESSION_COOKIE_SECURE,
    "CSRF_COOKIE_SECURE": settings.CSRF_COOKIE_SECURE,
    "SECURE_SSL_REDIRECT": settings.SECURE_SSL_REDIRECT,
    "SECURE_HSTS_SECONDS": settings.SECURE_HSTS_SECONDS,
    "SECURE_PROXY_SSL_HEADER": list(getattr(settings, "SECURE_PROXY_SSL_HEADER", None) or []),
    "DJANGO_ADMIN_ENABLED": settings.DJANGO_ADMIN_ENABLED,
    "admin_mounted": admin_mounted,
}))
"""


def _run_settings(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    clean_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(REPO_ROOT),
        "DJANGO_SETTINGS_MODULE": "backend.config.settings",
        "DATABASE_URL": "sqlite:///:memory:",
        **env,
    }
    return subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        env=clean_env,
        cwd=str(REPO_ROOT),
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize(
    ("secret_key", "delivery_key", "pepper", "problem"),
    [
        (DEV_SECRET_KEY, GOOD_DELIVERY_KEY, GOOD_PEPPER, "development placeholder"),
        ("", GOOD_DELIVERY_KEY, GOOD_PEPPER, "DJANGO_SECRET_KEY is not set"),
        ("short-but-random-1234", GOOD_DELIVERY_KEY, GOOD_PEPPER, "at least 50"),
        (GOOD_SECRET_KEY, "", GOOD_PEPPER, "AUTH_DELIVERY_SECRET_ENCRYPTION_KEY is not set"),
        (GOOD_SECRET_KEY, "not-a-fernet-key", GOOD_PEPPER, "AUTH_DELIVERY_SECRET_ENCRYPTION_KEY"),
        (GOOD_SECRET_KEY, GOOD_DELIVERY_KEY, "", "AUTH_SECRET_DIGEST_PEPPER is not set"),
        (GOOD_SECRET_KEY, GOOD_DELIVERY_KEY, "short", "AUTH_SECRET_DIGEST_PEPPER must have"),
        (GOOD_SECRET_KEY, GOOD_DELIVERY_KEY, GOOD_SECRET_KEY, "must differ"),
    ],
)
@pytest.mark.parametrize("environment", ["staging", "production", "qa"])
def test_non_local_environments_refuse_unsafe_secrets(
    environment: str,
    secret_key: str,
    delivery_key: str,
    pepper: str,
    problem: str,
) -> None:
    with pytest.raises(ImproperlyConfigured, match=problem):
        require_non_local_secrets(
            environment=environment,
            secret_key=secret_key,
            delivery_key=delivery_key,
            digest_pepper=pepper,
        )


def test_local_development_keeps_its_defaults() -> None:
    require_non_local_secrets(
        environment="local",
        secret_key=DEV_SECRET_KEY,
        delivery_key="",
        digest_pepper="",
    )


def test_real_secrets_pass() -> None:
    require_non_local_secrets(
        environment="staging",
        secret_key=GOOD_SECRET_KEY,
        delivery_key=GOOD_DELIVERY_KEY,
        digest_pepper=GOOD_PEPPER,
    )


def test_staging_process_refuses_to_start_with_the_development_key() -> None:
    result = _run_settings({"ENVIRONMENT": "staging", "DJANGO_SECRET_KEY": DEV_SECRET_KEY})

    assert result.returncode != 0
    assert "ENVIRONMENT=staging refuses to start" in result.stderr
    assert "AUTH_DELIVERY_SECRET_ENCRYPTION_KEY is not set" in result.stderr


def test_staging_defaults_are_safe_and_the_django_admin_is_never_mounted() -> None:
    result = _run_settings(
        {
            "ENVIRONMENT": "staging",
            "DJANGO_SECRET_KEY": GOOD_SECRET_KEY,
            "AUTH_DELIVERY_SECRET_ENCRYPTION_KEY": GOOD_DELIVERY_KEY,
            "AUTH_SECRET_DIGEST_PEPPER": GOOD_PEPPER,
            # Even an explicit request cannot mount the Django admin outside local.
            "DJANGO_ADMIN_ENABLED": "true",
        }
    )

    assert result.returncode == 0, result.stderr
    values = json.loads(result.stdout.strip().splitlines()[-1])
    assert values == {
        "DEBUG": False,
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
        "SECURE_SSL_REDIRECT": True,
        "SECURE_HSTS_SECONDS": 31536000,
        "SECURE_PROXY_SSL_HEADER": ["HTTP_X_FORWARDED_PROTO", "https"],
        "DJANGO_ADMIN_ENABLED": False,
        "admin_mounted": False,
    }


def test_local_defaults_stay_developer_friendly() -> None:
    result = _run_settings({"ENVIRONMENT": "local"})

    assert result.returncode == 0, result.stderr
    values = json.loads(result.stdout.strip().splitlines()[-1])
    assert values["DEBUG"] is True
    assert values["SESSION_COOKIE_SECURE"] is False
    assert values["admin_mounted"] is True


def _check_ids() -> set[str]:
    return {
        message.id
        for message in run_checks(include_deployment_checks=True)
        if message.id is not None
    }


def test_deploy_check_refuses_debug_outside_local(settings: Any) -> None:
    settings.ENVIRONMENT = "staging"
    settings.DEBUG = True

    assert "platform_core.E003" in _check_ids()

    settings.ENVIRONMENT = "local"
    assert "platform_core.E003" not in _check_ids()


def test_deploy_check_requires_the_proxy_count_behind_a_proxy(settings: Any) -> None:
    settings.ENVIRONMENT = "staging"
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    settings.TRUSTED_PROXY_COUNT = 0

    assert "platform_core.E004" in _check_ids()

    settings.TRUSTED_PROXY_COUNT = 2
    assert "platform_core.E004" not in _check_ids()


PROVIDER_CHECK_IDS = {
    "accounts_auth.E001",
    "communications.E001",
    "fx.E001",
    "kyc_compliance.E003",
}


def test_staging_may_run_mock_providers_but_production_may_not(settings: Any) -> None:
    # Staging sends no real email or SMS and makes no real provider calls (plan 19), and
    # QA mode needs the mock email provider; the deploy check at container start must
    # not stop such a staging process. Production still needs the real providers.
    settings.PHONE_VERIFICATION_PROVIDER = "mock"
    settings.COMMUNICATIONS_EMAIL_PROVIDER = "mock"
    settings.FX_RATE_PROVIDER = "mock"
    settings.DIDIT_SESSION_PROVIDER = "mock"
    settings.ENVIRONMENT = "staging"
    settings.IS_PRODUCTION = False
    assert not PROVIDER_CHECK_IDS & _check_ids()

    settings.ENVIRONMENT = "production"
    settings.IS_PRODUCTION = True
    assert PROVIDER_CHECK_IDS <= _check_ids()


def test_error_pages_mask_connection_strings(settings: Any) -> None:
    settings.DATABASE_URL = "postgres://banxum:FAKE_DB_PASSWORD@db:5432/banxum"
    settings.REDIS_URL = "redis://:FAKE_REDIS_PASSWORD@redis:6379/0"

    safe = SettingsMaskingExceptionReporterFilter().get_safe_settings()

    assert "FAKE_DB_PASSWORD" not in json.dumps(safe, default=str)
    assert "FAKE_REDIS_PASSWORD" not in json.dumps(safe, default=str)


def test_login_secret_crypto_has_no_fallback_outside_local() -> None:
    from backend.apps.accounts_auth.crypto import digest_secret, encrypt_delivery_secret

    with override_settings(ENVIRONMENT="staging", AUTH_DELIVERY_SECRET_ENCRYPTION_KEY=""):
        with pytest.raises(ImproperlyConfigured):
            encrypt_delivery_secret("token")
    with override_settings(ENVIRONMENT="staging", AUTH_SECRET_DIGEST_PEPPER=""):
        with pytest.raises(ImproperlyConfigured):
            digest_secret("token")
