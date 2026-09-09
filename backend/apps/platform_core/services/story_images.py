"""Story image intake: verify, normalise, shrink, and store admin-uploaded images.

Every uploaded file goes through Pillow twice (``verify`` then a full decode)
so that only real raster images are accepted. The accepted image is then
re-encoded from pixels as a metadata-free JPEG, downscaled and recompressed
until it fits ``MAX_STORED_BYTES``. Nothing from the original file survives
except the pixels.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import Any, BinaryIO

from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.apps.platform_core.models.story_images import StoryImage

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_STORED_BYTES = 1024 * 1024
MAX_SOURCE_PIXELS = 40_000_000
MAX_EDGE_STEPS = (2400, 1800, 1400, 1100, 900, 700, 500)
QUALITY_STEPS = (88, 82, 76, 70, 62, 55, 45)
ACCEPTED_FORMATS = frozenset({"JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF", "MPO"})


class StoryImageError(ValueError):
    pass


@dataclass(frozen=True)
class StoreStoryImageCommand:
    upload: BinaryIO
    original_filename: str
    uploaded_by_id: str


def _read_upload(upload: BinaryIO) -> bytes:
    if hasattr(upload, "seek"):
        try:
            upload.seek(0)
        except (OSError, ValueError):
            pass
    data = upload.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise StoryImageError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise StoryImageError("Images must be smaller than 25 MB before processing.")
    return data


def _decode_verified_image(data: bytes) -> Image.Image:
    # Pass 1: structural verification of the container. Pass 2: full decode.
    # A file that is not a real raster image fails one of the two.
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in ACCEPTED_FORMATS:
                raise StoryImageError(
                    "Only JPEG, PNG, WebP, GIF, BMP and TIFF images are accepted."
                )
            if probe.width * probe.height > MAX_SOURCE_PIXELS:
                raise StoryImageError("Images must contain no more than 40 million pixels.")
            probe.verify()
        image = Image.open(io.BytesIO(data))
        image.load()
    except StoryImageError:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
        SyntaxError,
    ) as exc:
        raise StoryImageError("The file is not a valid image.") from exc
    if image.width < 1 or image.height < 1:
        raise StoryImageError("The image is empty.")
    return image


def _flatten(image: Image.Image) -> Image.Image:
    # Honour EXIF rotation from pixels, then drop everything but pixels.
    try:
        image = ImageOps.exif_transpose(image) or image
    except Exception:  # pragma: no cover - defensive around broken EXIF blobs
        pass
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image.copy()


def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buffer.getvalue()


def _fit_within(image: Image.Image, max_edge: int) -> Image.Image:
    if max(image.size) <= max_edge:
        return image
    resized = image.copy()
    resized.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return resized


def normalise_story_image(data: bytes) -> tuple[bytes, int, int]:
    """Return ``(jpeg_bytes, width, height)`` for a verified image, <= 1 MB."""
    source = _flatten(_decode_verified_image(data))
    for max_edge in MAX_EDGE_STEPS:
        candidate = _fit_within(source, max_edge)
        for quality in QUALITY_STEPS:
            encoded = _encode_jpeg(candidate, quality)
            if len(encoded) <= MAX_STORED_BYTES:
                return encoded, candidate.width, candidate.height
    raise StoryImageError("The image could not be reduced to 1 MB.")


def store_story_image(command: StoreStoryImageCommand) -> StoryImage:
    data = _read_upload(command.upload)
    encoded, width, height = normalise_story_image(data)
    image = StoryImage(
        content_type="image/jpeg",
        byte_size=len(encoded),
        width=width,
        height=height,
        checksum_sha256=hashlib.sha256(encoded).hexdigest(),
        original_filename=str(command.original_filename or "")[:255],
        uploaded_by_id=str(command.uploaded_by_id),
    )
    with transaction.atomic():
        image.file.save(f"{image.id}.jpg", ContentFile(encoded), save=False)
        image.save()
    return image


def story_image_exists(image_id: str) -> bool:
    return StoryImage.objects.filter(id=image_id).exists()


def story_image_payload(image: StoryImage) -> dict[str, Any]:
    return {
        "id": str(image.id),
        "url": f"/api/v1/story-images/{image.id}/",
        "width": int(image.width),
        "height": int(image.height),
        "byte_size": int(image.byte_size),
        "content_type": image.content_type,
        "created_at": image.created_at,
    }
