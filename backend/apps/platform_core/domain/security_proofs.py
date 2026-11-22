# IP of Webby-Soft SRL.
"""Proof that a security exists before publication (18.10, Q13, U33-DEC-38).

Publication of a new loan is blocked until each security that is not released has every document
its type needs and a named verification by a security verifier (role ``security_verifier`` or its
deputy). An essential change (type, holder or guarantor, value, scope or limit, documents) makes the
verification no longer current; a new verification is needed and the history stays.

The list per type below is the Q13 working base (legal validates it per type and jurisdiction);
the platform setting ``loans.security_required_proofs`` can replace it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

REQUIRED_PROOFS_SETTING = "loans.security_required_proofs"

PROOF_LABELS = {
    "land_register_extract": "Land register extract",
    "mortgage_note_or_pledge": "Mortgage note or pledge agreement",
    "guarantee_agreement": "Signed guarantee agreement",
    "pledge_or_assignment_agreement": "Pledge or assignment agreement",
    "third_party_debtor_notice": "Notice to the third-party debtor (where the law requires it)",
    "security_transfer_agreement": "Pledge or security transfer agreement",
    "asset_list": "List of the assets",
    "pledge_agreement": "Pledge agreement",
    "certificates_or_custody_confirmation": "Share certificates or custody confirmation",
    "blocked_account_confirmation": "Blocked account confirmation",
    "vehicle_registration": "Vehicle registration document",
    "agreement": "The security agreement",
}

DEFAULT_REQUIRED_PROOFS: dict[str, tuple[str, ...]] = {
    "real_estate": ("land_register_extract", "mortgage_note_or_pledge"),
    "corporate_guarantee": ("guarantee_agreement",),
    "personal_guarantee": ("guarantee_agreement",),
    # The notice to the debtor is needed only where the law requires it: not a fixed requirement.
    "receivables": ("pledge_or_assignment_agreement",),
    "invoices": ("pledge_or_assignment_agreement",),
    "equipment": ("security_transfer_agreement", "asset_list"),
    "inventory": ("security_transfer_agreement", "asset_list"),
    "vehicle": ("security_transfer_agreement", "vehicle_registration"),
    "securities_pledge": ("pledge_agreement", "certificates_or_custody_confirmation"),
    "share_pledge": ("pledge_agreement", "certificates_or_custody_confirmation"),
    "cash_collateral": ("blocked_account_confirmation",),
    "asset_backed": ("agreement",),
    "mixed_collateral": ("agreement",),
    "other": ("agreement",),
}

# Fields whose change makes a verification no longer current (Q13: essential change). Audit
# step 7 (D8) adds the fields that change legal priority, collateral value or the investor
# disclosure: rank, prior-ranking debt, valuation date, source and appraiser, LTV counting,
# valuation exchange rate and its date, and insurance.
ESSENTIAL_FIELDS = (
    "security_type",
    "holder_name",
    "value_minor",
    "valuation_amount_minor",
    "valuation_currency",
    "undertaking_scope",
    "undertaking_limit_minor",
    "document_ids",
    "asset_reference",
    "rank",
    "prior_ranking_debt_minor",
    "valuation_date",
    "valuation_source",
    "appraiser",
    "counts_in_ltv",
    "valuation_fx_rate",
    "valuation_fx_rate_date",
    "insurance",
)


class ProofConfigurationError(ValueError):
    """The setting ``loans.security_required_proofs`` is not valid."""


def validate_required_proofs_setting(value: Any) -> dict[str, tuple[str, ...]]:
    """Audit S7-3: the setting maps known security types to non-empty lists of known proof
    categories, without blanks or duplicates. An empty setting means the Q13 base."""
    if value in (None, {}):
        return {}
    if not isinstance(value, Mapping):
        raise ProofConfigurationError("The required-proof setting must map security types.")
    result: dict[str, tuple[str, ...]] = {}
    for security_type, proofs in value.items():
        if security_type not in DEFAULT_REQUIRED_PROOFS:
            raise ProofConfigurationError(f"Unknown security type: {security_type!r}.")
        if not isinstance(proofs, list | tuple) or not proofs:
            raise ProofConfigurationError(f"Give at least one proof for {security_type}.")
        keys = tuple(str(item).strip() for item in proofs)
        if any(not key for key in keys):
            raise ProofConfigurationError(f"A proof for {security_type} is blank.")
        unknown = [key for key in keys if key not in PROOF_LABELS]
        if unknown:
            raise ProofConfigurationError(f"Unknown proof for {security_type}: {unknown[0]!r}.")
        if len(set(keys)) != len(keys):
            raise ProofConfigurationError(f"A proof for {security_type} is given twice.")
        result[str(security_type)] = keys
    return result


def required_proofs(
    security_type: str, configured: Mapping[str, Any] | None = None
) -> tuple[str, ...]:
    """The proof categories one security type needs (setting first, then the Q13 base).

    ``configured`` must be the output of ``validate_required_proofs_setting``.
    """
    if configured and security_type in configured:
        return tuple(str(item) for item in configured[security_type])
    return DEFAULT_REQUIRED_PROOFS.get(security_type, ("agreement",))


def same_required_proofs(stored: Any, required: tuple[str, ...]) -> bool:
    """Audit S7-3: a verification is current only for the proof list it was made against."""
    return sorted(str(item) for item in stored or []) == sorted(required)


def missing_proofs(required: tuple[str, ...], provided: Mapping[str, Any]) -> tuple[str, ...]:
    """Required categories without a document in ``provided`` (category -> document id)."""
    return tuple(key for key in required if not str(provided.get(key) or "").strip())


def essential_fingerprint(values: Mapping[str, Any]) -> str:
    """A stable text of the essential fields; a different value means an essential change."""
    parts = []
    for name in ESSENTIAL_FIELDS:
        value = values.get(name)
        if name == "document_ids":
            value = sorted(str(item) for item in value or [])
        elif isinstance(value, Decimal):
            value = format(value.normalize(), "f")
        elif isinstance(value, date):
            value = value.isoformat()
        elif isinstance(value, str):
            value = value.strip()
        parts.append(f"{name}={value!r}")
    return "|".join(parts)
