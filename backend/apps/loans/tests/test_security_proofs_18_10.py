"""IP of Webby-Soft SRL. 18.10 (Q13, U33-DEC-38): proof of securities before publication."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client

from backend.apps.loans import security_proofs as proofs
from backend.apps.loans.models import Loan, LoanSecurity
from backend.apps.loans.services import (
    LoanValidationError,
    PublishLoanCommand,
    create_loan,
    publish_loan,
)
from backend.apps.loans.tests.test_loans import _borrower, _loan_command, admin_user
from backend.apps.platform_core.domain import declarations as roles

__all__ = ["admin_user"]

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _gate_on(settings: Any) -> None:
    settings.SECURITY_PROOFS_REQUIRED = True


def _verifier(email: str = "verifier@example.test") -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            full_name="Vera Verifier",
            account_type="admin",
            status="active",
            is_staff=True,
            staff_roles=[roles.ROLE_SECURITY_VERIFIER],
        ),
    )


def _loan_with_documents(admin_user: Model) -> tuple[Loan, LoanSecurity, list[str]]:
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    documents = [str(uuid.uuid4()), str(uuid.uuid4())]
    [security] = LoanSecurity.objects.filter(loan=loan)
    security.document_ids = documents
    security.save(update_fields=["document_ids", "updated_at"])
    return loan, security, documents


def test_publication_waits_for_a_complete_named_verification(admin_user: Model) -> None:
    loan, security, documents = _loan_with_documents(admin_user)
    with pytest.raises(LoanValidationError, match="named verification"):
        publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))

    verifier = _verifier()
    # Real estate needs the land register extract and the mortgage note or pledge.
    with pytest.raises(proofs.SecurityProofError, match="Mortgage note"):
        proofs.record_security_verification(
            proofs.RecordSecurityVerificationCommand(
                actor=verifier,
                security_id=str(security.id),
                proofs={"land_register_extract": documents[0]},
            )
        )
    with pytest.raises(proofs.SecurityProofError, match="linked to this security"):
        proofs.record_security_verification(
            proofs.RecordSecurityVerificationCommand(
                actor=verifier,
                security_id=str(security.id),
                proofs={
                    "land_register_extract": documents[0],
                    "mortgage_note_or_pledge": str(uuid.uuid4()),
                },
            )
        )
    proofs.record_security_verification(
        proofs.RecordSecurityVerificationCommand(
            actor=verifier,
            security_id=str(security.id),
            proofs={
                "land_register_extract": documents[0],
                "mortgage_note_or_pledge": documents[1],
            },
            note="Extract of 2026-11-02 checked.",
        )
    )
    status = proofs.security_proof_status(security)
    assert status["verified"] is True and status["verified_by"] == "Vera Verifier"
    published = publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    assert published.status == "published"


def test_an_essential_change_needs_a_new_verification_and_keeps_the_history(
    admin_user: Model,
) -> None:
    loan, security, documents = _loan_with_documents(admin_user)
    verifier = _verifier()
    proofs.record_security_verification(
        proofs.RecordSecurityVerificationCommand(
            actor=verifier,
            security_id=str(security.id),
            proofs={
                "land_register_extract": documents[0],
                "mortgage_note_or_pledge": documents[1],
            },
        )
    )
    security.value_minor = 9_999_00
    security.save(update_fields=["value_minor", "updated_at"])
    status = proofs.security_proof_status(security)
    assert status["verified"] is False and status["needs_new_verification"] is True
    assert len(status["history"]) == 1
    with pytest.raises(LoanValidationError, match="no current verification"):
        publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    # A released security needs nothing (another one stays in place).
    LoanSecurity.objects.create(
        loan=loan, position=1, security_type="corporate_guarantee", status="released"
    )
    assert len(proofs.publication_problems(loan)) == 1


def test_only_the_security_verifier_records_and_the_api(admin_user: Model) -> None:
    loan, security, documents = _loan_with_documents(admin_user)
    with pytest.raises(proofs.SecurityProofPermissionError):
        proofs.record_security_verification(
            proofs.RecordSecurityVerificationCommand(
                actor=admin_user, security_id=str(security.id), proofs={}
            )
        )
    client = Client()
    client.force_login(cast(Any, _verifier("api-verifier@example.test")))
    listed = client.get(f"/api/v1/loans/admin/loans/{loan.pk}/security-proofs/")
    assert listed.status_code == 200
    assert [item["key"] for item in listed.json()[0]["required_proofs"]] == [
        "land_register_extract",
        "mortgage_note_or_pledge",
    ]
    recorded = client.post(
        f"/api/v1/loans/admin/securities/{security.id}/verification/",
        {
            "proofs": {
                "land_register_extract": documents[0],
                "mortgage_note_or_pledge": documents[1],
            },
            "note": "Checked.",
        },
        content_type="application/json",
    )
    assert recorded.status_code == 201, recorded.content
    assert recorded.json()["verified"] is True
