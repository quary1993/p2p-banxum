from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import TimestampedModel


def story_image_upload_path(instance: StoryImage, filename: str) -> str:
    # The original filename is never trusted or kept; every stored image is a
    # freshly re-encoded JPEG named after its own id.
    return f"story-images/{instance.id}.jpg"


class StoryImage(TimestampedModel):
    """Re-encoded, size-capped image embedded in an investor-facing story.

    Bytes only ever come out of the Pillow pipeline in
    ``platform_core.services.story_images`` (verified image, metadata
    stripped, JPEG, <= 1 MB) and are served only to authenticated users.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to=story_image_upload_path, max_length=255)
    content_type = models.CharField(max_length=64)
    byte_size = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    checksum_sha256 = models.CharField(max_length=64)
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_by_id = models.CharField(max_length=128)

    class Meta:
        ordering = ["-created_at", "-id"]
