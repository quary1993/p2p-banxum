"""Factory helpers for fx tests."""

from __future__ import annotations

from backend.apps.platform_core.models import PlatformSetting


def set_fx_enabled(enabled: bool) -> None:
    """Switch currency exchange on or off without an audit record (test setup only)."""
    PlatformSetting.objects.update_or_create(
        key="fx.enabled",
        defaults={"value": enabled, "value_type": "boolean"},
    )
