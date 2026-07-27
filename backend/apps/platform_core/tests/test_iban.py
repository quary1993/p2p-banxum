from __future__ import annotations

import pytest

from backend.apps.platform_core.domain.iban import (
    IbanValidationError,
    normalize_and_validate_iban,
)


@pytest.mark.parametrize(
    ("raw_iban", "normalized"),
    [
        ("ch93 0076 2011 6238 5295 7", "CH9300762011623852957"),
        ("DE89 3704 0044 0532 0130 00", "DE89370400440532013000"),
        ("GB82 WEST 1234 5698 7654 32", "GB82WEST12345698765432"),
        ("RO49 AAAA 1B31 0075 9384 0000", "RO49AAAA1B31007593840000"),
    ],
)
def test_normalize_and_validate_iban_accepts_valid_country_examples(
    raw_iban: str,
    normalized: str,
) -> None:
    assert normalize_and_validate_iban(raw_iban) == normalized


@pytest.mark.parametrize(
    "invalid_iban",
    [
        "CH9300762011623852958",  # Checksum mismatch.
        "DE8937040044053201300",  # Wrong German national length.
        "ZZ1100000000000000000000",  # Unsupported country code.
        "not-an-iban",
    ],
)
def test_normalize_and_validate_iban_rejects_invalid_values(invalid_iban: str) -> None:
    with pytest.raises(IbanValidationError):
        normalize_and_validate_iban(invalid_iban)
