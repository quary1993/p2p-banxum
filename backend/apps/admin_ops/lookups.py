from __future__ import annotations

import re
from datetime import date, datetime
from functools import lru_cache
from typing import Any, cast

from django.apps import apps
from django.db.models import CharField, Q, QuerySet
from django.db.models.functions import Cast

from backend.apps.platform_core.domain.money import minor_units_to_decimal

LOOKUP_MIN_QUERY_LENGTH = 3
LOOKUP_MAX_LIMIT = 50
INVESTOR_REFERENCE_RE = re.compile(r"L[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{8,9}", re.IGNORECASE)
LENDER_ACCOUNT_TYPES = frozenset(
    {
        "natural_person_lender",
        "legal_entity_lender_representative",
    }
)


def _model(app_label: str, model_name: str) -> Any:
    return apps.get_model(app_label, model_name)


def _limit(value: int | None) -> int:
    if value is None:
        return 20
    return max(1, min(value, LOOKUP_MAX_LIMIT))


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _query_ready(value: str | None) -> bool:
    return len(_clean(value)) >= LOOKUP_MIN_QUERY_LENGTH


def _uuid_searchable(queryset: QuerySet[Any]) -> QuerySet[Any]:
    return cast(QuerySet[Any], queryset.annotate(id_text=Cast("id", output_field=CharField())))


def _tokenized_user_filter(query: str) -> Q:
    tokens = [token for token in query.replace(",", " ").split() if token]
    if not tokens:
        return Q()
    combined = Q()
    for token in tokens:
        extracted_reference = _extract_investor_reference(token)
        reference_filter = (
            Q(investor_reference__iexact=extracted_reference)
            if extracted_reference
            else Q(pk__isnull=True)
        )
        combined &= (
            Q(id_text__icontains=token)
            | Q(email__icontains=token)
            | Q(full_name__icontains=token)
            | Q(investor_reference__icontains=token)
            | reference_filter
        )
    return combined


def _extract_investor_reference(value: str) -> str:
    match = INVESTOR_REFERENCE_RE.search(value.upper())
    return match.group(0) if match else ""


def _iban_suffix(value: str) -> str:
    compact = value.replace(" ", "")
    if len(compact) <= 8:
        return compact
    return compact[-8:]


def _date_label(value: date | datetime | None) -> str:
    if value is None:
        return "-"
    return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()


@lru_cache(maxsize=64)
def _currency_minor_units(currency: str) -> int:
    currency_model = _model("platform_core", "Currency")
    currency_obj = currency_model.objects.filter(code=currency.upper()).only("minor_units").first()
    return int(getattr(currency_obj, "minor_units", 2) if currency_obj is not None else 2)


def _money_label(amount_minor: int, currency: str) -> str:
    normalized_currency = currency.upper() or "CHF"
    minor_units = _currency_minor_units(normalized_currency)
    amount = minor_units_to_decimal(amount_minor, minor_units=minor_units)
    formatted = f"{amount:,.{minor_units}f}".replace(",", "'")
    return f"{normalized_currency} {formatted}"


def _user_result(
    user: Any, *, kind: str = "user", payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    reference = str(getattr(user, "investor_reference", "") or "")
    email = str(getattr(user, "email", ""))
    full_name = str(getattr(user, "full_name", ""))
    account_type = str(getattr(user, "account_type", ""))
    status = str(getattr(user, "status", ""))
    meta_parts = [part for part in (reference, email, account_type, status) if part]
    return {
        "id": str(user.pk),
        "kind": kind,
        "label": full_name or email or str(user.pk),
        "meta": " / ".join(meta_parts),
        "payload": {
            "email": email,
            "full_name": full_name,
            "investor_reference": reference,
            "account_type": account_type,
            "status": status,
            **(payload or {}),
        },
    }


def lookup_users(
    *, query: str = "", account_type: str = "", status: str = "", limit: int | None = 20
) -> list[dict[str, Any]]:
    if not _query_ready(query):
        return []
    user_model = _model("accounts_auth", "User")
    queryset = _uuid_searchable(user_model.objects.all())
    queryset = queryset.filter(_tokenized_user_filter(_clean(query)))
    if account_type:
        queryset = queryset.filter(account_type=account_type)
    if status:
        queryset = queryset.filter(status=status)
    return [
        _user_result(user)
        for user in queryset.order_by("full_name", "email", "id")[: _limit(limit)]
    ]


def lookup_investors(
    *,
    query: str = "",
    iban: str = "",
    status: str = "",
    limit: int | None = 20,
) -> list[dict[str, Any]]:
    user_model = _model("accounts_auth", "User")
    queryset = _uuid_searchable(user_model.objects.filter(account_type__in=LENDER_ACCOUNT_TYPES))
    query_filter = _tokenized_user_filter(_clean(query)) if _query_ready(query) else Q()
    iban_query = _clean(iban).replace(" ", "")
    matched_by_iban: dict[str, list[Any]] = {}
    if len(iban_query) >= LOOKUP_MIN_QUERY_LENGTH:
        instruction_model = _model("ledger", "InvestorPayoutInstruction")
        instruction_queryset = instruction_model.objects.filter(
            destination_iban__icontains=iban_query
        )
        investor_ids = [str(row.investor_user_id) for row in instruction_queryset[:100]]
        if investor_ids:
            query_filter |= Q(id__in=investor_ids)
        for instruction in instruction_queryset:
            matched_by_iban.setdefault(str(instruction.investor_user_id), []).append(instruction)
    if not query_filter:
        return []
    queryset = queryset.filter(query_filter)
    if status:
        queryset = queryset.filter(status=status)
    results: list[dict[str, Any]] = []
    collision_count = len(matched_by_iban) if matched_by_iban else 0
    for user in queryset.order_by("full_name", "email", "id")[: _limit(limit)]:
        instructions = matched_by_iban.get(str(user.pk), [])
        payload: dict[str, Any] = {"iban_match_count": collision_count}
        if instructions:
            instruction = instructions[0]
            payload.update(
                {
                    "matched_iban_suffix": _iban_suffix(str(instruction.destination_iban)),
                    "matched_payout_instruction_id": str(instruction.pk),
                    "matched_payout_status": str(instruction.status),
                }
            )
        results.append(_user_result(user, kind="investor", payload=payload))
    return results


def lookup_borrowers(
    *, query: str = "", status: str = "", limit: int | None = 20
) -> list[dict[str, Any]]:
    if not _query_ready(query):
        return []
    borrower_model = _model("entities", "BorrowerEntity")
    queryset = _uuid_searchable(borrower_model.objects.all())
    cleaned = _clean(query)
    queryset = queryset.filter(
        Q(id_text__icontains=cleaned)
        | Q(legal_name__icontains=cleaned)
        | Q(registration_number__icontains=cleaned)
        | Q(country__icontains=cleaned)
    )
    if status:
        queryset = queryset.filter(kyb_status=status)
    results: list[dict[str, Any]] = []
    for borrower in queryset.order_by("legal_name", "id")[: _limit(limit)]:
        results.append(
            {
                "id": str(borrower.pk),
                "kind": "borrower",
                "label": str(getattr(borrower, "legal_name", "")),
                "meta": (
                    f"{getattr(borrower, 'country', '') or 'country n/a'} / "
                    f"{getattr(borrower, 'kyb_status', '') or 'KYB n/a'} / "
                    f"{getattr(borrower, 'registration_number', '') or 'reg n/a'}"
                ),
                "payload": {
                    "legal_name": str(getattr(borrower, "legal_name", "")),
                    "registration_number": str(getattr(borrower, "registration_number", "")),
                    "country": str(getattr(borrower, "country", "")),
                    "kyb_status": str(getattr(borrower, "kyb_status", "")),
                    "compliance_hold": bool(getattr(borrower, "compliance_hold", False)),
                },
            }
        )
    return results


def lookup_loans(
    *, query: str = "", status: str = "", borrower_id: str = "", limit: int | None = 20
) -> list[dict[str, Any]]:
    if not _query_ready(query) and not borrower_id:
        return []
    loan_model = _model("loans", "Loan")
    queryset = _uuid_searchable(loan_model.objects.select_related("borrower", "currency").all())
    cleaned = _clean(query)
    if _query_ready(cleaned):
        queryset = queryset.filter(
            Q(id_text__icontains=cleaned)
            | Q(title__icontains=cleaned)
            | Q(status__icontains=cleaned)
            | Q(borrower__legal_name__icontains=cleaned)
        )
    if status:
        queryset = queryset.filter(status=status)
    if borrower_id:
        queryset = queryset.filter(borrower_id=borrower_id)
    results: list[dict[str, Any]] = []
    for loan in queryset.order_by("-created_at", "title", "id")[: _limit(limit)]:
        currency = str(
            getattr(getattr(loan, "currency", None), "code", getattr(loan, "currency_id", ""))
        )
        borrower = getattr(loan, "borrower", None)
        borrower_name = str(getattr(borrower, "legal_name", ""))
        results.append(
            {
                "id": str(loan.pk),
                "kind": "loan",
                "label": str(getattr(loan, "title", "")),
                "meta": (
                    f"{borrower_name or 'borrower n/a'} / {getattr(loan, 'status', '')} / "
                    f"{_money_label(int(getattr(loan, 'principal_minor', 0)), currency)}"
                ),
                "payload": {
                    "borrower_id": str(getattr(loan, "borrower_id", "")),
                    "borrower_name": borrower_name,
                    "status": str(getattr(loan, "status", "")),
                    "currency": currency,
                    "principal_minor": int(getattr(loan, "principal_minor", 0)),
                    "committed_principal_minor": int(getattr(loan, "committed_principal_minor", 0)),
                    "funding_deadline": _date_label(getattr(loan, "funding_deadline", None)),
                },
            }
        )
    return results


def lookup_kyc_cases(
    *, query: str = "", status: str = "", limit: int | None = 20
) -> list[dict[str, Any]]:
    if not _query_ready(query):
        return []
    case_model = _model("kyc_compliance", "KycVerificationCase")
    queryset = _uuid_searchable(case_model.objects.select_related("user").all())
    cleaned = _clean(query)
    queryset = queryset.filter(
        Q(id_text__icontains=cleaned)
        | Q(subject_reference__icontains=cleaned)
        | Q(vendor_data__icontains=cleaned)
        | Q(provider_session_id__icontains=cleaned)
        | Q(provider_verification_id__icontains=cleaned)
        | Q(user__email__icontains=cleaned)
        | Q(user__full_name__icontains=cleaned)
        | Q(user__investor_reference__icontains=cleaned)
    )
    if status:
        queryset = queryset.filter(status=status)
    results: list[dict[str, Any]] = []
    for case in queryset.order_by("-updated_at", "-created_at", "id")[: _limit(limit)]:
        user = getattr(case, "user", None)
        label = str(getattr(user, "full_name", "") or getattr(case, "subject_reference", ""))
        user_email = str(getattr(user, "email", ""))
        case_status = str(getattr(case, "status", ""))
        case_reference = str(getattr(case, "subject_reference", ""))
        results.append(
            {
                "id": str(case.pk),
                "kind": "kyc_case",
                "label": label,
                "meta": f"{case_status} / {user_email or case_reference}",
                "payload": {
                    "user_id": str(getattr(case, "user_id", "")),
                    "user_email": user_email,
                    "user_full_name": str(getattr(user, "full_name", "")),
                    "investor_reference": str(getattr(user, "investor_reference", "") or ""),
                    "status": str(getattr(case, "status", "")),
                    "subject_type": str(getattr(case, "subject_type", "")),
                    "subject_reference": str(getattr(case, "subject_reference", "")),
                    "manual_review_required": bool(getattr(case, "manual_review_required", False)),
                    "risk_classification": str(getattr(case, "risk_classification", "") or ""),
                    "detected_flags": list(getattr(case, "detected_flags", []) or []),
                    "blocking_reason": str(getattr(case, "blocking_reason", "") or ""),
                    "decision_at": _date_label(getattr(case, "decision_at", None)),
                    "provider_session_id": str(getattr(case, "provider_session_id", "")),
                    "provider_verification_id": str(getattr(case, "provider_verification_id", "")),
                    "provider_report_id": str(getattr(case, "provider_report_id", "") or ""),
                    "aml_screening_id": str(getattr(case, "aml_screening_id", "") or ""),
                },
            }
        )
    return results


def lookup_withdrawals(
    *, query: str = "", status: str = "", limit: int | None = 20
) -> list[dict[str, Any]]:
    if not _query_ready(query):
        return []
    withdrawal_model = _model("ledger", "InvestorWithdrawalRequest")
    user_model = _model("accounts_auth", "User")
    cleaned = _clean(query)
    user_ids = list(
        _uuid_searchable(user_model.objects.filter(account_type__in=LENDER_ACCOUNT_TYPES))
        .filter(_tokenized_user_filter(cleaned))
        .values_list("id", flat=True)[:100]
    )
    queryset = _uuid_searchable(withdrawal_model.objects.select_related("currency").all()).filter(
        Q(id_text__icontains=cleaned)
        | Q(investor_user_id__in=user_ids)
        | Q(destination_iban__icontains=cleaned)
        | Q(destination_account_name__icontains=cleaned)
    )
    if status:
        queryset = queryset.filter(status=status)
    users = {
        str(user.pk): user
        for user in user_model.objects.filter(
            id__in=list(queryset.values_list("investor_user_id", flat=True)[:100])
        )
    }
    results: list[dict[str, Any]] = []
    for request in queryset.order_by("requested_at", "id")[: _limit(limit)]:
        user = users.get(str(getattr(request, "investor_user_id", "")))
        currency = str(
            getattr(getattr(request, "currency", None), "code", getattr(request, "currency_id", ""))
        )
        investor_label = str(
            getattr(user, "full_name", "")
            or getattr(user, "email", "")
            or getattr(request, "investor_user_id", "")
        )
        results.append(
            {
                "id": str(request.pk),
                "kind": "withdrawal_request",
                "label": f"{investor_label} - {_money_label(int(request.amount_minor), currency)}",
                "meta": (
                    f"{request.status} / requested {_date_label(request.requested_at)} / "
                    f"IBAN ...{_iban_suffix(str(request.destination_iban))}"
                ),
                "payload": {
                    "investor_user_id": str(request.investor_user_id),
                    "investor_name": str(getattr(user, "full_name", "")),
                    "investor_email": str(getattr(user, "email", "")),
                    "investor_reference": str(getattr(user, "investor_reference", "") or ""),
                    "status": str(request.status),
                    "amount_minor": int(request.amount_minor),
                    "currency": currency,
                    "requested_at": _date_label(request.requested_at),
                    "iban_suffix": _iban_suffix(str(request.destination_iban)),
                    "is_forced": bool(request.is_forced),
                },
            }
        )
    return results


def lookup_primary_orders(
    *, query: str = "", status: str = "", limit: int | None = 20
) -> list[dict[str, Any]]:
    if not _query_ready(query):
        return []
    order_model = _model("marketplace_primary", "PrimaryInvestmentOrder")
    user_model = _model("accounts_auth", "User")
    cleaned = _clean(query)
    user_ids = list(
        _uuid_searchable(user_model.objects.filter(account_type__in=LENDER_ACCOUNT_TYPES))
        .filter(_tokenized_user_filter(cleaned))
        .values_list("id", flat=True)[:100]
    )
    queryset = _uuid_searchable(
        order_model.objects.select_related("loan", "currency").all()
    ).filter(
        Q(id_text__icontains=cleaned)
        | Q(investor_user_id__in=user_ids)
        | Q(loan__title__icontains=cleaned)
    )
    if status:
        queryset = queryset.filter(status=status)
    users = {
        str(user.pk): user
        for user in user_model.objects.filter(
            id__in=list(queryset.values_list("investor_user_id", flat=True)[:100])
        )
    }
    results: list[dict[str, Any]] = []
    for order in queryset.order_by("-created_at", "id")[: _limit(limit)]:
        user = users.get(str(order.investor_user_id))
        currency = str(
            getattr(getattr(order, "currency", None), "code", getattr(order, "currency_id", ""))
        )
        loan = getattr(order, "loan", None)
        investor_label = str(
            getattr(user, "full_name", "") or getattr(user, "email", "") or order.investor_user_id
        )
        order_amount = _money_label(int(order.requested_amount_minor), currency)
        results.append(
            {
                "id": str(order.pk),
                "kind": "primary_order",
                "label": f"{investor_label} - {getattr(loan, 'title', '')}",
                "meta": f"{order.status} / {order_amount}",
                "payload": {
                    "investor_user_id": str(order.investor_user_id),
                    "investor_name": str(getattr(user, "full_name", "")),
                    "investor_email": str(getattr(user, "email", "")),
                    "loan_id": str(getattr(order, "loan_id", "")),
                    "loan_title": str(getattr(loan, "title", "")),
                    "status": str(order.status),
                    "requested_amount_minor": int(order.requested_amount_minor),
                    "allocated_amount_minor": int(order.allocated_amount_minor),
                    "currency": currency,
                },
            }
        )
    return results


def lookup_secondary_listings(
    *, query: str = "", status: str = "", limit: int | None = 20
) -> list[dict[str, Any]]:
    if not _query_ready(query):
        return []
    listing_model = _model("secondary_market", "SecondaryMarketListing")
    user_model = _model("accounts_auth", "User")
    cleaned = _clean(query)
    user_ids = list(
        _uuid_searchable(user_model.objects.filter(account_type__in=LENDER_ACCOUNT_TYPES))
        .filter(_tokenized_user_filter(cleaned))
        .values_list("id", flat=True)[:100]
    )
    queryset = _uuid_searchable(
        listing_model.objects.select_related("loan", "currency").all()
    ).filter(
        Q(id_text__icontains=cleaned)
        | Q(seller_user_id__in=user_ids)
        | Q(loan__title__icontains=cleaned)
    )
    if status:
        queryset = queryset.filter(status=status)
    users = {
        str(user.pk): user
        for user in user_model.objects.filter(
            id__in=list(queryset.values_list("seller_user_id", flat=True)[:100])
        )
    }
    results: list[dict[str, Any]] = []
    for listing in queryset.order_by("-created_at", "id")[: _limit(limit)]:
        user = users.get(str(listing.seller_user_id))
        currency = str(
            getattr(getattr(listing, "currency", None), "code", getattr(listing, "currency_id", ""))
        )
        loan = getattr(listing, "loan", None)
        listing_amount = _money_label(int(listing.current_principal_minor), currency)
        seller_reference = str(
            getattr(user, "investor_reference", "") or getattr(user, "email", "")
        )
        results.append(
            {
                "id": str(listing.pk),
                "kind": "secondary_listing",
                "label": str(getattr(loan, "title", "") or listing.pk),
                "meta": f"{listing.status} / {listing_amount} / seller {seller_reference}",
                "payload": {
                    "seller_user_id": str(listing.seller_user_id),
                    "seller_name": str(getattr(user, "full_name", "")),
                    "seller_email": str(getattr(user, "email", "")),
                    "seller_reference": str(getattr(user, "investor_reference", "") or ""),
                    "loan_id": str(getattr(listing, "loan_id", "")),
                    "loan_title": str(getattr(loan, "title", "")),
                    "status": str(listing.status),
                    "current_principal_minor": int(listing.current_principal_minor),
                    "currency": currency,
                    "days_past_due": int(getattr(listing, "days_past_due", 0)),
                },
            }
        )
    return results


def lookup_document_template_versions(
    *,
    query: str = "",
    category: str = "",
    limit: int | None = 20,
) -> list[dict[str, Any]]:
    if not _query_ready(query) and not category:
        return []
    version_model = _model("documents", "DocumentTemplateVersion")
    queryset = _uuid_searchable(version_model.objects.select_related("template").all())
    cleaned = _clean(query)
    if _query_ready(cleaned):
        queryset = queryset.filter(
            Q(id_text__icontains=cleaned)
            | Q(title__icontains=cleaned)
            | Q(template__name__icontains=cleaned)
            | Q(template__template_key__icontains=cleaned)
            | Q(legal_review_reference__icontains=cleaned)
        )
    if category:
        queryset = queryset.filter(template__category=category)
    results: list[dict[str, Any]] = []
    for version in queryset.order_by("-created_at", "id")[: _limit(limit)]:
        template = getattr(version, "template", None)
        category_label = str(getattr(template, "category", ""))
        version_number = str(getattr(version, "version_number", ""))
        status_label = str(getattr(version, "status", ""))
        results.append(
            {
                "id": str(version.pk),
                "kind": "document_template_version",
                "label": str(getattr(version, "title", "") or getattr(template, "name", "")),
                "meta": f"{category_label} / v{version_number} / {status_label}",
                "payload": {
                    "template_id": str(getattr(version, "template_id", "")),
                    "template_name": str(getattr(template, "name", "")),
                    "template_key": str(getattr(template, "template_key", "")),
                    "category": str(getattr(template, "category", "")),
                    "language": str(getattr(template, "language", "")),
                    "version_number": int(getattr(version, "version_number", 0)),
                    "status": str(getattr(version, "status", "")),
                },
            }
        )
    return results
