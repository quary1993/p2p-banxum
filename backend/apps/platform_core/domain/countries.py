# IP of Webby-Soft SRL.
"""Country values entered as free text in the admin forms ("Switzerland", "CH", ...).

Borrower, Loan Originator and borrower-snapshot countries are free text. Rules that
depend on the country (the public site's ISO codes, the Swiss-borrower investor limit)
read them through ``country_code`` so every spelling counts the same way.
"""

from __future__ import annotations

from typing import Any

SWITZERLAND = "CH"

_COUNTRY_CODES_BY_NAME = {
    "switzerland": "CH",
    "schweiz": "CH",
    "suisse": "CH",
    "svizzera": "CH",
    "liechtenstein": "LI",
    "austria": "AT",
    "österreich": "AT",
    "osterreich": "AT",
    "belgium": "BE",
    "bulgaria": "BG",
    "croatia": "HR",
    "cyprus": "CY",
    "czechia": "CZ",
    "czech republic": "CZ",
    "denmark": "DK",
    "estonia": "EE",
    "finland": "FI",
    "france": "FR",
    "germany": "DE",
    "deutschland": "DE",
    "greece": "GR",
    "hungary": "HU",
    "iceland": "IS",
    "ireland": "IE",
    "italy": "IT",
    "italia": "IT",
    "latvia": "LV",
    "lithuania": "LT",
    "luxembourg": "LU",
    "malta": "MT",
    "monaco": "MC",
    "netherlands": "NL",
    "the netherlands": "NL",
    "norway": "NO",
    "poland": "PL",
    "portugal": "PT",
    "romania": "RO",
    "românia": "RO",
    "slovakia": "SK",
    "slovenia": "SI",
    "spain": "ES",
    "sweden": "SE",
    "united kingdom": "GB",
    "great britain": "GB",
    "united states": "US",
    "united states of america": "US",
}
_KNOWN_COUNTRY_CODES = frozenset(_COUNTRY_CODES_BY_NAME.values())


def country_code(value: Any) -> str:
    """ISO 3166-1 alpha-2 code for a stored country value, or "" when unknown."""
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) == 2 and text.isalpha():
        code = text.upper()
        return code if code in _KNOWN_COUNTRY_CODES else ""
    return _COUNTRY_CODES_BY_NAME.get(text.lower(), "")


def is_switzerland(value: Any) -> bool:
    """True for every spelling of Switzerland ("Switzerland", "CH", "Schweiz", ...)."""
    return country_code(value) == SWITZERLAND
