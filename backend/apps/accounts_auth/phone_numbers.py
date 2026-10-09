from __future__ import annotations

import re

# E.164: "+", a country code that does not start with 0, at most 15 digits in all.
E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")
_SEPARATORS = re.compile(r"[\s().\-/]")


class InvalidPhoneNumberError(ValueError):
    pass


def normalize_e164_phone_number(value: str) -> str:
    """Return the number in E.164 form ("+41790000000") or raise.

    Spaces, dots, dashes, slashes and brackets are dropped; a leading "00" is read as
    "+". Anything else must already be a full international number.
    """

    compact = _SEPARATORS.sub("", str(value or "").strip())
    if compact.startswith("00"):
        compact = f"+{compact[2:]}"
    if not E164_PATTERN.fullmatch(compact):
        raise InvalidPhoneNumberError(
            "Enter the mobile number in international format, for example +41 79 123 45 67."
        )
    return compact
