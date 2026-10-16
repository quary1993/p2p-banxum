"""Public site forms and newsletter: request validation and response shapes (COMMS-DEC-009)."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

from rest_framework import serializers

from backend.apps.communications.models import NewsletterSource
from backend.apps.platform_core.domain.time import business_date, now_utc

SHORT_TEXT_MAX_LENGTH = 200
EMAIL_MAX_LENGTH = 254
PHONE_MAX_LENGTH = 40
FREE_TEXT_MAX_LENGTH = 4000
MAX_LINKS_IN_FREE_TEXT = 5
MAX_AMOUNT = Decimal("1000000000000")
EARLIEST_FOUNDED_YEAR = 1800

# Select options exactly as the public site forms show them.
COUNTRY_CHOICES = (
    "Switzerland",
    "Germany",
    "Austria",
    "Italy",
    "Romania",
    "France",
    "Other EU country",
)
TERM_CHOICES = (
    "1 month",
    "3 months",
    "6 months",
    "12 months",
    "18 months",
    "24 months",
    "36 months",
    "48 months",
    "60 months",
)
PURPOSE_CHOICES = (
    "Extension or construction",
    "Machines and equipment",
    "Real estate",
    "Stock and working capital",
    "Refinancing",
    "Other",
)
SECURITY_CHOICES = (
    "Mortgage note",
    "Pledge on equipment",
    "Receivables",
    "Guarantee of the owners",
    "Not sure yet",
)
PRODUCT_CHOICES = (
    "Leasing",
    "Invoices (factoring)",
    "Business loans",
    "Real estate loans",
    "Other",
)
TOPIC_CHOICES = (
    "Investing",
    "My account",
    "A loan for my company",
    "Loan originators",
    "Press",
    "Other",
)
FREE_TEXT_FIELDS = ("about", "message")

# Bidirectional overrides and isolates can make text read differently from what it is.
_BIDI_CONTROLS = frozenset(chr(code) for code in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)))
_LINE_BREAKS = ("\r\n", "\r", " ", " ", "\x85")
_LINK_RE = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)
_PLAIN_AMOUNT_RE = re.compile(r"\A[0-9]+(?:\.[0-9]{1,2})?\Z")
_GROUPED_AMOUNT_RE = re.compile(
    r"\A[0-9]{1,3}(?P<sep>[,'’   ])[0-9]{3}(?:(?P=sep)[0-9]{3})*(?:\.[0-9]{1,2})?\Z"
)
_PHONE_RE = re.compile(r"\A\+?[0-9 ()./-]+\Z")
_YEAR_RE = re.compile(r"\A[0-9]{4}\Z")


def clean_free_text(value: str) -> str:
    """Keep line breaks (as \\n); drop every other control character and bidi override."""

    for line_break in _LINE_BREAKS:
        value = value.replace(line_break, "\n")
    value = value.replace("\t", " ")
    return "".join(
        character
        for character in value
        if character == "\n"
        or (unicodedata.category(character) != "Cc" and character not in _BIDI_CONTROLS)
    ).strip()


def clean_single_line(value: str) -> str:
    """One line: control characters and line breaks become spaces, runs of spaces one."""

    for line_break in _LINE_BREAKS:
        value = value.replace(line_break, " ")
    cleaned = "".join(
        " " if unicodedata.category(character) == "Cc" else character
        for character in value
        if character not in _BIDI_CONTROLS
    )
    return re.sub(r" {2,}", " ", cleaned).strip()


def count_links(value: str) -> int:
    return len(_LINK_RE.findall(value))


def parse_amount(value: str) -> Decimal:
    """A positive amount with at most 2 decimals, "250000", "250,000.00" or "250'000".

    Thousands separators must group digits by three, so "250,50" (a decimal comma) is
    refused instead of being read as 25050.
    """

    text = value.strip()
    if _PLAIN_AMOUNT_RE.match(text):
        digits = text
    else:
        grouped = _GROUPED_AMOUNT_RE.match(text)
        if grouped is None:
            raise ValueError("not an amount")
        digits = text.replace(grouped.group("sep"), "")
    try:
        amount = Decimal(digits)
    except InvalidOperation as exc:
        raise ValueError("not an amount") from exc
    if amount <= 0 or amount > MAX_AMOUNT:
        raise ValueError("out of range")
    return amount.quantize(Decimal("0.01"))


class SingleLineField(serializers.CharField):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("max_length", SHORT_TEXT_MAX_LENGTH)
        super().__init__(**kwargs)

    def to_internal_value(self, data: Any) -> str:
        value = clean_single_line(super().to_internal_value(data))
        if not value and not self.allow_blank:
            self.fail("blank")
        return value


class FreeTextField(serializers.CharField):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("max_length", FREE_TEXT_MAX_LENGTH)
        super().__init__(**kwargs)

    def to_internal_value(self, data: Any) -> str:
        value = clean_free_text(super().to_internal_value(data))
        if not value and not self.allow_blank:
            self.fail("blank")
        return value


class SelectField(serializers.ChoiceField):
    """One of the listed options; surrounding spaces are ignored."""

    def to_internal_value(self, data: Any) -> Any:
        if isinstance(data, str):
            data = data.strip()
            if data == "":
                if self.allow_blank:
                    return ""
                self.fail("required")
        return super().to_internal_value(data)


class AmountField(SingleLineField):
    """A positive decimal string; stored normalised with two decimals, e.g. "250000.00"."""

    default_error_messages = {
        "invalid_amount": "Enter an amount like 250000 or 250,000.00.",
    }

    def to_internal_value(self, data: Any) -> str:
        value = super().to_internal_value(data)
        if value == "":
            return value
        try:
            return f"{parse_amount(value):.2f}"
        except ValueError:
            self.fail("invalid_amount")
            raise  # pragma: no cover - fail() always raises


class YearField(SingleLineField):
    default_error_messages = {
        "invalid_year": "Enter a year between {earliest} and {latest}.",
    }

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("max_length", 4)
        super().__init__(**kwargs)

    def to_internal_value(self, data: Any) -> str:
        value = super().to_internal_value(data)
        latest = business_date(now_utc()).year
        if not _YEAR_RE.match(value) or not EARLIEST_FOUNDED_YEAR <= int(value) <= latest:
            self.fail("invalid_year", earliest=EARLIEST_FOUNDED_YEAR, latest=latest)
        return value


class PhoneField(SingleLineField):
    default_error_messages = {
        "invalid_phone": "Enter a phone number, for example +41 44 000 00 00."
    }

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("max_length", PHONE_MAX_LENGTH)
        super().__init__(**kwargs)

    def to_internal_value(self, data: Any) -> str:
        value = super().to_internal_value(data)
        if not _PHONE_RE.match(value) or sum(character.isdigit() for character in value) < 6:
            self.fail("invalid_phone")
        return value


class PublicEmailField(serializers.EmailField):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("max_length", EMAIL_MAX_LENGTH)
        super().__init__(**kwargs)


class _EnquiryFieldsSerializer(serializers.Serializer[Any]):
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        total = 0
        for name in FREE_TEXT_FIELDS:
            value = attrs.get(name)
            if not value:
                continue
            total += count_links(str(value))
            if total > MAX_LINKS_IN_FREE_TEXT:
                raise serializers.ValidationError({name: ["Please remove some links."]})
        return attrs


class CompanyEnquiryFieldsSerializer(_EnquiryFieldsSerializer):
    company_name = SingleLineField()
    country = SelectField(choices=COUNTRY_CHOICES)
    company_number = SingleLineField()
    amount = AmountField()
    term = SelectField(choices=TERM_CHOICES)
    purpose = SelectField(choices=PURPOSE_CHOICES)
    security = SelectField(choices=SECURITY_CHOICES)
    revenue = AmountField(required=False, allow_blank=True)
    founded = YearField()
    about = FreeTextField(required=False, allow_blank=True)
    contact_name = SingleLineField()
    role = SingleLineField()
    email = PublicEmailField()
    phone = PhoneField()


class OriginatorEnquiryFieldsSerializer(_EnquiryFieldsSerializer):
    company_name = SingleLineField()
    country = SelectField(choices=COUNTRY_CHOICES)
    licence = SingleLineField()
    product = SelectField(choices=PRODUCT_CHOICES)
    loan_book = AmountField()
    about = FreeTextField(required=False, allow_blank=True)
    contact_name = SingleLineField()
    email = PublicEmailField()


class ContactEnquiryFieldsSerializer(_EnquiryFieldsSerializer):
    name = SingleLineField()
    email = PublicEmailField()
    topic = SelectField(choices=TOPIC_CHOICES)
    message = FreeTextField()


class _EnquiryRequestSerializer(serializers.Serializer[Any]):
    consent = serializers.BooleanField(help_text="Must be true.")
    website = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        help_text="Honeypot: leave empty.",
    )
    elapsed_ms = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text="Milliseconds from showing the form to sending it.",
    )

    def validate_consent(self, value: bool) -> bool:
        if value is not True:
            raise serializers.ValidationError("Please agree before you send the form.")
        return value


class _KindEnquiryRequestSerializer(_EnquiryRequestSerializer):
    # The wire name "fields" clashes with ``Serializer.fields``, so the nested serializer
    # is added in ``get_fields`` instead of as a class attribute.
    form_fields_class: type[_EnquiryFieldsSerializer]

    def get_fields(self) -> dict[str, serializers.Field[Any, Any, Any, Any]]:
        declared = super().get_fields()
        declared["fields"] = self.form_fields_class()
        return declared


class CompanyEnquiryRequestSerializer(_KindEnquiryRequestSerializer):
    kind = serializers.ChoiceField(choices=["company"])
    form_fields_class = CompanyEnquiryFieldsSerializer


class OriginatorEnquiryRequestSerializer(_KindEnquiryRequestSerializer):
    kind = serializers.ChoiceField(choices=["originator"])
    form_fields_class = OriginatorEnquiryFieldsSerializer


class ContactEnquiryRequestSerializer(_KindEnquiryRequestSerializer):
    kind = serializers.ChoiceField(choices=["contact"])
    form_fields_class = ContactEnquiryFieldsSerializer


ENQUIRY_REQUEST_SERIALIZERS: dict[str, type[_KindEnquiryRequestSerializer]] = {
    "company": CompanyEnquiryRequestSerializer,
    "originator": OriginatorEnquiryRequestSerializer,
    "contact": ContactEnquiryRequestSerializer,
}


class PublicEnquiryCreatedSerializer(serializers.Serializer[Any]):
    reference = serializers.CharField()


class PublicErrorSerializer(serializers.Serializer[Any]):
    detail = serializers.CharField()
    code = serializers.CharField()


class NewsletterSubscribeRequestSerializer(serializers.Serializer[Any]):
    email = PublicEmailField()
    website = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        help_text="Honeypot: leave empty.",
    )

    def get_fields(self) -> dict[str, serializers.Field[Any, Any, Any, Any]]:
        # "source" clashes with ``Field.source``; added here instead of as an attribute.
        declared = super().get_fields()
        declared["source"] = serializers.ChoiceField(choices=NewsletterSource.choices)
        return declared


class NewsletterAcceptedSerializer(serializers.Serializer[Any]):
    detail = serializers.CharField()


class NewsletterTokenRequestSerializer(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=256)


class NewsletterStatusSerializer(serializers.Serializer[Any]):
    status = serializers.CharField()
