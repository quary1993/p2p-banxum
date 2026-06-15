from __future__ import annotations

from uuid import UUID

LENDER_ACCOUNT_TYPES = frozenset(
    {
        "natural_person_lender",
        "legal_entity_lender_representative",
    }
)
REFERENCE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def is_lender_account_type(account_type: str) -> bool:
    return account_type in LENDER_ACCOUNT_TYPES


def investor_reference_from_uuid(value: UUID | str) -> str:
    uuid_value = value if isinstance(value, UUID) else UUID(str(value))
    number = uuid_value.int
    chars: list[str] = []
    for _ in range(8):
        number, remainder = divmod(number, len(REFERENCE_ALPHABET))
        chars.append(REFERENCE_ALPHABET[remainder])
    return "L" + "".join(reversed(chars))


def next_investor_reference_candidate(base_reference: str, attempt: int) -> str:
    if attempt == 0:
        return base_reference
    suffix = REFERENCE_ALPHABET[(attempt - 1) % len(REFERENCE_ALPHABET)]
    return f"{base_reference[:-1]}{suffix}"
