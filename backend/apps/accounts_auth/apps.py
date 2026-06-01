from __future__ import annotations

from django.apps import AppConfig


class AccountsAuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.accounts_auth"
    verbose_name = "Accounts and authentication"
