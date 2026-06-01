from __future__ import annotations

from django.db import models

from backend.apps.platform_core.models.base import TimestampedModel


class FileScanStatus(models.TextChoices):
    QUARANTINED = "quarantined", "Quarantined"
    CLEAN = "clean", "Clean"
    INFECTED = "infected", "Infected"
    FAILED = "failed", "Failed"
    TIMEOUT = "timeout", "Timeout"


class FileAccessScope(models.TextChoices):
    OWNER = "owner", "Owner"
    INTERNAL = "internal", "Internal"
    PUBLIC = "public", "Public"


class StoredFile(TimestampedModel):
    storage_key = models.CharField(max_length=512, unique=True)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=128)
    size_bytes = models.PositiveBigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)
    scan_status = models.CharField(
        max_length=32,
        choices=FileScanStatus.choices,
        default=FileScanStatus.QUARANTINED,
    )
    access_scope = models.CharField(
        max_length=32,
        choices=FileAccessScope.choices,
        default=FileAccessScope.OWNER,
    )
    owner_type = models.CharField(max_length=64, blank=True)
    owner_id = models.CharField(max_length=128, blank=True)
    created_by_type = models.CharField(max_length=64)
    created_by_id = models.CharField(max_length=128)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner_type", "owner_id"]),
            models.Index(fields=["scan_status", "access_scope"]),
        ]
