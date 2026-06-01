"""Django settings for the BANXUM modular monolith."""

from __future__ import annotations

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, True),
    DJANGO_ALLOWED_HOSTS=(list[str], ["localhost", "127.0.0.1", "0.0.0.0"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-local-dev-key-change-me")
ENVIRONMENT = env("ENVIRONMENT", default="local")
IS_PRODUCTION = ENVIRONMENT == "production"

DEBUG = env.bool("DJANGO_DEBUG", default=not IS_PRODUCTION)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

PLATFORM_BRAND_NAME = env("PLATFORM_BRAND_NAME", default="BANXUM")
LEGAL_OPERATOR_NAME = env("LEGAL_OPERATOR_NAME", default="Garanta Finanzgruppe AG")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "backend.apps.platform_core",
    "backend.apps.accounts_auth",
    "backend.apps.kyc_compliance",
    "backend.apps.entities",
    "backend.apps.loans",
    "backend.apps.marketplace_primary",
    "backend.apps.ledger",
    "backend.apps.servicing",
    "backend.apps.secondary_market",
    "backend.apps.fx",
    "backend.apps.documents",
    "backend.apps.communications",
    "backend.apps.reporting",
    "backend.apps.admin_ops",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "backend" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.config.wsgi.application"
ASGI_APPLICATION = "backend.config.asgi.application"

DATABASE_URL = env("DATABASE_URL", default="")
if DATABASE_URL:
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("BUSINESS_TIMEZONE", default="Europe/Zurich")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts_auth.User"

SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=IS_PRODUCTION)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=IS_PRODUCTION)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", default="Lax")
CSRF_COOKIE_SAMESITE = env("CSRF_COOKIE_SAMESITE", default="Lax")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=IS_PRODUCTION)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000 if IS_PRODUCTION else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=IS_PRODUCTION,
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=IS_PRODUCTION)
if env.bool("DJANGO_USE_X_FORWARDED_PROTO", default=IS_PRODUCTION):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
TRUST_X_FORWARDED_FOR = env.bool("TRUST_X_FORWARDED_FOR", default=False)

REGISTRATION_TERMS_VERSION = env("REGISTRATION_TERMS_VERSION", default="registration-v1")
REGISTRATION_TERMS_HASH = env(
    "REGISTRATION_TERMS_HASH",
    default="3b0ba70e0b1d68a6acd2135c832cf114f6db2fb5c8896625c1f28f3ba7bd8dca",
)
AUTH_DELIVERY_SECRET_ENCRYPTION_KEY = env("AUTH_DELIVERY_SECRET_ENCRYPTION_KEY", default="")
AUTH_SECRET_DIGEST_PEPPER = env("AUTH_SECRET_DIGEST_PEPPER", default="")
AUTH_MAGIC_LINK_COOLDOWN_SECONDS = env.int("AUTH_MAGIC_LINK_COOLDOWN_SECONDS", default=60)
AUTH_MAGIC_LINK_HOURLY_LIMIT = env.int("AUTH_MAGIC_LINK_HOURLY_LIMIT", default=5)
AUTH_MAGIC_LINK_DAILY_LIMIT = env.int("AUTH_MAGIC_LINK_DAILY_LIMIT", default=20)
AUTH_REGISTRATION_COOLDOWN_SECONDS = env.int("AUTH_REGISTRATION_COOLDOWN_SECONDS", default=10)
AUTH_REGISTRATION_HOURLY_LIMIT = env.int("AUTH_REGISTRATION_HOURLY_LIMIT", default=20)
AUTH_REGISTRATION_DAILY_LIMIT = env.int("AUTH_REGISTRATION_DAILY_LIMIT", default=100)
AUTH_SENSITIVE_CODE_COOLDOWN_SECONDS = env.int(
    "AUTH_SENSITIVE_CODE_COOLDOWN_SECONDS",
    default=60,
)
PHONE_VERIFICATION_PROVIDER = env("PHONE_VERIFICATION_PROVIDER", default="mock")
AUTH_PHONE_VERIFICATION_TTL_SECONDS = env.int("AUTH_PHONE_VERIFICATION_TTL_SECONDS", default=600)
AUTH_PHONE_VERIFICATION_MAX_ATTEMPTS = env.int("AUTH_PHONE_VERIFICATION_MAX_ATTEMPTS", default=3)
AUTH_PHONE_VERIFICATION_COOLDOWN_SECONDS = env.int(
    "AUTH_PHONE_VERIFICATION_COOLDOWN_SECONDS",
    default=60,
)
AUTH_PHONE_VERIFICATION_HOURLY_LIMIT = env.int("AUTH_PHONE_VERIFICATION_HOURLY_LIMIT", default=5)
AUTH_PHONE_VERIFICATION_DAILY_LIMIT = env.int("AUTH_PHONE_VERIFICATION_DAILY_LIMIT", default=20)
AUTH_PHONE_VERIFICATION_CONFIRM_HOURLY_LIMIT = env.int(
    "AUTH_PHONE_VERIFICATION_CONFIRM_HOURLY_LIMIT",
    default=10,
)
AUTH_PHONE_VERIFICATION_CONFIRM_DAILY_LIMIT = env.int(
    "AUTH_PHONE_VERIFICATION_CONFIRM_DAILY_LIMIT",
    default=50,
)
DIDIT_ENVIRONMENT = env("DIDIT_ENVIRONMENT", default=ENVIRONMENT)
DIDIT_WORKFLOW_ID = env("DIDIT_WORKFLOW_ID", default="didit-natural-person-lender-v1")
DIDIT_MOCK_VERIFICATION_BASE_URL = env(
    "DIDIT_MOCK_VERIFICATION_BASE_URL",
    default="https://mock.didit.local/verify",
)
DIDIT_WEBHOOK_SECRET = env("DIDIT_WEBHOOK_SECRET", default="")
DIDIT_WEBHOOK_REQUIRE_SIGNATURE = env.bool(
    "DIDIT_WEBHOOK_REQUIRE_SIGNATURE",
    default=ENVIRONMENT != "local",
)
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHE_URL = env(
    "CACHE_URL",
    default=REDIS_URL if ENVIRONMENT in {"staging", "production"} else "",
)
if CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": CACHE_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "banxum-local-cache",
        }
    }

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "BANXUM API",
    "DESCRIPTION": "Internal API for BANXUM investor and admin portals.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
