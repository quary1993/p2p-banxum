"""IP of Webby-Soft SRL. Re-audit: proof documents uploaded to a loan (owner's choice).

A Loan Originator claim has no borrower record. Its securities link documents uploaded to the
loan; a document counts as proof only after an admin confirmed its check (security review
G-1); then the offer can be verified and published with the proof rule on.
"""

from __future__ import annotations

import hashlib
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.loans import loan_documents, securities
from backend.apps.loans import security_proofs as proofs
from backend.apps.loans.models import LoanDocument, LoanSecurity
from backend.apps.platform_core.domain import declarations as roles
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.models import AuditEvent

PDF = b"%PDF-1.4 synthetic assignment agreement"


@pytest.fixture(autouse=True)
def _proofs_on(settings: Any, tmp_path: Path) -> None:
    settings.SECURITY_PROOFS_REQUIRED = True
    settings.MEDIA_ROOT = str(tmp_path)


def _user(email: str, **extra: Any) -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email, full_name=email.split("@")[0], status="active", **extra
        ),
    )


def _admin() -> Model:
    return _user("docs-admin@example.test", account_type="admin", is_staff=True)


def _verifier() -> Model:
    return _user(
        "docs-verifier@example.test",
        account_type="admin",
        is_staff=True,
        staff_roles=[roles.ROLE_SECURITY_VERIFIER],
    )


def _originator_offer(admin: Model) -> Any:
    claims: Any = import_module("backend.apps.originator_claims.tests.test_originator_claims")
    originator: Any = import_module("backend.apps.originator_claims.services")
    models: Any = import_module("backend.apps.originator_claims.models")
    today = business_date(timezone.now())
    lo = originator.create_loan_originator(
        originator.CreateLoanOriginatorCommand(
            actor=admin,
            legal_name="Docs Originator AG",
            public_name="Docs Originator",
            registration_number="CHE-444.555.667",
            jurisdiction="CH",
            registered_address="Bern, Switzerland",
            settlement_account_name="Docs Originator AG",
            settlement_iban="CH9300762011623852957",
            kyb_evidence_reference="KYB-DOCS-001",
            status=models.LoanOriginatorStatus.ACTIVE,
        )
    )
    return originator.create_originator_loan(
        originator.CreateOriginatorLoanCommand(
            actor=admin,
            originator_id=str(lo.id),
            title="Docs claim",
            investor_summary="Performing claim.",
            purpose="working_capital",
            purpose_description="Working capital",
            currency="CHF",
            original_principal_minor=1_000_000,
            interest_rate_bps=1200,
            target_yield_bps=800,
            distribution_model=models.OriginatorDistributionModel.LEGACY_YIELD_V1,
            minimum_investment_minor=100_000,
            repayment_type="equal_installments",
            interest_only_months=0,
            collateral_type="receivables",
            collateral_value_minor=1_500_000,
            collateral_description="Assigned receivables",
            risk_rating="BBB",
            csv_content=claims._dated_two_period_csv(
                today=today, include_payment=False, final_due_days=90
            ),
            source_filename="docs.csv",
            as_of_date=today,
            borrower_snapshot={
                "borrower_legal_name": "Docs Borrower AG",
                "borrower_display_name": "Docs borrower",
            },
            historical_boundary_offer=True,
        )
    )


@pytest.mark.django_db
def test_a_loan_originator_offer_is_published_with_uploaded_and_checked_proofs() -> None:
    admin = _admin()
    result = _originator_offer(admin)
    loan = result.loan
    originator: Any = import_module("backend.apps.originator_claims.services")
    today = business_date(timezone.now())
    [security] = LoanSecurity.objects.filter(loan_id=loan.id)
    assert loan.borrower_id is None
    with pytest.raises(originator.OriginatorClaimsValidationError, match="named verification"):
        originator.publish_originator_loan(
            originator.PublishOriginatorLoanCommand(
                actor=admin, loan_id=str(loan.id), as_of_date=today
            )
        )

    client = Client()
    client.force_login(cast(Any, admin))
    uploaded = client.post(
        f"/api/v1/loans/admin/loans/{loan.id}/documents/",
        {
            "file": SimpleUploadedFile("assignment.pdf", PDF, content_type="application/pdf"),
            "display_name": "Assignment agreement 2026",
            "document_type": "pledge_or_assignment_agreement",
        },
    )
    assert uploaded.status_code == 201, uploaded.content
    document_id = uploaded.json()["id"]
    assert uploaded.json()["checked"] is False
    # The security editor offers the uploaded document for this claim.
    offered = securities.borrower_documents_for_securities(actor=admin, loan_id=str(loan.id))
    assert [item["id"] for item in offered] == [document_id]
    security.document_ids = [document_id]
    security.save(update_fields=["document_ids", "updated_at"])

    verify = proofs.RecordSecurityVerificationCommand(
        actor=_verifier(),
        security_id=str(security.id),
        proofs={"pledge_or_assignment_agreement": document_id},
    )
    with pytest.raises(proofs.SecurityProofError, match="waits for its check"):
        proofs.record_security_verification(verify)
    opened = client.get(f"/api/v1/loans/admin/securities/{security.id}/documents/{document_id}/")
    assert opened.status_code == 404  # not yet checked

    # Re-audit 2: the platform does not serve the unchecked file, so the admin gives the
    # SHA-256 of the scanned original; a different file is refused.
    assert uploaded.json()["checksum_sha256"] == hashlib.sha256(PDF).hexdigest()
    wrong = client.post(
        f"/api/v1/loans/admin/loan-documents/{document_id}/check/",
        {"note": "Scanned another file.", "checksum_sha256": hashlib.sha256(b"x").hexdigest()},
        content_type="application/json",
    )
    assert wrong.status_code == 400
    assert "does not match" in wrong.json()["detail"]
    checked = client.post(
        f"/api/v1/loans/admin/loan-documents/{document_id}/check/",
        {
            "note": "Scanned with the office antivirus; content read.",
            "checksum_sha256": hashlib.sha256(PDF).hexdigest().upper(),
        },
        content_type="application/json",
    )
    assert checked.status_code == 200, checked.content
    assert checked.json()["checked"] is True
    assert AuditEvent.objects.filter(action="loan.document_check_confirmed").count() == 1
    proofs.record_security_verification(verify)
    status = proofs.security_proof_status(security)
    assert status["verified"] is True
    assert status["documents"][0]["source"] == "loan"
    assert status["documents"][0]["title"] == "Assignment agreement 2026"
    opened = client.get(f"/api/v1/loans/admin/securities/{security.id}/documents/{document_id}/")
    assert opened.status_code == 200, opened.content
    assert opened.json()["display_name"] == "Assignment agreement 2026"

    originator.publish_originator_loan(
        originator.PublishOriginatorLoanCommand(actor=admin, loan_id=str(loan.id), as_of_date=today)
    )

    # Re-audit 2: when a scanner later marks the file as not clean, the verification ends.
    stored = LoanDocument.objects.select_related("stored_file").get(id=document_id).stored_file
    stored.scan_status = "infected"
    stored.save(update_fields=["scan_status"])
    assert proofs.current_verification(security) is None
    assert "did not pass its file check" in proofs.verification_problem(security)


@pytest.mark.django_db
def test_uploads_are_admin_only_and_must_be_pdf_or_image() -> None:
    admin = _admin()
    result = _originator_offer(admin)
    url = f"/api/v1/loans/admin/loans/{result.loan.id}/documents/"
    client = Client()
    client.force_login(cast(Any, admin))
    refused = client.post(
        url,
        {
            "file": SimpleUploadedFile("run.exe", b"MZ\x90\x00", content_type="application/pdf"),
            "display_name": "Not a PDF",
            "document_type": "other",
        },
    )
    assert refused.status_code == 400
    assert "PDF, PNG or JPEG" in refused.json()["detail"]
    with pytest.raises(loan_documents.LoanDocumentError, match="how the file was checked"):
        document = loan_documents.upload_loan_document(
            loan_documents.UploadLoanDocumentCommand(
                actor=admin,
                loan_id=str(result.loan.id),
                filename="a.pdf",
                content=PDF,
                display_name="Agreement",
            )
        )
        loan_documents.confirm_loan_document_check(
            actor=admin,
            document_id=str(document.id),
            note="ok",
            checksum_sha256=hashlib.sha256(PDF).hexdigest(),
        )

    investor = Client()
    investor.force_login(
        cast(Any, _user("docs-investor@example.test", account_type="natural_person_lender"))
    )
    assert investor.get(url).status_code == 403
    assert (
        investor.post(
            url,
            {
                "file": SimpleUploadedFile("a.pdf", PDF, content_type="application/pdf"),
                "display_name": "Agreement",
                "document_type": "other",
            },
        ).status_code
        == 403
    )
    assert LoanDocument.objects.filter(loan_id=result.loan.id).count() == 1
