"""Constrained rich-text document used for investor-facing stories.

Stories are stored as a small block/run JSON document instead of HTML so that
nothing an admin types can ever reach investors as markup. Every block and
inline run is whitelisted here; anything else is rejected at write time.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

STORY_VERSION = 1
MAX_BLOCKS = 200
MAX_LIST_ITEMS = 100
MAX_RUNS_PER_TEXT = 200
MAX_TEXT_CHARS = 5_000
MAX_TOTAL_CHARS = 60_000
MAX_LINK_CHARS = 2_000
MAX_ALT_CHARS = 200
MAX_CAPTION_CHARS = 300
TEXT_BLOCKS = {"paragraph", "heading", "quote"}
LIST_BLOCKS = {"bullet_list", "numbered_list"}
HEADING_LEVELS = {2, 3}


class StoryValidationError(ValueError):
    pass


def empty_story() -> dict[str, Any]:
    return {"version": STORY_VERSION, "blocks": []}


def _clean_text(value: Any, *, label: str, limit: int) -> str:
    if not isinstance(value, str):
        raise StoryValidationError(f"{label} must be text.")
    cleaned = value.replace("\r\n", "\n").replace("\r", "\n")
    # Strip control characters except newline and tab.
    cleaned = "".join(ch for ch in cleaned if ch in "\n\t" or ord(ch) >= 32)
    if len(cleaned) > limit:
        raise StoryValidationError(f"{label} cannot exceed {limit} characters.")
    return cleaned


def _clean_href(value: Any) -> str:
    if not isinstance(value, str):
        raise StoryValidationError("Links must be text URLs.")
    href = value.strip()
    if len(href) > MAX_LINK_CHARS:
        raise StoryValidationError("Links cannot exceed 2,000 characters.")
    lowered = href.lower()
    if not (lowered.startswith("https://") or lowered.startswith("mailto:")):
        raise StoryValidationError("Links must start with https:// or mailto:.")
    if any(ch.isspace() for ch in href) or "\x00" in href:
        raise StoryValidationError("Links cannot contain whitespace.")
    return href


def _clean_runs(value: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise StoryValidationError(f"{label} must be a list of text runs.")
    if len(value) > MAX_RUNS_PER_TEXT:
        raise StoryValidationError(f"{label} has too many formatting runs.")
    runs: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise StoryValidationError(f"{label} runs must be objects.")
        unknown = set(raw) - {"text", "bold", "italic", "href"}
        if unknown:
            raise StoryValidationError(f"{label} contains unsupported formatting.")
        text = _clean_text(raw.get("text", ""), label=label, limit=MAX_TEXT_CHARS)
        if text == "":
            continue
        run: dict[str, Any] = {"text": text}
        if raw.get("bold") is True:
            run["bold"] = True
        if raw.get("italic") is True:
            run["italic"] = True
        if raw.get("href") not in (None, ""):
            run["href"] = _clean_href(raw.get("href"))
        runs.append(run)
    return runs


def _runs_length(runs: list[dict[str, Any]]) -> int:
    return sum(len(run["text"]) for run in runs)


def validate_story(
    value: Any,
    *,
    image_exists: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    """Validate and normalise a story document.

    Returns the normalised document. ``image_exists`` is consulted for every
    image block so stories can only reference images the platform stored.
    """
    if value in (None, "", {}):
        return empty_story()
    if not isinstance(value, dict):
        raise StoryValidationError("Story must be an object.")
    if set(value) - {"version", "blocks"}:
        raise StoryValidationError("Story contains unsupported keys.")
    if value.get("version", STORY_VERSION) != STORY_VERSION:
        raise StoryValidationError("Unsupported story version.")
    raw_blocks = value.get("blocks", [])
    if not isinstance(raw_blocks, list):
        raise StoryValidationError("Story blocks must be a list.")
    if len(raw_blocks) > MAX_BLOCKS:
        raise StoryValidationError(f"Stories cannot exceed {MAX_BLOCKS} blocks.")
    blocks: list[dict[str, Any]] = []
    total_chars = 0
    for raw in raw_blocks:
        if not isinstance(raw, dict):
            raise StoryValidationError("Each story block must be an object.")
        block_type = raw.get("type")
        if not isinstance(block_type, str):
            raise StoryValidationError("Each story block must have a text type.")
        if block_type in TEXT_BLOCKS:
            unknown = set(raw) - {"type", "runs", "level"}
            if unknown or (block_type != "heading" and "level" in raw):
                raise StoryValidationError(f"{block_type} block contains unsupported keys.")
            runs = _clean_runs(raw.get("runs", []), label=f"{block_type} text")
            total_chars += _runs_length(runs)
            block: dict[str, Any] = {"type": block_type, "runs": runs}
            if block_type == "heading":
                level = raw.get("level", 2)
                if type(level) is not int or level not in HEADING_LEVELS:
                    raise StoryValidationError("Headings must be level 2 or 3.")
                block["level"] = level
            blocks.append(block)
        elif block_type in LIST_BLOCKS:
            if set(raw) - {"type", "items"}:
                raise StoryValidationError(f"{block_type} block contains unsupported keys.")
            raw_items = raw.get("items", [])
            if not isinstance(raw_items, list):
                raise StoryValidationError("List items must be a list.")
            if len(raw_items) > MAX_LIST_ITEMS:
                raise StoryValidationError(f"Lists cannot exceed {MAX_LIST_ITEMS} items.")
            items = [_clean_runs(item, label="list item") for item in raw_items]
            items = [item for item in items if item]
            total_chars += sum(_runs_length(item) for item in items)
            if not items:
                continue
            blocks.append({"type": block_type, "items": items})
        elif block_type == "image":
            if set(raw) - {"type", "image_id", "alt", "caption"}:
                raise StoryValidationError("Image block contains unsupported keys.")
            image_id = str(raw.get("image_id", "")).strip()
            try:
                image_uuid = uuid.UUID(image_id)
            except (TypeError, ValueError) as exc:
                raise StoryValidationError("Image blocks must reference a stored image.") from exc
            if image_exists is not None and not image_exists(str(image_uuid)):
                raise StoryValidationError("Story references an image that does not exist.")
            alt = _clean_text(raw.get("alt", ""), label="Image description", limit=MAX_ALT_CHARS)
            caption = _clean_text(
                raw.get("caption", ""), label="Image caption", limit=MAX_CAPTION_CHARS
            )
            total_chars += len(alt) + len(caption)
            blocks.append(
                {"type": "image", "image_id": str(image_uuid), "alt": alt, "caption": caption}
            )
        elif block_type == "divider":
            if set(raw) - {"type"}:
                raise StoryValidationError("Divider block contains unsupported keys.")
            blocks.append({"type": "divider"})
        else:
            raise StoryValidationError("Story contains an unsupported block type.")
    if total_chars > MAX_TOTAL_CHARS:
        raise StoryValidationError(f"Stories cannot exceed {MAX_TOTAL_CHARS} characters of text.")
    return {"version": STORY_VERSION, "blocks": blocks}


def story_image_ids(story: dict[str, Any]) -> list[str]:
    return [
        str(block["image_id"])
        for block in story.get("blocks", [])
        if isinstance(block, dict) and block.get("type") == "image"
    ]
