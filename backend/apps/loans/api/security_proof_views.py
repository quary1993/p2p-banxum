# IP of Webby-Soft SRL.
"""18.10 (Q13) API: proof of securities and their named verification."""

from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.loans import loan_documents
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
    checked = serializers.BooleanField()
    source = serializers.CharField(allow_blank=True)  # type: ignore[assignment]


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


class LoanDocumentSerializer(serializers.Serializer[Any]):
    id = serializers.CharField()
    display_name = serializers.CharField()
    document_type = serializers.CharField()
    document_type_label = serializers.CharField()
    document_date = serializers.DateField(allow_null=True)
    uploaded_at = serializers.DateTimeField()
    checked = serializers.BooleanField()
    checked_at = serializers.DateTimeField(allow_null=True)
    check_note = serializers.CharField(allow_blank=True)
    size_bytes = serializers.IntegerField()


class LoanDocumentUploadSerializer(serializers.Serializer[Any]):
    file = serializers.FileField()
    display_name = serializers.CharField(max_length=200)
    document_type = serializers.ChoiceField(choices=loan_documents.document_type_choices())
    document_date = serializers.DateField(required=False, allow_null=True)


class LoanDocumentCheckSerializer(serializers.Serializer[Any]):
    note = serializers.CharField(max_length=500)


class LoanDocumentListView(APIView):
    """Re-audit (owner's choice of 2026-11-20): proof documents uploaded to a loan."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(responses={200: LoanDocumentSerializer(many=True)})
    def get(self, request: Request, loan_id: str) -> Response:
        try:
            payload = loan_documents.list_loan_documents(
                actor=cast(Model, request.user), loan_id=str(loan_id)
            )
        except loan_documents.LoanDocumentPermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(payload)

    @extend_schema(request=LoanDocumentUploadSerializer, responses={201: LoanDocumentSerializer})
    def post(self, request: Request, loan_id: str) -> Response:
        serializer = LoanDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        upload = data["file"]
        if upload.size > loan_documents.MAX_DOCUMENT_BYTES:
            return Response(
                {"detail": "A document can have at most 20 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            document = loan_documents.upload_loan_document(
                loan_documents.UploadLoanDocumentCommand(
                    actor=cast(Model, request.user),
                    loan_id=str(loan_id),
                    filename=str(getattr(upload, "name", "") or ""),
                    content=upload.read(),
                    display_name=data["display_name"],
                    document_type=data["document_type"],
                    document_date=data.get("document_date"),
                )
            )
        except loan_documents.LoanDocumentPermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except loan_documents.LoanDocumentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(loan_documents.document_payload(document), status=status.HTTP_201_CREATED)


class LoanDocumentCheckView(APIView):
    """G-1: an admin confirms that the file was checked before it counts as proof."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=LoanDocumentCheckSerializer, responses={200: LoanDocumentSerializer})
    def post(self, request: Request, document_id: str) -> Response:
        serializer = LoanDocumentCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = loan_documents.confirm_loan_document_check(
                actor=cast(Model, request.user),
                document_id=str(document_id),
                note=serializer.validated_data["note"],
            )
        except loan_documents.LoanDocumentPermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except loan_documents.LoanDocumentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(loan_documents.document_payload(document))
