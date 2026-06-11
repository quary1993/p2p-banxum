from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from django.conf import settings


class PhoneProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PhoneVerificationStartResult:
    provider_reference: str
    provider_status: str


@dataclass(frozen=True, slots=True)
class PhoneVerificationCheckResult:
    approved: bool
    provider_status: str
    provider_reference: str = ""


def _twilio_verify_url(path: str) -> str:
    service_sid = str(settings.TWILIO_VERIFY_SERVICE_SID).strip()
    if not service_sid:
        raise PhoneProviderError("Twilio Verify service SID is not configured.")
    return f"https://verify.twilio.com/v2/Services/{urllib.parse.quote(service_sid)}/{path}"


def _twilio_auth_credentials() -> tuple[str, str]:
    api_key_sid = str(settings.TWILIO_API_KEY_SID).strip()
    api_key_secret = str(settings.TWILIO_API_KEY_SECRET).strip()
    if api_key_sid and api_key_secret:
        return api_key_sid, api_key_secret

    account_sid = str(settings.TWILIO_ACCOUNT_SID).strip()
    auth_token = str(settings.TWILIO_AUTH_TOKEN).strip()
    if account_sid and auth_token:
        return account_sid, auth_token

    raise PhoneProviderError("Twilio credentials are not configured.")


def _twilio_request(path: str, payload: dict[str, str]) -> dict[str, Any]:
    username, password = _twilio_auth_credentials()
    request = urllib.request.Request(
        _twilio_verify_url(path),
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, "https://verify.twilio.com/", username, password)
    opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(password_manager))
    try:
        with opener.open(request, timeout=settings.TWILIO_TIMEOUT_SECONDS) as response:
            if response.status < 200 or response.status >= 300:
                raise PhoneProviderError(f"Twilio Verify returned HTTP {response.status}.")
            return dict(json.loads(response.read().decode("utf-8")))
    except urllib.error.HTTPError as exc:
        raise PhoneProviderError(f"Twilio Verify returned HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise PhoneProviderError("Twilio Verify request failed.") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PhoneProviderError("Twilio Verify returned malformed JSON.") from exc


def start_twilio_verify(phone_number: str) -> PhoneVerificationStartResult:
    payload = _twilio_request(
        "Verifications",
        {
            "To": phone_number,
            "Channel": str(settings.TWILIO_VERIFY_CHANNEL).strip() or "sms",
        },
    )
    sid = str(payload.get("sid", "")).strip()
    status = str(payload.get("status", "")).strip()
    if not sid:
        raise PhoneProviderError("Twilio Verify response did not include a verification SID.")
    return PhoneVerificationStartResult(provider_reference=sid, provider_status=status)


def check_twilio_verify(phone_number: str, raw_code: str) -> PhoneVerificationCheckResult:
    payload = _twilio_request(
        "VerificationCheck",
        {
            "To": phone_number,
            "Code": raw_code,
        },
    )
    status = str(payload.get("status", "")).strip()
    sid = str(payload.get("sid", "")).strip()
    return PhoneVerificationCheckResult(
        approved=status == "approved",
        provider_status=status,
        provider_reference=sid,
    )
