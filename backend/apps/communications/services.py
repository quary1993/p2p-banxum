# ruff: noqa: E501

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from backend.apps.communications.models import (
    CommunicationEvent,
    CommunicationEventType,
    EmailDeliveryRecord,
    EmailDeliveryStatus,
)
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.models.events import OutboxStatus
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import (
    DomainEventCommand,
    mark_outbox_failed,
    mark_outbox_processed,
    record_domain_event,
)


class CommunicationsError(RuntimeError):
    pass


class UnsupportedEmailTopicError(CommunicationsError):
    pass


class EmailProviderError(CommunicationsError):
    pass


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    recipient_email: str
    subject: str
    body_text: str
    body_html: str
    template_key: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmailProviderResult:
    provider_message_id: str


@dataclass(frozen=True, slots=True)
class EmailButton:
    label: str
    url: str
    variant: str = "primary"


@dataclass(frozen=True, slots=True)
class EmailTemplateContent:
    notice_label: str
    preheader: str
    status_label: str
    status_tone: str
    headline: str
    paragraphs: tuple[str, ...]
    data_rows: tuple[tuple[str, str], ...] = ()
    buttons: tuple[EmailButton, ...] = ()
    fine_print: str = ""


class EmailProvider(Protocol):
    provider_name: str

    def send(self, email: RenderedEmail) -> EmailProviderResult:
        ...


@dataclass(frozen=True, slots=True)
class DispatchEmailOutboxCommand:
    limit: int | None = None
    now: Any | None = None


@dataclass(frozen=True, slots=True)
class DispatchEmailOutboxResult:
    processed_count: int
    sent_count: int
    failed_count: int
    dead_letter_count: int
    skipped_count: int
    message_ids: tuple[int, ...]


class MockEmailProvider:
    provider_name = "mock"

    def send(self, email: RenderedEmail) -> EmailProviderResult:
        stable = f"{email.template_key}:{email.recipient_email}:{timezone.now().timestamp()}"
        return EmailProviderResult(provider_message_id=f"mock-{abs(hash(stable))}")


class SendGridEmailProvider:
    provider_name = "sendgrid"

    def send(self, email: RenderedEmail) -> EmailProviderResult:
        api_key = settings.SENDGRID_API_KEY
        from_email = settings.SENDGRID_FROM_EMAIL
        from_name = settings.SENDGRID_FROM_NAME
        if not api_key or not from_email:
            raise EmailProviderError("SendGrid provider is not configured.")

        payload = {
            "personalizations": [{"to": [{"email": email.recipient_email}]}],
            "from": {"email": from_email, "name": from_name},
            "subject": email.subject,
            "content": [
                {"type": "text/plain", "value": email.body_text},
                {"type": "text/html", "value": email.body_html or _html_from_text(email.body_text)},
            ],
        }
        request = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=settings.SENDGRID_TIMEOUT_SECONDS,
            ) as response:
                if response.status < 200 or response.status >= 300:
                    raise EmailProviderError(f"SendGrid returned HTTP {response.status}.")
                provider_message_id = response.headers.get("X-Message-Id", "")
        except urllib.error.HTTPError as exc:
            raise EmailProviderError(f"SendGrid returned HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise EmailProviderError("SendGrid request failed.") from exc
        return EmailProviderResult(provider_message_id=provider_message_id)


def _email_provider() -> EmailProvider:
    provider = settings.COMMUNICATIONS_EMAIL_PROVIDER.lower()
    if provider == "sendgrid":
        return SendGridEmailProvider()
    if provider in {"mock", "local"}:
        return MockEmailProvider()
    raise EmailProviderError(f"Unsupported email provider '{provider}'.")


def _auth_services_module() -> Any:
    from importlib import import_module

    return import_module("backend.apps.accounts_auth.services")


def _email_login_token_model() -> Any:
    return apps.get_model("accounts_auth", "EmailLoginToken")


def _sensitive_action_code_model() -> Any:
    return apps.get_model("accounts_auth", "SensitiveActionCode")


def _base_url() -> str:
    base_url = str(settings.PUBLIC_APP_BASE_URL).rstrip("/")
    if not base_url:
        raise CommunicationsError("PUBLIC_APP_BASE_URL is required to render email links.")
    return base_url


URL_RE = re.compile(r"https?://[^\s<>\"]+")
STATUS_STYLES = {
    "confirmation": ("#e7efe8", "#b8cdbd", "#2f6b4f"),
    "warning": ("#f6ecd2", "#e3cf9c", "#6f4a0d"),
    "danger": ("#f6e2dd", "#e4b8ad", "#9c3127"),
    "info": ("#e3edf4", "#bdd0dc", "#244e72"),
}


def _escape_attr(value: str) -> str:
    return html.escape(value, quote=True)


def _linkified_text(value: str) -> str:
    result: list[str] = []
    position = 0
    for match in URL_RE.finditer(value):
        url = match.group(0)
        trailing = ""
        while url and url[-1] in ".,);]":
            trailing = url[-1] + trailing
            url = url[:-1]
        result.append(html.escape(value[position : match.start()]))
        safe_url = _escape_attr(url)
        result.append(
            f'<a href="{safe_url}" target="_blank" '
            'style="color:#2f6b4f; text-decoration:underline; word-break:break-all;">'
            f"{html.escape(url)}</a>{html.escape(trailing)}"
        )
        position = match.end()
    result.append(html.escape(value[position:]))
    return "".join(result).replace("\n", "<br>")


def _paragraph_html(paragraphs: tuple[str, ...]) -> str:
    return "".join(
        (
            '<p class="font-sans" '
            'style="margin:0 0 14px 0; color:#4b544d; font-size:15px; line-height:24px;">'
            f"{_linkified_text(paragraph)}</p>"
        )
        for paragraph in paragraphs
        if paragraph
    )


def _button_html(button: EmailButton, *, first: bool) -> str:
    safe_url = _escape_attr(button.url)
    safe_label = html.escape(button.label)
    if button.variant == "secondary":
        background = "#fffefb"
        color = "#1b211d"
        border = "#d2cdbd"
        vml_border = "#d2cdbd"
    else:
        background = "#2f6b4f"
        color = "#ffffff"
        border = "#2f6b4f"
        vml_border = "#2f6b4f"
    width = max(150, min(260, 28 + len(button.label) * 9))
    padding = "0 10px 0 0" if first else "0"
    return f"""
                        <td class="btn-td" style="padding:{padding};">
                          <!--[if mso]>
                          <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{safe_url}" style="height:46px;v-text-anchor:middle;width:{width}px;" arcsize="11%" strokecolor="{vml_border}" fillcolor="{background}">
                          <w:anchorlock/><center style="color:{color};font-family:Helvetica,Arial,sans-serif;font-size:15px;font-weight:600;">{safe_label}</center>
                          </v:roundrect>
                          <![endif]-->
                          <!--[if !mso]><!-- -->
                          <a class="btn-a font-sans" href="{safe_url}" target="_blank" style="display:inline-block; white-space:nowrap; background-color:{background}; color:{color}; font-size:15px; font-weight:600; line-height:44px; padding:0 24px; border:1px solid {border}; border-radius:6px; text-align:center;">{safe_label}</a>
                          <!--<![endif]-->
                        </td>"""


def _buttons_html(buttons: tuple[EmailButton, ...]) -> str:
    if not buttons:
        return ""
    button_cells = "\n".join(_button_html(button, first=index == 0) for index, button in enumerate(buttons))
    return f"""
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td class="px" style="padding:10px 36px 8px 36px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>{button_cells}
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>"""


def _data_rows_html(rows: tuple[tuple[str, str], ...]) -> str:
    if not rows:
        return ""
    row_html: list[str] = []
    for index, (key, value) in enumerate(rows):
        border = "" if index == len(rows) - 1 else " border-bottom:1px solid #ece8dc;"
        row_html.append(
            "<tr>"
            f'<td class="font-sans data-k" style="padding:11px 0; color:#717a72; font-size:13px;{border}">'
            f"{html.escape(key)}</td>"
            f'<td class="font-mono data-v" align="right" style="padding:11px 0; color:#1b211d; font-size:14px; font-weight:500;{border}">'
            f"{_linkified_text(value)}</td>"
            "</tr>"
        )
    rows_combined = "".join(row_html)
    return f"""
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td class="px" style="padding:8px 36px 20px 36px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#faf8f1; border:1px solid #e0dccf; border-radius:8px;">
                      <tr>
                        <td style="padding:6px 18px;">
                          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                            {rows_combined}
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>"""


def _render_banxum_email_html(content: EmailTemplateContent) -> str:
    platform = html.escape(str(settings.PLATFORM_BRAND_NAME))
    operator = html.escape(str(settings.LEGAL_OPERATOR_NAME))
    configured_support_email = str(getattr(settings, "SUPPORT_EMAIL", "") or "support@banxum.com")
    support_email = html.escape(configured_support_email)
    base_url = _base_url()
    portal_url = _escape_attr(base_url)
    documents_url = _escape_attr(f"{base_url}/documents")
    settings_url = _escape_attr(f"{base_url}/settings")
    support_mailto = _escape_attr(f"mailto:{configured_support_email}")
    status_background, status_border, status_color = STATUS_STYLES.get(
        content.status_tone, STATUS_STYLES["info"]
    )
    preheader = html.escape(content.preheader[:180])
    notice_label = html.escape(content.notice_label.upper())
    status_label = html.escape(content.status_label)
    headline = html.escape(content.headline)
    paragraphs = _paragraph_html(content.paragraphs)
    data_panel = _data_rows_html(content.data_rows)
    buttons = _buttons_html(content.buttons)
    fine_print = (
        f"""
                    <p class="font-sans" style="margin:18px 0 0 0; color:#717a72; font-size:12px; line-height:19px;">
                      {_linkified_text(content.fine_print)}
                    </p>"""
        if content.fine_print
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta name="x-apple-disable-message-reformatting" />
  <meta name="color-scheme" content="light only" />
  <meta name="supported-color-schemes" content="light only" />
  <title>{platform}</title>
  <!--[if mso]>
  <noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
  <![endif]-->
  <link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    html, body {{ margin:0 !important; padding:0 !important; height:100% !important; width:100% !important; }}
    * {{ -ms-text-size-adjust:100%; -webkit-text-size-adjust:100%; }}
    table, td {{ mso-table-lspace:0pt !important; mso-table-rspace:0pt !important; border-collapse:collapse !important; }}
    img {{ -ms-interpolation-mode:bicubic; border:0; height:auto; line-height:100%; outline:none; text-decoration:none; }}
    a {{ text-decoration:none; }}
    a[x-apple-data-detectors] {{ color:inherit !important; text-decoration:none !important; font-size:inherit !important; font-family:inherit !important; font-weight:inherit !important; line-height:inherit !important; }}
    u + #body a {{ color:inherit; text-decoration:none; }}
    .font-sans {{ font-family:'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; }}
    .font-mono {{ font-family:'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace; }}
    @media screen and (max-width:600px) {{
      .container {{ width:100% !important; max-width:100% !important; }}
      .px {{ padding-left:22px !important; padding-right:22px !important; }}
      .btn-td {{ display:block !important; padding:0 0 12px 0 !important; }}
      .btn-a {{ display:block !important; text-align:center !important; }}
      .h1 {{ font-size:22px !important; line-height:28px !important; }}
      .data-k {{ display:block !important; width:100% !important; padding:12px 0 2px 0 !important; }}
      .data-v {{ display:block !important; width:100% !important; padding:0 0 12px 0 !important; text-align:left !important; }}
    }}
  </style>
</head>
<body id="body" style="margin:0; padding:0; width:100%; background-color:#e9e5d9;">
  <div style="display:none; max-height:0; overflow:hidden; mso-hide:all; font-size:1px; line-height:1px; color:#e9e5d9; opacity:0;">
    {preheader}
    &nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#e9e5d9;">
    <tr>
      <td align="center" style="padding:28px 12px 40px 12px;">
        <table role="presentation" class="container" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px; max-width:600px;">
          <tr>
            <td class="px" style="padding:4px 8px 16px 8px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="left" style="vertical-align:middle;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td style="vertical-align:middle; padding-right:9px;">
                          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="30" height="30" style="width:30px; height:30px; background-color:#2f6b4f; border-radius:7px;">
                            <tr><td align="center" valign="middle" class="font-sans" style="color:#ffffff; font-size:17px; font-weight:700; line-height:30px;">B</td></tr>
                          </table>
                        </td>
                        <td style="vertical-align:middle;" class="font-sans">
                          <div style="color:#1b211d; font-size:17px; font-weight:700; letter-spacing:2px; line-height:18px;">{platform}</div>
                          <div style="color:#717a72; font-size:10px; letter-spacing:0.3px; line-height:13px;">{operator}</div>
                        </td>
                      </tr>
                    </table>
                  </td>
                  <td align="right" class="font-sans" style="vertical-align:middle; color:#98a09a; font-size:11px; letter-spacing:0.4px;">{notice_label}</td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background-color:#fffefb; border:1px solid #e0dccf; border-radius:12px; overflow:hidden;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr><td style="height:3px; background-color:#2f6b4f; font-size:0; line-height:0;">&nbsp;</td></tr>
              </table>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td class="px" style="padding:30px 36px 0 36px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:18px;">
                      <tr>
                        <td class="font-sans" style="background-color:{status_background}; border:1px solid {status_border}; border-radius:999px; padding:5px 12px; color:{status_color}; font-size:12px; font-weight:600; letter-spacing:0.2px;">&#9679;&nbsp; {status_label}</td>
                      </tr>
                    </table>
                    <h1 class="font-sans h1" style="margin:0 0 12px 0; color:#1b211d; font-size:25px; line-height:31px; font-weight:600; letter-spacing:-0.3px;">{headline}</h1>
                    {paragraphs}
                  </td>
                </tr>
              </table>
              {data_panel}
              {buttons}
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td class="px" style="padding:18px 36px 32px 36px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr><td style="height:1px; background-color:#e0dccf; font-size:0; line-height:0;">&nbsp;</td></tr>
                    </table>
                    {fine_print}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td class="px" style="padding:24px 24px 8px 24px;">
              <p class="font-sans" style="margin:0 0 8px 0; color:#4b544d; font-size:12px; line-height:18px;">
                <strong style="color:#1b211d;">{platform}</strong> is a peer-to-peer lending platform operated by {operator}.
              </p>
              <p class="font-sans" style="margin:0 0 14px 0; color:#717a72; font-size:12px; line-height:18px;">
                You receive transactional emails because you hold an active account or requested secure access. These cannot be unsubscribed while your account is open.
                Manage marketing preferences in <a href="{settings_url}" style="color:#2f6b4f; text-decoration:underline;">Settings</a>.
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td class="font-sans" style="color:#98a09a; font-size:11px; padding-right:12px;"><a href="{portal_url}" style="color:#717a72; text-decoration:underline;">Portal</a></td>
                  <td class="font-sans" style="color:#98a09a; font-size:11px; padding-right:12px;"><a href="{documents_url}" style="color:#717a72; text-decoration:underline;">Documents</a></td>
                  <td class="font-sans" style="color:#98a09a; font-size:11px; padding-right:12px;"><a href="{support_mailto}" style="color:#717a72; text-decoration:underline;">{support_email}</a></td>
                </tr>
              </table>
              <p class="font-sans" style="margin:16px 0 0 0; color:#b3ab98; font-size:11px; line-height:16px;">&copy; 2026 {operator}. All rights reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _html_from_text(body_text: str) -> str:
    return _render_banxum_email_html(
        EmailTemplateContent(
            notice_label="Account notice",
            preheader=body_text.splitlines()[0] if body_text.splitlines() else "BANXUM account notice",
            status_label="Information",
            status_tone="info",
            headline="Account notice",
            paragraphs=tuple(paragraph for paragraph in body_text.split("\n\n") if paragraph.strip()),
            fine_print=(
                "This is an automated transactional account notice. "
                f"If you need help, contact {getattr(settings, 'SUPPORT_EMAIL', '') or 'support@banxum.com'}."
            ),
        )
    )


def _render_magic_link_email(message: OutboxMessage) -> RenderedEmail:
    payload = message.payload
    token_id = str(payload.get("delivery_secret_ref", ""))
    recipient = str(payload.get("email", "")).strip().lower()
    if not token_id or not recipient:
        raise CommunicationsError("Magic-link email payload is incomplete.")

    token_model = _email_login_token_model()
    token = token_model.objects.select_related("user").get(id=token_id)
    raw_token = _auth_services_module().delivery_secret_for_magic_link(token)
    login_url = f"{_base_url()}/login?token={urllib.parse.quote(raw_token)}"
    platform = settings.PLATFORM_BRAND_NAME
    operator = settings.LEGAL_OPERATOR_NAME
    subject = f"Your {platform} login link"
    body_text = (
        f"Use this secure link to sign in to {platform}:\n\n"
        f"{login_url}\n\n"
        f"The link expires at {token.expires_at.isoformat()} and can be used only once.\n"
        "If you did not request this email, you can ignore it.\n\n"
        f"{platform} is operated by {operator}."
    )
    return RenderedEmail(
        recipient_email=recipient,
        subject=subject,
        body_text=body_text,
        body_html=_render_banxum_email_html(
            EmailTemplateContent(
                notice_label="Secure login",
                preheader=f"Use your secure one-time {platform} login link.",
                status_label="Secure login",
                status_tone="info",
                headline=f"Sign in to {platform}",
                paragraphs=(
                    f"Use this secure one-time link to sign in to {platform}.",
                    "The link can be used only once. If you did not request this email, you can ignore it.",
                ),
                data_rows=(
                    ("Expires at", token.expires_at.isoformat()),
                    ("Recipient", recipient),
                ),
                buttons=(EmailButton("Open secure login link", login_url),),
                fine_print=(
                    f"If the button does not work, copy this link into your browser: {login_url}. "
                    f"{platform} is operated by {operator}."
                ),
            )
        ),
        template_key="auth.magic_link.v1",
        metadata={
            "user_id": str(payload.get("user_id", "")),
            "expires_at": token.expires_at.isoformat(),
            "secret_redacted_in_outbox": bool(payload.get("secret_redacted")),
        },
    )


def _render_sensitive_action_code_email(message: OutboxMessage) -> RenderedEmail:
    payload = message.payload
    code_id = str(payload.get("delivery_secret_ref", ""))
    recipient = str(payload.get("email", "")).strip().lower()
    action = str(payload.get("action", "sensitive_action"))
    if not code_id or not recipient:
        raise CommunicationsError("Sensitive-action email payload is incomplete.")

    code_model = _sensitive_action_code_model()
    code_record = code_model.objects.select_related("user").get(id=code_id)
    raw_code = _auth_services_module().delivery_secret_for_sensitive_action_code(code_record)
    platform = settings.PLATFORM_BRAND_NAME
    operator = settings.LEGAL_OPERATOR_NAME
    subject = f"Your {platform} confirmation code"
    body_text = (
        f"Your {platform} confirmation code is:\n\n"
        f"{raw_code}\n\n"
        f"It expires at {code_record.expires_at.isoformat()} and is valid for {action}.\n"
        "If you did not request this code, contact support and do not share it.\n\n"
        f"{platform} is operated by {operator}."
    )
    return RenderedEmail(
        recipient_email=recipient,
        subject=subject,
        body_text=body_text,
        body_html=_render_banxum_email_html(
            EmailTemplateContent(
                notice_label="Confirmation code",
                preheader=f"Your {platform} confirmation code for {action}.",
                status_label="Action needed",
                status_tone="warning",
                headline="Confirm this account action",
                paragraphs=(
                    f"Use this code to confirm your {platform} action.",
                    "Never share this code. If you did not request it, contact support and do not continue.",
                ),
                data_rows=(
                    ("Confirmation code", raw_code),
                    ("Action", action),
                    ("Expires at", code_record.expires_at.isoformat()),
                ),
                buttons=(EmailButton("Open BANXUM", _base_url()),),
                fine_print=f"{platform} is operated by {operator}.",
            )
        ),
        template_key=f"auth.{action}.code.v1",
        metadata={
            "user_id": str(payload.get("user_id", "")),
            "action": action,
            "expires_at": code_record.expires_at.isoformat(),
            "secret_redacted_in_outbox": bool(payload.get("secret_redacted")),
        },
    )


def _payload_status_for_topic(topic: str, template_key: str) -> tuple[str, str]:
    combined = f"{topic} {template_key}".lower()
    if any(token in combined for token in ("reminder", "deadline", "warning", "ageing")):
        return ("Action needed", "warning")
    if any(token in combined for token in ("failed", "default", "penalty", "risk")):
        return ("Important", "danger")
    if any(token in combined for token in ("confirmation", "credited", "completed", "approved")):
        return ("Confirmation", "confirmation")
    return ("Information", "info")


def _payload_data_rows(payload: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    raw_rows = payload.get("data_rows")
    if not isinstance(raw_rows, list):
        return ()
    rows: list[tuple[str, str]] = []
    for item in raw_rows[:8]:
        if isinstance(item, dict):
            label = str(item.get("label", "")).strip()
            value = str(item.get("value", "")).strip()
        elif isinstance(item, list | tuple) and len(item) >= 2:
            label = str(item[0]).strip()
            value = str(item[1]).strip()
        else:
            continue
        if label and value:
            rows.append((label, value))
    return tuple(rows)


def _payload_buttons(payload: dict[str, Any]) -> tuple[EmailButton, ...]:
    raw_buttons = payload.get("buttons")
    buttons: list[EmailButton] = []
    if isinstance(raw_buttons, list):
        for item in raw_buttons[:2]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            url = str(item.get("url", "")).strip()
            variant = str(item.get("variant", "primary")).strip() or "primary"
            if label and url.startswith(("https://", "http://")):
                buttons.append(EmailButton(label=label, url=url, variant=variant))
    if buttons:
        return tuple(buttons)
    action_url = str(payload.get("action_url", "")).strip()
    action_label = str(payload.get("action_label", "")).strip() or "Open BANXUM"
    if action_url.startswith(("https://", "http://")):
        return (EmailButton(action_label, action_url),)
    return ()


def _render_payload_email(message: OutboxMessage) -> RenderedEmail:
    payload = message.payload
    recipient = str(
        payload.get("email") or payload.get("recipient_email") or payload.get("to_email") or ""
    ).strip().lower()
    subject = str(payload.get("subject", "")).strip()
    body_text = str(payload.get("body_text", "")).strip()
    body_html = str(payload.get("body_html", "")).strip()
    template_key = str(payload.get("template_key", message.topic)).strip()
    if not recipient or not subject or not (body_text or body_html):
        raise UnsupportedEmailTopicError(
            f"Email topic '{message.topic}' has no renderable template."
        )
    if not body_text:
        body_text = html.unescape(body_html)
    if not body_html:
        status_label, status_tone = _payload_status_for_topic(message.topic, template_key)
        paragraphs = tuple(paragraph for paragraph in body_text.split("\n\n") if paragraph.strip())
        body_html = _render_banxum_email_html(
            EmailTemplateContent(
                notice_label=str(payload.get("notice_label", "Investor notice")),
                preheader=str(payload.get("preheader", paragraphs[0] if paragraphs else subject)),
                status_label=str(payload.get("status_label", status_label)),
                status_tone=str(payload.get("status_tone", status_tone)),
                headline=str(payload.get("headline", subject)),
                paragraphs=paragraphs,
                data_rows=_payload_data_rows(payload),
                buttons=_payload_buttons(payload),
                fine_print=str(
                    payload.get(
                        "fine_print",
                        (
                            "This is an automated transactional account notice. "
                            f"If you need help, contact {getattr(settings, 'SUPPORT_EMAIL', '') or 'support@banxum.com'}."
                        ),
                    )
                ),
            )
        )
    return RenderedEmail(
        recipient_email=recipient,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        template_key=template_key,
        metadata={"payload_template": True},
    )


def render_email_for_outbox_message(message: OutboxMessage) -> RenderedEmail:
    if message.topic == "email.magic_link_requested":
        return _render_magic_link_email(message)
    if message.topic == "email.sensitive_action_code_requested":
        return _render_sensitive_action_code_email(message)
    if message.topic.startswith("email."):
        return _render_payload_email(message)
    raise UnsupportedEmailTopicError(f"Outbox topic '{message.topic}' is not an email topic.")


def _record_delivery_attempt(
    *,
    message: OutboxMessage,
    rendered_email: RenderedEmail | None,
    provider_name: str,
    attempt_number: int,
    status: EmailDeliveryStatus,
    provider_message_id: str = "",
    error: str = "",
) -> EmailDeliveryRecord:
    return cast(
        EmailDeliveryRecord,
        EmailDeliveryRecord.objects.create(
            outbox_message=message,
            topic=message.topic,
            template_key=rendered_email.template_key if rendered_email else message.topic,
            recipient_email=rendered_email.recipient_email if rendered_email else "",
            subject=rendered_email.subject if rendered_email else "",
            body_text=rendered_email.body_text if rendered_email else "",
            body_html=rendered_email.body_html if rendered_email else "",
            provider=provider_name,
            provider_message_id=provider_message_id,
            status=status,
            attempt_number=attempt_number,
            sent_at=timezone.now() if status == EmailDeliveryStatus.SENT else None,
            error=error[:4000],
            metadata=rendered_email.metadata if rendered_email else {},
        ),
    )


def _record_delivery_events(record: EmailDeliveryRecord) -> None:
    if record.status == EmailDeliveryStatus.SENT:
        event_type = CommunicationEventType.EMAIL_SENT
        action = "communications.email_sent"
        domain_event = "EmailSent"
    else:
        event_type = CommunicationEventType.EMAIL_FAILED
        action = "communications.email_failed"
        domain_event = "EmailDeliveryFailed"
    CommunicationEvent.objects.create(
        event_type=event_type,
        outbox_message=record.outbox_message,
        email_delivery_record=record,
        metadata={
            "topic": record.topic,
            "recipient_email": record.recipient_email,
            "attempt_number": record.attempt_number,
            "status": record.status,
        },
    )
    record_audit_event(
        AuditCommand(
            actor=ActorRef.system(),
            action=action,
            target_type="OutboxMessage",
            target_id=str(record.outbox_message_id),
            metadata={
                "email_delivery_record_id": str(record.id),
                "topic": record.topic,
                "recipient_email": record.recipient_email,
                "attempt_number": record.attempt_number,
                "status": record.status,
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type=domain_event,
            aggregate_type="OutboxMessage",
            aggregate_id=str(record.outbox_message_id),
            payload={
                "email_delivery_record_id": str(record.id),
                "topic": record.topic,
                "status": record.status,
            },
            idempotency_key=f"communications:{record.status}:{record.id}",
        )
    )


def _due_email_message_ids(*, limit: int, now: Any) -> list[int]:
    return list(
        OutboxMessage.objects.filter(
            status=OutboxStatus.PENDING,
            topic__startswith="email.",
        )
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .order_by("created_at", "id")
        .values_list("id", flat=True)[:limit]
    )


@transaction.atomic
def _dispatch_one_email_message(message_id: int, *, provider: EmailProvider, now: Any) -> bool:
    message = (
        OutboxMessage.objects.select_for_update()
        .filter(id=message_id, status=OutboxStatus.PENDING, topic__startswith="email.")
        .first()
    )
    if message is None:
        return False
    if message.next_attempt_at is not None and message.next_attempt_at > now:
        return False

    attempt_number = message.attempts + 1
    rendered_email: RenderedEmail | None = None
    try:
        rendered_email = render_email_for_outbox_message(message)
        provider_result = provider.send(rendered_email)
        record = _record_delivery_attempt(
            message=message,
            rendered_email=rendered_email,
            provider_name=provider.provider_name,
            provider_message_id=provider_result.provider_message_id,
            attempt_number=attempt_number,
            status=EmailDeliveryStatus.SENT,
        )
        mark_outbox_processed(message)
        _record_delivery_events(record)
        return True
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        record = _record_delivery_attempt(
            message=message,
            rendered_email=rendered_email,
            provider_name=provider.provider_name,
            attempt_number=attempt_number,
            status=EmailDeliveryStatus.FAILED,
            error=error,
        )
        mark_outbox_failed(message, error)
        _record_delivery_events(record)
        return True


def dispatch_due_email_outbox_messages(
    command: DispatchEmailOutboxCommand | None = None,
) -> DispatchEmailOutboxResult:
    command = command or DispatchEmailOutboxCommand()
    now = command.now or timezone.now()
    limit = command.limit or settings.COMMUNICATIONS_DISPATCH_LIMIT
    provider = _email_provider()
    message_ids = _due_email_message_ids(limit=limit, now=now)

    processed_ids: list[int] = []
    skipped = 0
    for message_id in message_ids:
        dispatched = _dispatch_one_email_message(message_id, provider=provider, now=now)
        if dispatched:
            processed_ids.append(message_id)
        else:
            skipped += 1

    records = EmailDeliveryRecord.objects.filter(outbox_message_id__in=processed_ids)
    latest_records = {
        record.outbox_message_id: record
        for record in records.order_by("outbox_message_id", "attempt_number")
    }
    sent = sum(1 for record in latest_records.values() if record.status == EmailDeliveryStatus.SENT)
    failed = sum(
        1 for record in latest_records.values() if record.status == EmailDeliveryStatus.FAILED
    )
    dead_letter = OutboxMessage.objects.filter(
        id__in=processed_ids,
        status=OutboxStatus.DEAD_LETTER,
    ).count()
    return DispatchEmailOutboxResult(
        processed_count=len(processed_ids),
        sent_count=sent,
        failed_count=failed,
        dead_letter_count=dead_letter,
        skipped_count=skipped,
        message_ids=tuple(processed_ids),
    )


def dispatch_email_outbox_message_now(message_id: int) -> bool:
    """Dispatch one queued email immediately.

    Auth and step-up emails are time-sensitive. They still go through the
    durable outbox, but callers can ask for immediate delivery after their
    transaction commits so the scheduled dispatcher is only the retry fallback.
    """
    provider = _email_provider()
    return _dispatch_one_email_message(message_id, provider=provider, now=timezone.now())
