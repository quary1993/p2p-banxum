# IP of Webby-Soft SRL.
"""18.10 (Q13) API: proof of securities and their named verification."""

from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.loans import security_proofs as services
from backend.apps.loans.models import Loan, LoanSecurity
from backend.apps.platform_core.domain.access import is_admin_actor


class RequiredProofSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]


class ProofDocumentSerializer(serializers.Serializer[Any]):
    id = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    document_type = serializers.CharField(allow_blank=True)
    document_date = serializers.DateField(allow_null=True)
    uploaded_at = serializers.DateTimeField(allow_null=True)
    available = serializers.BooleanField()


class VerificationProofSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    document = ProofDocumentSerializer()


class VerificationHistorySerializer(serializers.Serializer[Any]):
    verifier_name = serializers.CharField()
    verified_at = serializers.DateTimeField()
    note = serializers.CharField(allow_blank=True)
    required_proofs = serializers.ListField(child=serializers.CharField())
    proofs = VerificationProofSerializer(many=True)


class SecurityProofStatusSerializer(serializers.Serializer[Any]):
    security_id = serializers.UUIDField()
    security_type = serializers.CharField()
    released = serializers.BooleanField()
    required_proofs = RequiredProofSerializer(many=True)
    configuration_error = serializers.CharField(allow_blank=True)
    document_ids = serializers.ListField(child=serializers.CharField())
    documents = ProofDocumentSerializer(many=True)
    verified = serializers.BooleanField()
    verified_by = serializers.CharField(allow_blank=True)
    verified_at = serializers.DateTimeField(allow_null=True)
    proofs = serializers.DictField(child=serializers.CharField())
    needs_new_verification = serializers.BooleanField()
    problem = serializers.CharField(allow_blank=True)
    history = VerificationHistorySerializer(many=True)


class SecurityVerificationRequestSerializer(serializers.Serializer[Any]):
    proofs = serializers.DictField(child=serializers.CharField(allow_blank=True))
    note = serializers.CharField(required=False, allow_blank=True, default="")


class LoanSecurityProofsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SecurityProofStatusSerializer(many=True)})
    def get(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)
        loan = Loan.objects.filter(id=loan_id).first()
        if loan is None:
            return Response({"detail": "Loan does not exist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(services.loan_security_proofs(loan))


class LoanSecurityVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SecurityVerificationRequestSerializer,
        responses={201: SecurityProofStatusSerializer},
    )
    def post(self, request: Request, security_id: str) -> Response:
        serializer = SecurityVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.record_security_verification(
                services.RecordSecurityVerificationCommand(
                    actor=cast(Model, request.user),
                    security_id=str(security_id),
                    proofs=dict(serializer.validated_data["proofs"]),
                    note=serializer.validated_data["note"],
                )
            )
        except services.SecurityProofPermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except services.SecurityProofError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        security = LoanSecurity.objects.get(id=security_id)
        return Response(services.security_proof_status(security), status=status.HTTP_201_CREATED)


class SecurityProofDocumentFileSerializer(serializers.Serializer[Any]):
    document_id = serializers.CharField()
    display_name = serializers.CharField()
    filename = serializers.CharField()
    content_type = serializers.CharField()
    content_encoding = serializers.CharField()
    content = serializers.CharField()
    content_sha256 = serializers.CharField()


class SecurityProofDocumentView(APIView):
    """Audit S7-8: an admin opens a document of the security to check it."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SecurityProofDocumentFileSerializer})
    def get(self, request: Request, security_id: str, document_id: str) -> Response:
        try:
            payload = services.open_proof_document(
                actor=cast(Model, request.user),
                security_id=str(security_id),
                document_id=str(document_id),
            )
        except services.SecurityProofPermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except services.SecurityProofError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(payload)
