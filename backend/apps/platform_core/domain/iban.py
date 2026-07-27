from __future__ import annotations

import re


class IbanValidationError(ValueError):
    pass


# ISO 13616 lengths for countries currently publishing IBAN formats. Keeping
# this registry here prevents a checksum-valid string with the wrong national
# length from being accepted as payout evidence.
IBAN_LENGTHS = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28,
    "BA": 20, "BE": 16, "BG": 22, "BH": 22, "BR": 29,
    "BY": 28, "CH": 21, "CR": 22, "CY": 28, "CZ": 24,
    "DE": 22, "DK": 18, "DO": 28, "EE": 20, "EG": 29,
    "ES": 24, "FI": 18, "FO": 18, "FR": 27, "GB": 22,
    "GE": 22, "GI": 23, "GL": 18, "GR": 27, "GT": 28,
    "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IQ": 23,
    "IS": 26, "IT": 27, "JO": 30, "KZ": 20, "KW": 30,
    "LB": 28, "LC": 32, "LI": 21, "LT": 20, "LU": 20,
    "LV": 21, "MC": 27, "MD": 24, "ME": 22, "MK": 19,
    "MR": 27, "MT": 31, "MU": 30, "NL": 18, "NO": 15,
    "PK": 24, "PL": 28, "PS": 29, "PT": 25, "QA": 29,
    "RO": 24, "RS": 22, "SA": 24, "SC": 31, "SE": 24,
    "SI": 19, "SK": 24, "SM": 27, "ST": 25, "SV": 28,
    "TL": 23, "TN": 24, "TR": 26, "UA": 29, "VA": 22,
    "VG": 24, "XK": 20,
}


def normalize_and_validate_iban(value: str) -> str:
    iban = re.sub(r"\s+", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]+", iban):
        raise IbanValidationError("IBAN has an invalid structure.")

    expected_length = IBAN_LENGTHS.get(iban[:2])
    if expected_length is None:
        raise IbanValidationError("IBAN country is not supported.")
    if len(iban) != expected_length:
        raise IbanValidationError("IBAN has an invalid length for its country.")

    remainder = 0
    for character in iban[4:] + iban[:4]:
        digits = character if character.isdigit() else str(ord(character) - 55)
        for digit in digits:
            remainder = (remainder * 10 + int(digit)) % 97
    if remainder != 1:
        raise IbanValidationError("IBAN checksum is invalid.")
    return iban
