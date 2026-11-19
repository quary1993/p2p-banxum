# IP of Webby-Soft SRL.
"""18.10 API: investor declarations, compliance reviews, re-verification dates, staff roles."""

from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.kyc_compliance import declarations as services
from backend.apps.platform_core.domain import declarations as rules


class DeclarationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    version = serializers.IntegerField()
    subject_type = serializers.CharField()
    beneficial_owner_is_self = serializers.BooleanField()
    beneficial_owner_name = serializers.CharField(allow_blank=True)
    sources_of_funds = serializers.ListField(child=serializers.CharField())
    savings_origin = serializers.CharField(allow_blank=True)
    source_other_text = serializers.CharField(allow_blank=True)
    pep_status = serializers.CharField()
    pep_person = serializers.CharField(allow_blank=True)
    pep_relation = serializers.CharField(allow_blank=True)
    pep_function = serializers.CharField(allow_blank=True)
    pep_country = serializers.CharField(allow_blank=True)
    yearly_volume_band = serializers.CharField()
    company_details = serializers.DictField(child=serializers.CharField(allow_blank=True))
    review_triggers = serializers.ListField(child=serializers.CharField())
    submitted_at = serializers.DateTimeField()


class InvestorComplianceStatusSerializer(serializers.Serializer[Any]):
    declaration = DeclarationSerializer(allow_null=True)
    review_open = serializers.BooleanField()
    review_status = serializers.CharField(allow_null=True)
    review_message = serializers.CharField(allow_blank=True)
    reverification_due_date = serializers.DateField(allow_null=True)
    investment_block = serializers.CharField(allow_null=True)
    investment_block_message = serializers.CharField(allow_blank=True)


class DeclarationSubmitSerializer(serializers.Serializer[Any]):
    subject_type = serializers.ChoiceField(
        choices=[rules.SUBJECT_PERSON, rules.SUBJECT_COMPANY], default=rules.SUBJECT_PERSON
    )
    beneficial_owner_is_self = serializers.BooleanField()
    beneficial_owner_name = serializers.CharField(required=False, allow_blank=True, default="")
    sources_of_funds = serializers.ListField(
        child=serializers.ChoiceField(choices=list(rules.SOURCES_OF_FUNDS)), allow_empty=False
    )
    savings_origin = serializers.CharField(required=False, allow_blank=True, default="")
    source_other_text = serializers.CharField(required=False, allow_blank=True, default="")
    pep_status = serializers.ChoiceField(choices=list(rules.PEP_ANSWERS))
    pep_person = serializers.CharField(required=False, allow_blank=True, default="")
    pep_relation = serializers.CharField(required=False, allow_blank=True, default="")
    pep_function = serializers.CharField(required=False, allow_blank=True, default="")
    pep_country = serializers.CharField(required=False, allow_blank=True, default="")
    yearly_volume_band = serializers.ChoiceField(choices=list(rules.VOLUME_BANDS))
    company_details = serializers.DictField(
        child=serializers.CharField(allow_blank=True), required=False, default=dict
    )


class ComplianceReviewSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    investor_id = serializers.UUIDField()
    investor_name = serializers.CharField()
    investor_email = serializers.CharField()
    declaration_version = serializers.IntegerField(allow_null=True)
    triggers = serializers.ListField(child=serializers.CharField())
    trigger_labels = serializers.ListField(child=serializers.CharField())
    necessary = serializers.BooleanField()
    status = serializers.CharField()
    opened_reason = serializers.CharField(allow_blank=True)
    investor_message = serializers.CharField(allow_blank=True)
    outcome_note = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    closed_at = serializers.DateTimeField(allow_null=True)


class ReverificationRowSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    due_date = serializers.DateField()
    reason = serializers.CharField(allow_blank=True)
    notices_sent = serializers.ListField(child=serializers.IntegerField())
    completed_at = serializers.DateTimeField(allow_null=True)
    replaced_at = serializers.DateTimeField(allow_null=True)


class InvestorComplianceFileSerializer(serializers.Serializer[Any]):
    investor_id = serializers.UUIDField()
    declarations = DeclarationSerializer(many=True)
    reviews = ComplianceReviewSerializer(many=True)
    reverifications = ReverificationRowSerializer(many=True)


class OpenReviewRequestSerializer(serializers.Serializer[Any]):
    investor_id = serializers.UUIDField()
    reason = serializers.CharField()
    necessary = serializers.BooleanField(default=True)


class ReviewDecisionRequestSerializer(serializers.Serializer[Any]):
    decision = serializers.ChoiceField(choices=["close", "more_information"])
    note = serializers.CharField(required=False, allow_blank=True, default="")
    investor_message = serializers.CharField(required=False, allow_blank=True, default="")


class ReverificationRequestSerializer(serializers.Serializer[Any]):
    due_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class StaffRolesRequestSerializer(serializers.Serializer[Any]):
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=list(rules.STAFF_ROLES)), allow_empty=True
    )


class StaffRolesResponseSerializer(serializers.Serializer[Any]):
    user_id = serializers.UUIDField()
    roles = serializers.ListField(child=serializers.CharField())


def _error(exc: Exception) -> Response:
    if isinstance(exc, services.DeclarationsPermissionError):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class InvestorDeclarationView(APIView):
    """Settings > Declarations: the investor's status and a new declaration version."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InvestorComplianceStatusSerializer})
    def get(self, request: Request) -> Response:
        return Response(services.investor_compliance_status(request.user))

    @extend_schema(
        request=DeclarationSubmitSerializer, responses={201: InvestorComplianceStatusSerializer}
    )
    def post(self, request: Request) -> Response:
        serializer = DeclarationSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.submit_declaration(
                services.SubmitDeclarationCommand(
                    actor=cast(Model, request.user), data=dict(serializer.validated_data)
                )
            )
        except (services.DeclarationsError, services.DeclarationsPermissionError) as exc:
            return _error(exc)
        return Response(
            services.investor_compliance_status(request.user), status=status.HTTP_201_CREATED
        )


class ComplianceReviewListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ComplianceReviewSerializer(many=True)})
    def get(self, request: Request) -> Response:
        try:
            rows = services.list_reviews(
                actor=cast(Model, request.user), status=request.query_params.get("status")
            )
        except services.DeclarationsPermissionError as exc:
            return _error(exc)
        return Response(rows)

    @extend_schema(request=OpenReviewRequestSerializer, responses={201: ComplianceReviewSerializer})
    def post(self, request: Request) -> Response:
        serializer = OpenReviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            review = services.open_review(
                services.OpenReviewCommand(
                    actor=cast(Model, request.user),
                    investor_id=str(data["investor_id"]),
                    reason=data["reason"],
                    necessary=data["necessary"],
                )
            )
        except (services.DeclarationsError, services.DeclarationsPermissionError) as exc:
            return _error(exc)
        return Response(services.review_payload(review), status=status.HTTP_201_CREATED)


class ComplianceReviewDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReviewDecisionRequestSerializer, responses={200: ComplianceReviewSerializer}
    )
    def post(self, request: Request, review_id: str) -> Response:
        serializer = ReviewDecisionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            review = services.decide_review(
                services.DecideReviewCommand(
                    actor=cast(Model, request.user),
                    review_id=str(review_id),
                    decision=data["decision"],
                    note=data["note"],
                    investor_message=data["investor_message"],
                )
            )
        except (services.DeclarationsError, services.DeclarationsPermissionError) as exc:
            return _error(exc)
        return Response(services.review_payload(review))


class InvestorComplianceFileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InvestorComplianceFileSerializer})
    def get(self, request: Request, investor_id: str) -> Response:
        try:
            return Response(
                services.investor_compliance_file(
                    actor=cast(Model, request.user), investor_id=str(investor_id)
                )
            )
        except services.DeclarationsPermissionError as exc:
            return _error(exc)


class InvestorReverificationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReverificationRequestSerializer, responses={200: InvestorComplianceFileSerializer}
    )
    def post(self, request: Request, investor_id: str) -> Response:
        serializer = ReverificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = cast(Model, request.user)
        try:
            services.set_reverification(
                services.SetReverificationCommand(
                    actor=actor,
                    investor_id=str(investor_id),
                    due_date=serializer.validated_data["due_date"],
                    reason=serializer.validated_data["reason"],
                )
            )
            return Response(
                services.investor_compliance_file(actor=actor, investor_id=str(investor_id))
            )
        except (services.DeclarationsError, services.DeclarationsPermissionError) as exc:
            return _error(exc)


class InvestorReverificationCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: InvestorComplianceFileSerializer})
    def post(self, request: Request, investor_id: str) -> Response:
        actor = cast(Model, request.user)
        try:
            services.complete_reverification(actor=actor, investor_id=str(investor_id))
            return Response(
                services.investor_compliance_file(actor=actor, investor_id=str(investor_id))
            )
        except (services.DeclarationsError, services.DeclarationsPermissionError) as exc:
            return _error(exc)


class StaffRolesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=StaffRolesRequestSerializer, responses={200: StaffRolesResponseSerializer}
    )
    def post(self, request: Request, user_id: str) -> Response:
        serializer = StaffRolesRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = cast(
                Any,
                services.set_staff_roles(
                    services.SetStaffRolesCommand(
                        actor=cast(Model, request.user),
                        user_id=str(user_id),
                        roles=tuple(serializer.validated_data["roles"]),
                    )
                ),
            )
        except (services.DeclarationsError, services.DeclarationsPermissionError) as exc:
            return _error(exc)
        return Response({"user_id": str(user.pk), "roles": list(user.staff_roles)})
