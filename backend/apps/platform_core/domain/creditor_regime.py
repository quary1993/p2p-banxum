"""IP of Webby-Soft SRL. 18.9 (Q03, F06-F09, E-02): Swiss creditor modes, the rules only.

Each Swiss borrower (one UID) is in one mode, pre-selected "sandbox" and confirmed by an admin:

- ``sandbox``: the total ``T`` of the borrower stays below CHF 500,000; no creditor limit (the
  sandbox's CHF 1 million limit is then always met).
- ``ten_twenty``: at most 10 relevant creditors per financing and 20 per borrower, at any total.

Switching: to 10/20 only when the borrower has at most 20 relevant creditors and every open
financing at most 10; to sandbox only when ``T`` is below CHF 500,000; never while a project of the
borrower is in funding.

Where a creditor limit applies, a participation that takes a new place must invest at least:

    minimum = min(R, max(usual minimum, round up to whole units of max(0, P - F) / N))

``P`` the success threshold of the offer, ``F`` the amount already allocated, ``R`` the amount still
open, ``N`` the places really left under all limits. Money in integer minor units; the WW (legal)
validation gates real use (IMPLEMENTATION_PLAN 18.0).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MODE_SANDBOX = "sandbox"
MODE_TEN_TWENTY = "ten_twenty"
MODES = {MODE_SANDBOX: "Sandbox", MODE_TEN_TWENTY: "10/20"}

SANDBOX_TOTAL_LIMIT_CHF_MINOR = 500_000_00
FINANCING_CREDITOR_LIMIT = 10
BORROWER_CREDITOR_LIMIT = 20
WHOLE_UNIT_MINOR = 100

SANDBOX_NOTICE_TEXT_SETTING = "swiss.sandbox_notice_text"
SANDBOX_NOTICE_APPROVED_SETTING = "swiss.sandbox_notice_approved"
SANDBOX_NOTICE_PLACEHOLDER = (
    "[Placeholder - legal text pending] {borrower} operates under the Swiss sandbox exemption "
    "from the banking licence and is not supervised by FINMA. Your investment is not covered by "
    "the Swiss deposit protection."
)

_UID_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4)
_UID_PATTERN = re.compile(r"^CHE(\d{9})$")


class CreditorRegimeError(ValueError):
    pass


def normalize_uid(value: str) -> str:
    """'CHE-123.456.788' / 'che123456788' -> 'CHE-123.456.788'; checks the mod-11 digit."""
    compact = re.sub(r"[\s.\-]", "", str(value or "")).upper()
    for suffix in ("MWST", "TVA", "IVA", "HR"):
        if compact.endswith(suffix):
            compact = compact[: -len(suffix)]
    match = _UID_PATTERN.match(compact)
    if match is None:
        raise CreditorRegimeError("Enter the Swiss UID of the borrower (CHE-123.456.789).")
    digits = match.group(1)
    total = sum(int(digit) * weight for digit, weight in zip(digits[:8], _UID_WEIGHTS, strict=True))
    check = 11 - total % 11
    if check == 11:
        check = 0
    if check == 10 or check != int(digits[8]):
        raise CreditorRegimeError("This Swiss UID is not valid (check digit).")
    return f"CHE-{digits[0:3]}.{digits[3:6]}.{digits[6:9]}"


def require_mode(value: str) -> str:
    mode = str(value or "").strip()
    if mode not in MODES:
        raise CreditorRegimeError("Choose the creditor mode: sandbox or 10/20.")
    return mode


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def dynamic_minimum_minor(
    *,
    usual_minimum_minor: int,
    remaining_minor: int,
    threshold_minor: int,
    allocated_minor: int,
    places_left: int,
) -> int | None:
    """What a participation that takes a new place must invest now; None when no place is left."""
    if places_left <= 0:
        return None
    remaining = max(0, remaining_minor)
    missing = max(0, threshold_minor - allocated_minor)
    share = _ceil_div(missing, places_left) if missing else 0
    share = _ceil_div(share, WHOLE_UNIT_MINOR) * WHOLE_UNIT_MINOR
    return min(remaining, max(usual_minimum_minor, share))


@dataclass(frozen=True, slots=True)
class RegimeCheck:
    ok: bool
    message: str = ""


def check_sandbox_total(total_chf_minor: int) -> RegimeCheck:
    if total_chf_minor >= SANDBOX_TOTAL_LIMIT_CHF_MINOR:
        return RegimeCheck(
            False,
            "In sandbox mode the borrower's total must stay below CHF 500,000 (now CHF "
            f"{total_chf_minor / 100:,.2f}). Switch the borrower to the 10/20 mode first.",
        )
    return RegimeCheck(True)


def check_ten_twenty(*, financing_creditors: int, borrower_creditors: int) -> RegimeCheck:
    if financing_creditors > FINANCING_CREDITOR_LIMIT:
        return RegimeCheck(
            False,
            f"In 10/20 mode a financing may have at most {FINANCING_CREDITOR_LIMIT} creditors "
            f"(now {financing_creditors}).",
        )
    if borrower_creditors > BORROWER_CREDITOR_LIMIT:
        return RegimeCheck(
            False,
            f"In 10/20 mode a borrower may have at most {BORROWER_CREDITOR_LIMIT} creditors "
            f"(now {borrower_creditors}).",
        )
    return RegimeCheck(True)


def synthetic_uid(seed: int) -> str:
    """A valid UID for demo and QA data only (never a real company): base 9xx.xxx.xx + check."""
    value = 90_000_000 + seed % 10_000_000
    while True:
        digits = f"{value:08d}"
        total = sum(int(digit) * weight for digit, weight in zip(digits, _UID_WEIGHTS, strict=True))
        check = 11 - total % 11
        if check == 11:
            check = 0
        if check != 10:
            text = f"{digits}{check}"
            return f"CHE-{text[0:3]}.{text[3:6]}.{text[6:9]}"
        value += 1
