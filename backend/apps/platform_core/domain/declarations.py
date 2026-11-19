# IP of Webby-Soft SRL.
"""Investor self-declarations and compliance reviews (18.10, Q12, U33-DEC-27).

Pure rules: the answer choices, the validation of one declaration and the review triggers. The
records, reviews and re-verification dates live in ``backend.apps.kyc_compliance``.

A review is an analysis, not a refusal. While a necessary review is open, the investor cannot make a
new investment, reservation or resale purchase; the account, documents and existing investments stay
accessible.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

# Staff roles (18.10): granted to admin accounts by a superadmin.
ROLE_COMPLIANCE = "compliance"
ROLE_COMPLIANCE_DEPUTY = "compliance_deputy"
ROLE_SECURITY_VERIFIER = "security_verifier"
ROLE_SECURITY_VERIFIER_DEPUTY = "security_verifier_deputy"
STAFF_ROLES = (
    ROLE_COMPLIANCE,
    ROLE_COMPLIANCE_DEPUTY,
    ROLE_SECURITY_VERIFIER,
    ROLE_SECURITY_VERIFIER_DEPUTY,
)
COMPLIANCE_ROLES = frozenset({ROLE_COMPLIANCE, ROLE_COMPLIANCE_DEPUTY})
SECURITY_VERIFIER_ROLES = frozenset({ROLE_SECURITY_VERIFIER, ROLE_SECURITY_VERIFIER_DEPUTY})

SUBJECT_PERSON = "person"
SUBJECT_COMPANY = "company"

SOURCES_OF_FUNDS = (
    "salary",
    "savings",
    "sale_of_property",
    "inheritance",
    "business_income",
    "dividends",
    "investment_income",
    "rent",
    "other",
)
PEP_ANSWERS = ("no", "yes", "not_sure")
VOLUME_BANDS = ("under_10k", "10k_50k", "50k_250k", "over_250k")

TRIGGER_PEP = "pep"
TRIGGER_BENEFICIAL_OWNER = "beneficial_owner_other_person"
TRIGGER_SOURCE_OTHER = "source_of_funds_other"
TRIGGER_VOLUME = "volume_over_250k"

TRIGGER_LABELS = {
    TRIGGER_PEP: "PEP: Yes or Not sure",
    TRIGGER_BENEFICIAL_OWNER: "The beneficial owner of the funds is another person",
    TRIGGER_SOURCE_OTHER: "Source of funds: Other",
    TRIGGER_VOLUME: "Expected yearly volume over 250,000",
}

# Re-verification notices, days before the date set by compliance.
REVERIFICATION_NOTICE_DAYS = (30, 7)


class DeclarationError(ValueError):
    """A declaration that cannot be accepted, with a message for the investor."""


@dataclass(frozen=True)
class DeclarationAnswers:
    subject_type: str
    beneficial_owner_is_self: bool
    beneficial_owner_name: str
    sources_of_funds: tuple[str, ...]
    savings_origin: str
    source_other_text: str
    pep_status: str
    pep_person: str
    pep_relation: str
    pep_function: str
    pep_country: str
    yearly_volume_band: str
    company_details: Mapping[str, Any]


def _text(value: Any) -> str:
    return str(value or "").strip()


def validate_declaration(data: Mapping[str, Any]) -> DeclarationAnswers:
    """Check one submitted declaration and return its normalized answers."""
    subject = _text(data.get("subject_type")) or SUBJECT_PERSON
    if subject not in (SUBJECT_PERSON, SUBJECT_COMPANY):
        raise DeclarationError("Choose a person or a company declaration.")
    owner_is_self = data.get("beneficial_owner_is_self")
    if not isinstance(owner_is_self, bool):
        raise DeclarationError("Say whether you are the beneficial owner of the funds.")
    owner_name = _text(data.get("beneficial_owner_name"))
    if not owner_is_self and not owner_name:
        raise DeclarationError("Enter the name of the beneficial owner of the funds.")
    raw_sources = data.get("sources_of_funds") or []
    if isinstance(raw_sources, str) or not isinstance(raw_sources, Iterable):
        raise DeclarationError("Choose at least one source of funds.")
    sources = tuple(dict.fromkeys(_text(item) for item in raw_sources if _text(item)))
    if not sources:
        raise DeclarationError("Choose at least one source of funds.")
    unknown = [item for item in sources if item not in SOURCES_OF_FUNDS]
    if unknown:
        raise DeclarationError(f"Unknown source of funds: {', '.join(unknown)}.")
    savings_origin = _text(data.get("savings_origin"))
    if "savings" in sources and not savings_origin:
        raise DeclarationError("Say where your savings come from.")
    other_text = _text(data.get("source_other_text"))
    if "other" in sources and not other_text:
        raise DeclarationError("Explain the other source of funds.")
    pep = _text(data.get("pep_status"))
    if pep not in PEP_ANSWERS:
        raise DeclarationError("Answer the question about politically exposed persons.")
    pep_fields = {
        name: _text(data.get(name))
        for name in ("pep_person", "pep_relation", "pep_function", "pep_country")
    }
    if pep == "yes" and not all(pep_fields.values()):
        raise DeclarationError(
            "For a politically exposed person, enter the person, the relation, the function and "
            "the country."
        )
    band = _text(data.get("yearly_volume_band"))
    if band not in VOLUME_BANDS:
        raise DeclarationError("Choose your expected yearly investment volume.")
    company = data.get("company_details") or {}
    if not isinstance(company, Mapping):
        raise DeclarationError("Company details are not valid.")
    if subject == SUBJECT_COMPANY:
        for key, label in (
            ("company_name", "the company name"),
            ("representative_name", "the representative"),
            ("representative_authority", "the representative's authority"),
            ("controlling_persons", "the controlling persons"),
        ):
            if not _text(company.get(key)):
                raise DeclarationError(f"Enter {label}.")
    return DeclarationAnswers(
        subject_type=subject,
        beneficial_owner_is_self=owner_is_self,
        beneficial_owner_name="" if owner_is_self else owner_name,
        sources_of_funds=sources,
        savings_origin=savings_origin if "savings" in sources else "",
        source_other_text=other_text if "other" in sources else "",
        pep_status=pep,
        pep_person=pep_fields["pep_person"] if pep == "yes" else "",
        pep_relation=pep_fields["pep_relation"] if pep == "yes" else "",
        pep_function=pep_fields["pep_function"] if pep == "yes" else "",
        pep_country=pep_fields["pep_country"] if pep == "yes" else "",
        yearly_volume_band=band,
        company_details={str(k): _text(v) for k, v in company.items()}
        if subject == SUBJECT_COMPANY
        else {},
    )


def review_triggers(answers: DeclarationAnswers) -> tuple[str, ...]:
    """The Q12 cases that open a necessary review (compliance can add others by hand)."""
    triggers: list[str] = []
    if answers.pep_status in ("yes", "not_sure"):
        triggers.append(TRIGGER_PEP)
    if not answers.beneficial_owner_is_self:
        triggers.append(TRIGGER_BENEFICIAL_OWNER)
    if "other" in answers.sources_of_funds:
        triggers.append(TRIGGER_SOURCE_OTHER)
    if answers.yearly_volume_band == "over_250k":
        triggers.append(TRIGGER_VOLUME)
    return tuple(triggers)


def has_staff_role(user: Any, roles: Iterable[str]) -> bool:
    """True when the user holds one of ``roles`` (stored on the account as a list)."""
    held = getattr(user, "staff_roles", None) or []
    wanted = set(roles)
    return any(str(role) in wanted for role in held)
