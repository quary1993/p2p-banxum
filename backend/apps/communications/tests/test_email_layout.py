"""The shared email layout follows the October 2026 site design and carries the logo."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from django.test import override_settings

from backend.apps.communications.services import (
    EMAIL_LOGO_INVERSE_PATH,
    EMAIL_LOGO_PATH,
    EmailButton,
    EmailTemplateContent,
    _email_time,
    _render_banxum_email_html,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _content(**overrides: object) -> EmailTemplateContent:
    values: dict[str, object] = {
        "notice_label": "Balance notice",
        "preheader": "We credited CHF 25'000.00.",
        "status_label": "Credited",
        "status_tone": "confirmation",
        "headline": "Your deposit is credited",
        "paragraphs": ("We credited CHF 25'000.00 to your balance.",),
        "data_rows": (("Amount", "CHF 25'000.00"),),
        "buttons": (EmailButton("Open balances", "https://app.banxum.test/balances"),),
    }
    values.update(overrides)
    return EmailTemplateContent(**values)  # type: ignore[arg-type]


@override_settings(PUBLIC_APP_BASE_URL="https://app.banxum.test", EMAIL_ASSET_BASE_URL="")
def test_header_and_footer_show_the_hosted_logo_with_a_text_fallback() -> None:
    body = _render_banxum_email_html(_content())

    assert f'src="https://app.banxum.test/{EMAIL_LOGO_PATH}"' in body
    assert f'src="https://app.banxum.test/{EMAIL_LOGO_INVERSE_PATH}"' in body
    assert body.count('alt="BANXUM"') == 2
    # The old green "B" tile and fonts of the earlier design are gone.
    assert "#2f6b4f" not in body
    assert "Public Sans" not in body
    assert "Archivo" in body
    # Pill buttons and square status tags, as on the site.
    assert "border-radius:999px" in body
    assert "Credited" in body
    assert "Open balances" in body


@override_settings(
    PUBLIC_APP_BASE_URL="https://app.banxum.test",
    EMAIL_ASSET_BASE_URL="https://cdn.banxum.test/",
)
def test_email_images_can_come_from_another_host() -> None:
    body = _render_banxum_email_html(_content())

    assert f'src="https://cdn.banxum.test/{EMAIL_LOGO_PATH}"' in body
    assert 'href="https://app.banxum.test"' in body


@override_settings(PUBLIC_APP_BASE_URL="https://app.banxum.test", PLATFORM_BRAND_NAME="Lendo")
def test_another_platform_name_gets_a_text_wordmark_not_the_banxum_logo() -> None:
    body = _render_banxum_email_html(_content())

    assert EMAIL_LOGO_PATH not in body
    assert ">Lendo</span>" in body


@override_settings(PUBLIC_APP_BASE_URL="https://app.banxum.test")
def test_a_highlighted_code_is_shown_large_above_the_details() -> None:
    body = _render_banxum_email_html(
        _content(highlight=("Your confirmation code", "106297"), data_rows=())
    )

    assert "Your confirmation code" in body
    assert "106297" in body
    assert "font-size:36px" in body


def test_expiry_times_read_as_zurich_wall_time() -> None:
    assert _email_time(datetime(2026, 10, 12, 12, 39, tzinfo=UTC)) == (
        "12 Oct 2026, 14:39 (Zurich time)"
    )
    assert _email_time(datetime(2026, 1, 5, 7, 0, tzinfo=UTC)) == "05 Jan 2026, 08:00 (Zurich time)"


def test_the_logo_files_exist_in_the_public_frontend_folder() -> None:
    public = REPO_ROOT / "frontend" / "public"

    assert (public / EMAIL_LOGO_PATH).is_file()
    assert (public / EMAIL_LOGO_INVERSE_PATH).is_file()
