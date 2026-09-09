from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from PIL import Image

from backend.apps.platform_core.domain.story import (
    MAX_BLOCKS,
    StoryValidationError,
    story_image_ids,
    validate_story,
)
from backend.apps.platform_core.models.story_images import StoryImage
from backend.apps.platform_core.services.story_images import (
    MAX_STORED_BYTES,
    StoreStoryImageCommand,
    StoryImageError,
    normalise_story_image,
    store_story_image,
)


def _png_bytes(size: tuple[int, int] = (64, 48), *, alpha: bool = False) -> bytes:
    image = Image.new(
        "RGBA" if alpha else "RGB", size, (200, 30, 30, 120) if alpha else (200, 30, 30)
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _noise_jpeg(size: tuple[int, int]) -> bytes:
    # Random pixels compress badly, which forces the shrink loop to work.
    import os

    image = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


# --- validator -----------------------------------------------------------


def test_validate_story_normalises_supported_blocks() -> None:
    image_id = str(uuid.uuid4())
    story = validate_story(
        {
            "version": 1,
            "blocks": [
                {"type": "heading", "level": 2, "runs": [{"text": "About us"}]},
                {
                    "type": "paragraph",
                    "runs": [
                        {"text": "We build ", "bold": False},
                        {"text": "bakeries", "bold": True, "italic": True},
                        {"text": " (site)", "href": "https://example.test/"},
                        {"text": ""},
                    ],
                },
                {"type": "bullet_list", "items": [[{"text": "one"}], [], [{"text": "two"}]]},
                {"type": "image", "image_id": image_id, "alt": "Shop", "caption": "Main street"},
                {"type": "divider"},
                {"type": "quote", "runs": [{"text": "Quality first"}]},
            ],
        },
        image_exists=lambda _id: True,
    )
    assert story["version"] == 1
    assert [block["type"] for block in story["blocks"]] == [
        "heading",
        "paragraph",
        "bullet_list",
        "image",
        "divider",
        "quote",
    ]
    assert story["blocks"][0]["level"] == 2
    paragraph = story["blocks"][1]["runs"]
    assert paragraph == [
        {"text": "We build "},
        {"text": "bakeries", "bold": True, "italic": True},
        {"text": " (site)", "href": "https://example.test/"},
    ]
    assert story["blocks"][2]["items"] == [[{"text": "one"}], [{"text": "two"}]]
    assert story["blocks"][3] == {
        "type": "image",
        "image_id": image_id,
        "alt": "Shop",
        "caption": "Main street",
    }
    assert story_image_ids(story) == [image_id]


def test_validate_story_accepts_empty_values() -> None:
    assert validate_story(None) == {"version": 1, "blocks": []}
    assert validate_story({}) == {"version": 1, "blocks": []}
    assert validate_story({"version": 1, "blocks": []}) == {"version": 1, "blocks": []}


@pytest.mark.parametrize(
    "document",
    [
        {"version": 2, "blocks": []},
        {"version": 1, "blocks": [{"type": "script", "runs": []}]},
        {"version": 1, "blocks": [{"type": "paragraph", "runs": [{"text": "x", "onclick": "1"}]}]},
        {
            "version": 1,
            "blocks": [
                {"type": "paragraph", "runs": [{"text": "x", "href": "javascript:alert(1)"}]}
            ],
        },
        {
            "version": 1,
            "blocks": [
                {"type": "paragraph", "runs": [{"text": "x", "href": "http://insecure.test"}]}
            ],
        },
        {"version": 1, "blocks": [{"type": "heading", "level": 1, "runs": [{"text": "x"}]}]},
        {"version": 1, "blocks": [{"type": "paragraph", "html": "<b>x</b>"}]},
        {
            "version": 1,
            "blocks": [{"type": "image", "image_id": "not-a-uuid", "alt": "", "caption": ""}],
        },
        {
            "version": 1,
            "blocks": [{"type": "image", "image_id": str(uuid.uuid4()), "src": "https://x"}],
        },
        {
            "version": 1,
            "blocks": [{"type": "paragraph", "runs": [{"text": "x"}]}] * (MAX_BLOCKS + 1),
        },
        {"version": 1, "blocks": [], "extra": 1},
        "<p>not json</p>",
    ],
)
def test_validate_story_rejects_unsupported_content(document: Any) -> None:
    with pytest.raises(StoryValidationError):
        validate_story(document, image_exists=lambda _id: True)


def test_validate_story_requires_known_images() -> None:
    document = {
        "version": 1,
        "blocks": [{"type": "image", "image_id": str(uuid.uuid4()), "alt": "", "caption": ""}],
    }
    with pytest.raises(StoryValidationError, match="does not exist"):
        validate_story(document, image_exists=lambda _id: False)


def test_validate_story_strips_control_characters() -> None:
    story = validate_story(
        {"version": 1, "blocks": [{"type": "paragraph", "runs": [{"text": "a\x00b\x07c\nd"}]}]}
    )
    assert story["blocks"][0]["runs"] == [{"text": "abc\nd"}]


# --- image pipeline ------------------------------------------------------


def test_normalise_story_image_reencodes_as_metadata_free_jpeg() -> None:
    encoded, width, height = normalise_story_image(_png_bytes((64, 48), alpha=True))
    assert (width, height) == (64, 48)
    with Image.open(io.BytesIO(encoded)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert not image.info.get("exif")
        # Alpha is flattened onto white, so the pixel is a tinted red, not raw RGBA.
        pixel = image.getpixel((5, 5))
        assert pixel[0] > pixel[1] and pixel[0] > pixel[2]


def test_normalise_story_image_shrinks_to_one_megabyte() -> None:
    encoded, width, height = normalise_story_image(_noise_jpeg((2600, 2000)))
    assert len(encoded) <= MAX_STORED_BYTES
    assert max(width, height) <= 2400


def test_story_image_pixel_limit_is_hard_and_does_not_change_pillow_globals(
    monkeypatch: Any,
) -> None:
    from backend.apps.platform_core.services import story_images

    original_limit = Image.MAX_IMAGE_PIXELS
    monkeypatch.setattr(story_images, "MAX_SOURCE_PIXELS", 100)
    with pytest.raises(StoryImageError, match="million pixels"):
        normalise_story_image(_png_bytes((11, 10)))
    assert Image.MAX_IMAGE_PIXELS == original_limit
    assert normalise_story_image(_png_bytes((10, 10)))[1:] == (10, 10)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"GIF89a not really an image",
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        b"%PDF-1.4 fake",
        b"\xff\xd8\xff\xe0" + b"\x00" * 64,
        b"MZ" + b"\x00" * 200,
    ],
)
def test_normalise_story_image_rejects_non_images(payload: bytes) -> None:
    with pytest.raises(StoryImageError):
        normalise_story_image(payload)


@pytest.mark.django_db
def test_store_story_image_persists_reencoded_file(settings: Any, tmp_path: Path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    image = store_story_image(
        StoreStoryImageCommand(
            upload=io.BytesIO(_png_bytes((120, 80))),
            original_filename="../../etc/passwd.png",
            uploaded_by_id="admin-1",
        )
    )
    stored = StoryImage.objects.get(id=image.id)
    assert stored.content_type == "image/jpeg"
    assert (stored.width, stored.height) == (120, 80)
    assert stored.byte_size == Path(stored.file.path).stat().st_size
    assert stored.file.name == f"story-images/{stored.id}.jpg"
    assert "passwd" not in stored.file.name


# --- endpoints -----------------------------------------------------------


def _user(*, email: str, account_type: str, is_staff: bool) -> Any:
    user_model = get_user_model()
    return user_model.objects.create_user(
        email=email,
        full_name="Story User",
        account_type=account_type,
        status="active",
        is_staff=is_staff,
        is_active=True,
    )


@pytest.mark.django_db
def test_story_image_endpoints_enforce_roles(settings: Any, tmp_path: Path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    admin = _user(email="story-admin@example.test", account_type="admin", is_staff=True)
    investor = _user(
        email="story-investor@example.test", account_type="natural_person_lender", is_staff=False
    )
    upload = io.BytesIO(_png_bytes((40, 40)))
    upload.name = "shop.png"

    anonymous = Client()
    assert anonymous.post("/api/v1/admin/story-images/", {"file": upload}).status_code == 403

    investor_client = Client()
    investor_client.force_login(investor)
    upload.seek(0)
    assert investor_client.post("/api/v1/admin/story-images/", {"file": upload}).status_code == 403

    admin_client = Client()
    admin_client.force_login(admin)
    upload.seek(0)
    response = admin_client.post("/api/v1/admin/story-images/", {"file": upload})
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["url"] == f"/api/v1/story-images/{body['id']}/"
    assert body["content_type"] == "image/jpeg"

    # Anyone signed in can view; anonymous callers cannot.
    assert anonymous.get(body["url"]).status_code == 403
    served = investor_client.get(body["url"])
    assert served.status_code == 200
    assert served["Content-Type"] == "image/jpeg"
    assert served["Cache-Control"].startswith("private")
    assert b"".join(cast(Any, served).streaming_content)[:3] == b"\xff\xd8\xff"
    assert investor_client.get(f"/api/v1/story-images/{uuid.uuid4()}/").status_code == 404

    bad = io.BytesIO(b"<html><script>alert(1)</script></html>")
    bad.name = "evil.png"
    rejected = admin_client.post("/api/v1/admin/story-images/", {"file": bad})
    assert rejected.status_code == 400
    assert "not a valid image" in rejected.json()["detail"]
