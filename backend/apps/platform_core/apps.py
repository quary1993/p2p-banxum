from __future__ import annotations

from django.apps import AppConfig


class PlatformCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.platform_core"
    verbose_name = "Platform core"

    def ready(self) -> None:
        from backend.apps.platform_core import checks  # noqa: F401
