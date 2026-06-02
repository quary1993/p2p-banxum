from __future__ import annotations

from django.apps import apps


def test_domain_apps_are_installed() -> None:
    expected_app_labels = {
        "platform_core",
        "accounts_auth",
        "kyc_compliance",
        "entities",
        "loans",
        "marketplace_primary",
        "holdings",
        "ledger",
        "servicing",
        "secondary_market",
        "fx",
        "documents",
        "communications",
        "reporting",
        "admin_ops",
    }

    installed_labels = {app_config.label for app_config in apps.get_app_configs()}

    assert expected_app_labels <= installed_labels
