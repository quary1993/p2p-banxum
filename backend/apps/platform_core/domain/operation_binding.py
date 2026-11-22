"""IP of Webby-Soft SRL. 18.5 (U33-DEC-01): the email code of an operation is bound to it.

The investor asks for the email code with the details of the operation (amount, currency,
account, loan, listing, price). The email shows a short summary of these details. At
confirmation, the module that runs the operation builds the same details from its own data;
the code works only when both fingerprints match. A code for 100 EUR cannot confirm 1,000 EUR,
and a code for one bank account cannot add another.

Each action accepts one of a few fixed sets of fields. Values are normalized before the
fingerprint (amounts as whole minor units, currencies and IBANs in capitals without spaces,
ids in lower case), so the client and the server get the same result for the same operation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal

BOUND_ACTIONS: dict[str, tuple[frozenset[str], ...]] = {
    "withdrawal": (frozenset({"amount_minor", "currency", "iban"}),),
    "bank_account_change": (
        frozenset({"currency", "iban"}),
        frozenset({"instruction_id"}),
    ),
    "fx": (frozenset({"amount_minor", "source_currency", "target_currency"}),),
    "primary_investment": (frozenset({"amount_minor", "currency", "loan_id"}),),
    "secondary_market_listing": (
        frozenset({"holding_id", "price_bps"}),
        frozenset({"listing_id", "price_bps"}),
    ),
    "secondary_market_purchase": (frozenset({"amount_minor", "currency", "listing_id"}),),
}

_INTEGER_FIELDS = frozenset({"amount_minor", "price_bps"})
_CURRENCY_FIELDS = frozenset({"currency", "source_currency", "target_currency"})
_ID_FIELDS = frozenset({"holding_id", "instruction_id", "listing_id", "loan_id"})


class OperationBindingError(ValueError):
    pass


def is_bound_action(action: str) -> bool:
    return str(action) in BOUND_ACTIONS


def _normalized_value(key: str, value: object) -> str:
    if key in _INTEGER_FIELDS:
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise OperationBindingError(f"{key} must be a whole number.") from exc
        # A resale price can be 0 % of the principal (the buyer pays only the interest).
        if number < 0 or (number == 0 and key != "price_bps"):
            raise OperationBindingError(f"{key} must be more than zero.")
        return str(number)
    text = str(value if value is not None else "").strip()
    if key in _CURRENCY_FIELDS:
        text = text.upper()
        if len(text) != 3 or not text.isalpha():
            raise OperationBindingError(f"{key} must be a 3-letter currency code.")
        return text
    if key == "iban":
        text = "".join(text.split()).upper()
        if len(text) < 15 or len(text) > 34 or not text.isalnum():
            raise OperationBindingError("iban is not a valid IBAN.")
        return text
    if key in _ID_FIELDS:
        text = text.lower()
        if not text or len(text) > 64:
            raise OperationBindingError(f"{key} is required.")
        return text
    raise OperationBindingError(f"{key} is not an operation field.")


def normalized_operation(action: str, details: Mapping[str, object]) -> dict[str, str]:
    """The details in canonical form; refuses unknown actions and wrong sets of fields."""
    shapes = BOUND_ACTIONS.get(str(action))
    if shapes is None:
        raise OperationBindingError("This action is not bound to operation details.")
    keys = frozenset(str(key) for key in details)
    if keys not in shapes:
        expected = " or ".join(", ".join(sorted(shape)) for shape in shapes)
        raise OperationBindingError(f"Send the operation details: {expected}.")
    return {str(key): _normalized_value(str(key), value) for key, value in details.items()}


def operation_fingerprint(action: str, details: Mapping[str, object]) -> str:
    canonical = json.dumps(
        {"action": str(action), "details": normalized_operation(action, details)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _money(amount_minor: str, currency: str) -> str:
    value = (Decimal(int(amount_minor)) / Decimal(100)).quantize(Decimal("0.01"))
    return f"{value:,.2f} {currency}"


def _ending(iban: str) -> str:
    return f"IBAN ending {iban[-4:]}"


def operation_summary(action: str, details: Mapping[str, object]) -> str:
    """One line for the email: what the code confirms (no full IBAN)."""
    values = normalized_operation(action, details)
    if action == "withdrawal":
        return (
            f"Withdrawal of {_money(values['amount_minor'], values['currency'])} "
            f"to {_ending(values['iban'])}"
        )
    if action == "bank_account_change":
        if "iban" in values:
            return f"New {values['currency']} bank account, {_ending(values['iban'])}"
        return "Change of the default return account"
    if action == "fx":
        return (
            "Currency exchange of "
            f"{_money(values['amount_minor'], values['source_currency'])} "
            f"to {values['target_currency']}"
        )
    if action == "primary_investment":
        return (
            f"Investment of {_money(values['amount_minor'], values['currency'])} "
            f"in loan {values['loan_id'][:8]}"
        )
    if action == "secondary_market_listing":
        price = (Decimal(int(values["price_bps"])) / Decimal(100)).quantize(Decimal("0.01"))
        return f"Resale listing at {price}% of the outstanding principal"
    if action == "secondary_market_purchase":
        return (
            f"Resale purchase for {_money(values['amount_minor'], values['currency'])} "
            f"(listing {values['listing_id'][:8]})"
        )
    raise OperationBindingError("This action is not bound to operation details.")
