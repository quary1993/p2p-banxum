"""Anonymous public-site endpoints: forms and newsletter (COMMS-DEC-009).

No session and no CSRF (``authentication_classes = []``), every write throttled.
"""

from __future__ import annotations

import logging
from typing import Any, NoReturn, cast

from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    PolymorphicProxySerializer,
    extend_schema,
)
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.communications.api.serializers import (
    ENQUIRY_REQUEST_SERIALIZERS,
    CompanyEnquiryRequestSerializer,
    ContactEnquiryRequestSerializer,
    NewsletterAcceptedSerializer,
    NewsletterStatusSerializer,
    NewsletterSubscribeRequestSerializer,
    NewsletterTokenRequestSerializer,
    OriginatorEnquiryRequestSerializer,
    PublicEnquiryCreatedSerializer,
    PublicErrorSerializer,
)
from backend.apps.communications.api.throttles import (
    NEWSLETTER_CONFIRMATION_EMAIL_SCOPE,
    PUBLIC_ENQUIRY_SCOPE,
    NewsletterConfirmThrottle,
    NewsletterSubscribeThrottle,
    NewsletterUnsubscribeThrottle,
    newsletter_confirmation_global_limits,
    public_enquiry_global_limits,
    public_enquiry_ip_limits,
    public_enquiry_sender_limits,
)
from backend.apps.communications.newsletter import (
    NewsletterTokenError,
    SubscribeNewsletterCommand,
    confirm_newsletter_subscription,
    subscribe_to_newsletter,
    unsubscribe_from_newsletter,
)
from backend.apps.communications.public_forms import (
    SubmitPublicEnquiryCommand,
    believable_fake_reference,
    submit_public_enquiry,
)
from backend.apps.platform_core.api.request_meta import client_ip, user_agent
from backend.apps.platform_core.services.rate_limits import (
    record_window_hits,
    window_wait_seconds,
)

logger = logging.getLogger(__name__)

PUBLIC_ENQUIRY_MAX_BODY_BYTES = 32 * 1024
MINIMUM_HUMAN_ELAPSED_MS = 3000
ENQUIRY_THROTTLED_DETAIL = "Too many messages. Please try again later or write to us by email."
NEWSLETTER_THROTTLED_DETAIL = "Too many requests. Please try again later."
NEWSLETTER_ACCEPTED_DETAIL = "Check your inbox to confirm."
INVALID_TOKEN_DETAIL = "This link is not valid or has expired."


class PublicThrottled(APIException):
    """429 with the public-site body ``{detail, code: "throttled"}`` and Retry-After."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "throttled"

    def __init__(self, message: str, wait: float | None = None) -> None:
        super().__init__({"detail": message, "code": "throttled"})
        self.wait = int(wait) if wait else None


class PublicWriteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[type[BaseAuthentication]] = []
    throttled_detail = NEWSLETTER_THROTTLED_DETAIL

    def throttled(self, request: Request, wait: float | None) -> NoReturn:
        raise PublicThrottled(self.throttled_detail, wait)


def _honeypot_filled(raw: dict[str, Any]) -> bool:
    website = raw.get("website")
    if website is None:
        return False
    return bool(website.strip()) if isinstance(website, str) else bool(website)


def _sent_too_fast(raw: dict[str, Any]) -> bool:
    elapsed = raw.get("elapsed_ms")
    if elapsed is None or isinstance(elapsed, bool):
        return False
    try:
        return float(elapsed) < MINIMUM_HUMAN_ELAPSED_MS
    except (TypeError, ValueError):
        return False


def _request_body_too_large(request: Request) -> bool:
    try:
        declared = int(request.META.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        declared = 0
    if declared > PUBLIC_ENQUIRY_MAX_BODY_BYTES:
        return True
    return len(request.body) > PUBLIC_ENQUIRY_MAX_BODY_BYTES


class _RequiredBodySchema(AutoSchema):
    """A polymorphic (oneOf) body has no top-level ``required`` list, so drf-spectacular
    marks it optional; the form body is always required."""

    def _get_request_body(self, direction: str = "request") -> dict[str, Any] | None:
        body = super()._get_request_body(direction)  # type: ignore[no-untyped-call]
        if body is not None:
            body["required"] = True
        return cast(dict[str, Any] | None, body)


PUBLIC_ENQUIRY_REQUEST = PolymorphicProxySerializer(
    component_name="PublicEnquiryRequest",
    serializers={
        "company": CompanyEnquiryRequestSerializer,
        "originator": OriginatorEnquiryRequestSerializer,
        "contact": ContactEnquiryRequestSerializer,
    },
    resource_type_field_name="kind",
)


class PublicEnquiryView(PublicWriteView):
    """The For companies, For loan originators and Contact forms: one email to BANXUM."""

    parser_classes = [JSONParser]
    throttled_detail = ENQUIRY_THROTTLED_DETAIL
    schema = _RequiredBodySchema()

    @extend_schema(
        request=PUBLIC_ENQUIRY_REQUEST,
        responses={
            201: PublicEnquiryCreatedSerializer,
            400: OpenApiResponse(
                description=(
                    "Field errors under `fields` (by field name); `kind`, `consent` and "
                    '`elapsed_ms` errors at the top level; `{detail, code: "too_large"}` '
                    "for a body over 32 KB."
                )
            ),
            429: PublicErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        if _request_body_too_large(request):
            return Response(
                {"detail": "The form is too large.", "code": "too_large"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ip_limits = public_enquiry_ip_limits(request)
        wait = window_wait_seconds(PUBLIC_ENQUIRY_SCOPE, ip_limits)
        if wait is not None:
            raise PublicThrottled(ENQUIRY_THROTTLED_DETAIL, wait)

        raw = request.data
        if not isinstance(raw, dict):
            raise ValidationError({"detail": "Send the form as a JSON object."})
        kind = raw.get("kind")
        if _honeypot_filled(raw) or _sent_too_fast(raw):
            record_window_hits(PUBLIC_ENQUIRY_SCOPE, ip_limits)
            reference = believable_fake_reference(kind if isinstance(kind, str) else "")
            logger.info(
                "Public enquiry refused as automated (honeypot=%s, too_fast=%s); "
                "nothing stored or sent.",
                _honeypot_filled(raw),
                _sent_too_fast(raw),
            )
            return Response({"reference": reference}, status=status.HTTP_201_CREATED)

        serializer_class = ENQUIRY_REQUEST_SERIALIZERS.get(kind) if isinstance(kind, str) else None
        if serializer_class is None:
            raise ValidationError({"kind": ["Choose company, originator or contact."]})
        serializer = serializer_class(data=raw)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        fields: dict[str, Any] = dict(data["fields"])

        limits = [
            *public_enquiry_sender_limits(str(fields["email"])),
            *public_enquiry_global_limits(),
        ]
        wait = window_wait_seconds(PUBLIC_ENQUIRY_SCOPE, limits)
        if wait is not None:
            raise PublicThrottled(ENQUIRY_THROTTLED_DETAIL, wait)

        enquiry = submit_public_enquiry(
            SubmitPublicEnquiryCommand(
                kind=str(data["kind"]),
                fields=fields,
                ip_address=client_ip(request) or "",
                user_agent=user_agent(request),
            )
        )
        record_window_hits(PUBLIC_ENQUIRY_SCOPE, [*ip_limits, *limits])
        return Response({"reference": enquiry.reference}, status=status.HTTP_201_CREATED)


class NewsletterSubscribeView(PublicWriteView):
    """Start the double opt-in. Always the same answer for a well-formed address."""

    parser_classes = [JSONParser]
    throttle_classes = [NewsletterSubscribeThrottle]

    @extend_schema(
        request=NewsletterSubscribeRequestSerializer,
        responses={
            202: NewsletterAcceptedSerializer,
            400: OpenApiResponse(description="`{email: [...]}` or `{source: [...]}`."),
            429: PublicErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        accepted = Response({"detail": NEWSLETTER_ACCEPTED_DETAIL}, status=status.HTTP_202_ACCEPTED)
        raw = request.data
        if isinstance(raw, dict) and _honeypot_filled(raw):
            logger.info("Newsletter subscription refused as automated; nothing stored or sent.")
            return accepted
        serializer = NewsletterSubscribeRequestSerializer(data=raw)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        # Checked for every address, so the answer never tells whether one is subscribed.
        global_limits = newsletter_confirmation_global_limits()
        wait = window_wait_seconds(NEWSLETTER_CONFIRMATION_EMAIL_SCOPE, global_limits)
        if wait is not None:
            raise PublicThrottled(NEWSLETTER_THROTTLED_DETAIL, wait)
        result = subscribe_to_newsletter(
            SubscribeNewsletterCommand(
                email=str(data["email"]),
                source=str(data["source"]),
                ip_address=client_ip(request) or "",
            )
        )
        if result.confirmation_queued:
            record_window_hits(NEWSLETTER_CONFIRMATION_EMAIL_SCOPE, global_limits)
        return accepted


def _invalid_token_response() -> Response:
    return Response(
        {"detail": INVALID_TOKEN_DETAIL, "code": "invalid_token"},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _request_token(request: Request) -> object:
    data = request.data
    token = data.get("token") if hasattr(data, "get") else None
    if not token:
        token = request.query_params.get("token")
    return token


class NewsletterConfirmView(PublicWriteView):
    parser_classes = [JSONParser]
    throttle_classes = [NewsletterConfirmThrottle]

    @extend_schema(
        request=NewsletterTokenRequestSerializer,
        responses={
            200: NewsletterStatusSerializer,
            400: PublicErrorSerializer,
            429: PublicErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        try:
            confirm_newsletter_subscription(_request_token(request))
        except NewsletterTokenError:
            return _invalid_token_response()
        return Response({"status": "confirmed"}, status=status.HTTP_200_OK)


class NewsletterUnsubscribeView(PublicWriteView):
    """Unsubscribe; repeating it is fine.

    Also the RFC 8058 one-click target of the ``List-Unsubscribe`` header: mail providers
    POST ``List-Unsubscribe=One-Click`` as a form body with the token in the query string.
    """

    parser_classes = [JSONParser, FormParser, MultiPartParser]
    throttle_classes = [NewsletterUnsubscribeThrottle]

    @extend_schema(
        request=NewsletterTokenRequestSerializer,
        parameters=[
            OpenApiParameter(
                "token",
                str,
                OpenApiParameter.QUERY,
                required=False,
                description="Token for one-click unsubscribe (RFC 8058) instead of the body.",
            )
        ],
        responses={
            200: NewsletterStatusSerializer,
            400: PublicErrorSerializer,
            429: PublicErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        try:
            unsubscribe_from_newsletter(_request_token(request))
        except NewsletterTokenError:
            return _invalid_token_response()
        return Response({"status": "unsubscribed"}, status=status.HTTP_200_OK)
