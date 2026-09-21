from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from django.db import models

from backend.apps.platform_core.domain.time import now_utc


class PlatformDateTimeField(models.DateTimeField):  # type: ignore[type-arg]
    """Django auto timestamps backed by the platform clock.

    The platform clock is real UTC in production and can be pinned in an
    explicitly enabled non-production QA environment. The field deconstructs
    as Django's stock DateTimeField because its database representation is
    identical; only runtime timestamp selection differs.
    """

    def pre_save(self, model_instance: models.Model, add: bool) -> Any:
        if self.auto_now or (self.auto_now_add and add):
            value = now_utc()
            setattr(model_instance, self.attname, value)
            return value
        return super().pre_save(model_instance, add)

    def deconstruct(self) -> tuple[str, str, Sequence[Any], dict[str, Any]]:
        name, _path, args, kwargs = super().deconstruct()
        return name, "django.db.models.DateTimeField", args, kwargs


class AppendOnlyViolation(RuntimeError):
    pass


class AppendOnlyQuerySet(models.QuerySet[Any]):
    def update(self, **kwargs: Any) -> int:
        raise AppendOnlyViolation("Append-only records cannot be updated.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise AppendOnlyViolation("Append-only records cannot be deleted.")


class AppendOnlyManager(models.Manager[Any]):
    def get_queryset(self) -> AppendOnlyQuerySet:
        return AppendOnlyQuerySet(self.model, using=self._db)


class AppendOnlyModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    objects = AppendOnlyManager()

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise AppendOnlyViolation("Append-only records cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise AppendOnlyViolation("Append-only records cannot be deleted.")


class TimestampedModel(models.Model):
    created_at = PlatformDateTimeField(auto_now_add=True)
    updated_at = PlatformDateTimeField(auto_now=True)

    class Meta:
        abstract = True
