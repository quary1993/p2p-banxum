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

# Fields whose change makes a verification no longer current (Q13: essential change).
ESSENTIAL_FIELDS = (
    "security_type",
    "holder_name",
    "value_minor",
    "valuation_amount_minor",
    "valuation_currency",
    "undertaking_scope",
    "undertaking_limit_minor",
    "document_ids",
)


def required_proofs(
    security_type: str, configured: Mapping[str, Any] | None = None
) -> tuple[str, ...]:
    """The proof categories one security type needs (setting first, then the Q13 base)."""
    if configured and security_type in configured:
        value = configured[security_type]
        if isinstance(value, list | tuple):
            return tuple(str(item) for item in value)
    return DEFAULT_REQUIRED_PROOFS.get(security_type, ("agreement",))


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
        parts.append(f"{name}={value!r}")
    return "|".join(parts)
