from __future__ import annotations

import uuid
from typing import Any

from django.db import models


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
