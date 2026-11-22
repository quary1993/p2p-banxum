"""IP of Webby-Soft SRL. 18.10 (Q13, U33-DEC-38): proof of securities before publication."""

from __future__ import annotations

import hashlib
import uuid
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client

from backend.apps.loans import security_proofs as proofs
from backend.apps.loans.models import Loan, LoanSecurity, LoanSecurityVerification
from backend.apps.loans.services import (
    LoanValidationError,
    PublishLoanCommand,
    create_loan,
    publish_loan,
)
from backend.apps.loans.tests.test_loans import _borrower, _loan_command, admin_user
from backend.apps.platform_core.domain import declarations as roles
from backend.apps.platform_core.domain import security_proofs as rules
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.models import AuditEvent, PlatformSetting, StoredFile
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.platform_core.services.settings import (
    SetPlatformSettingCommand,
    set_platform_setting,
)

__all__ = ["admin_user"]

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _gate_on(settings: Any, tmp_path: Path) -> None:
    settings.SECURITY_PROOFS_REQUIRED = True
    settings.MEDIA_ROOT = str(tmp_path)


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


def _document(admin_user: Model, borrower: Any, name: str) -> str:
    """A scanned borrower document with a small file (audit S7-3, S7-8: real documents)."""
    from django.conf import settings

    content = f"%PDF-1.4 {name}".encode()
    storage_key = f"borrowers/{borrower.pk}/{uuid.uuid4().hex}.pdf"
    path = Path(settings.MEDIA_ROOT) / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    stored = StoredFile.objects.create(
        storage_key=storage_key,
        original_filename=f"{name}.pdf",
        content_type="application/pdf",
        size_bytes=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        scan_status="clean",
        owner_type="borrower",
        owner_id=str(borrower.pk),
        created_by_type="admin",
        created_by_id=str(admin_user.pk),
    )
    document = apps.get_model("entities", "BorrowerDocument").objects.create(
        borrower=borrower,
        document_type="other",
        display_name=name,
        stored_file=stored,
        created_by_admin_id=admin_user.pk,
        created_by_account_type="admin",
    )
    return str(document.pk)


def _loan_with_documents(admin_user: Model) -> tuple[Loan, LoanSecurity, list[str]]:
    borrower = _borrower(admin_user)
    loan = create_loan(_loan_command(admin_user, borrower))
    documents = [
        _document(admin_user, borrower, "Land register extract 2026"),
        _document(admin_user, borrower, "Mortgage note"),
    ]
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
    with pytest.raises(LoanValidationError, match="essential detail changed"):
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


def _verify(security: LoanSecurity, documents: list[str], verifier: Model | None = None) -> None:
    proofs.record_security_verification(
        proofs.RecordSecurityVerificationCommand(
            actor=verifier or _verifier(f"v-{uuid.uuid4().hex[:8]}@example.test"),
            security_id=str(security.id),
            proofs={
                "land_register_extract": documents[0],
                "mortgage_note_or_pledge": documents[1],
            },
        )
    )


def _set_proofs(value: Any) -> None:
    set_platform_setting(
        SetPlatformSettingCommand(
            actor=ActorRef(actor_type="system", actor_id="test"),
            key=rules.REQUIRED_PROOFS_SETTING,
            value=value,
        )
    )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (["land_register_extract"], "map security types"),
        ({"spaceship": ["agreement"]}, "Unknown security type"),
        ({"real_estate": []}, "at least one proof"),
        ({"real_estate": ["land_register_extract", " "]}, "blank"),
        ({"real_estate": ["land_register_extract", "unknown_paper"]}, "Unknown proof"),
        ({"real_estate": ["agreement", "agreement"]}, "given twice"),
    ],
)
def test_a_wrong_required_proof_setting_is_refused(value: Any, message: str) -> None:
    """Audit S7-3: unknown, blank, duplicate, empty or malformed lists are refused."""
    with pytest.raises(rules.ProofConfigurationError, match=message):
        _set_proofs(value)
    assert not PlatformSetting.objects.filter(key=rules.REQUIRED_PROOFS_SETTING).exists()


def test_a_change_of_the_required_proofs_needs_a_new_verification(admin_user: Model) -> None:
    """Audit S7-3: add, replace and remove a proof; a malformed stored setting fails closed."""
    loan, security, documents = _loan_with_documents(admin_user)
    _verify(security, documents)
    assert proofs.publication_problems(loan) == []

    # Add a proof: the old verification is no longer current.
    _set_proofs({"real_estate": ["land_register_extract", "mortgage_note_or_pledge", "agreement"]})
    assert "list of required proofs changed" in proofs.publication_problems(loan)[0]
    with pytest.raises(LoanValidationError, match="list of required proofs changed"):
        publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    # Replace a proof, then remove one: still a new verification each time.
    _set_proofs({"real_estate": ["land_register_extract", "agreement"]})
    assert proofs.publication_problems(loan)
    _set_proofs({"real_estate": ["land_register_extract"]})
    assert proofs.publication_problems(loan)
    proofs.record_security_verification(
        proofs.RecordSecurityVerificationCommand(
            actor=_verifier(),
            security_id=str(security.id),
            proofs={"land_register_extract": documents[0]},
        )
    )
    assert proofs.publication_problems(loan) == []
    status = proofs.security_proof_status(security)
    assert status["history"][0]["required_proofs"] == ["land_register_extract"]

    # A malformed setting stored outside the service: verification and publication stop.
    PlatformSetting.objects.filter(key=rules.REQUIRED_PROOFS_SETTING).update(
        value={"real_estate": []}
    )
    assert "not valid" in proofs.publication_problems(loan)[0]
    assert "not valid" in proofs.security_proof_status(security)["configuration_error"]
    with pytest.raises(proofs.SecurityProofError, match="not valid"):
        _verify(security, documents)


def test_essential_fields_and_proof_documents_keep_the_verification_current(
    admin_user: Model,
) -> None:
    """Audit step 7 (D8) and S7-3: rank, prior debt, valuation details, LTV counting and a
    removed proof document all need a new verification."""
    loan, security, documents = _loan_with_documents(admin_user)
    for name, value in (
        ("rank", 2),
        ("prior_ranking_debt_minor", 100_000_00),
        ("valuation_source", "New appraisal"),
        ("counts_in_ltv", not security.counts_in_ltv),
        ("insurance", "Building insurance until 2030"),
    ):
        _verify(security, documents)
        assert proofs.publication_problems(loan) == []
        LoanSecurity.objects.filter(pk=security.pk).update(**{name: value})
        security.refresh_from_db()
        assert "essential detail changed" in proofs.publication_problems(loan)[0], name
    _verify(security, documents)
    apps.get_model("entities", "BorrowerDocument").objects.filter(pk=documents[1]).delete()
    assert "no longer available" in proofs.publication_problems(loan)[0]


def test_new_investments_stop_while_a_published_loan_needs_a_new_verification(
    admin_user: Model,
) -> None:
    """Audit S7-4: an essential change after publication stops new orders and allocations
    until the security is verified again."""
    primary: Any = import_module("backend.apps.marketplace_primary.services")
    helpers: Any = import_module("backend.apps.marketplace_primary.tests.test_primary_marketplace")
    loan, security, documents = _loan_with_documents(admin_user)
    _verify(security, documents)
    publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    investor = cast(
        Model,
        get_user_model().objects.create_user(
            email="proof-investor@example.test",
            full_name="Proof Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    helpers._approve_financial_access(investor)
    helpers._declare_deposit(admin_user, investor, amount_minor=10_000_00, idempotency_key="pd")

    def order(key: str) -> Any:
        return primary.create_primary_investment_order(
            primary.CreatePrimaryInvestmentOrderCommand(
                actor=investor, loan_id=str(loan.pk), amount_minor=1_000_00, idempotency_key=key
            )
        )

    reserved = order("before-change")
    LoanSecurity.objects.filter(pk=security.pk).update(holder_name="Another holder")
    assert "wait until the securities are verified" in proofs.investment_problem(loan)
    with pytest.raises(primary.MarketplacePrimaryValidationError, match="verified again"):
        order("after-change")
    acceptance = helpers._create_primary_acceptance(
        investor, order_id=str(reserved.id), idempotency_key="proof-accept"
    )
    with pytest.raises(primary.MarketplacePrimaryValidationError, match="verified again"):
        primary.allocate_primary_order_from_balance(
            primary.AllocatePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(reserved.id),
                **helpers._sandbox_ack(reserved),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="proof-allocate",
                **helpers._sensitive_code_payload(investor, "primary_investment"),
            )
        )
    security.refresh_from_db()
    _verify(security, documents)
    assert proofs.investment_problem(loan) == ""
    assert order("after-new-verification").status


def test_a_loan_without_any_verification_keeps_its_earlier_rules(admin_user: Model) -> None:
    """Audit S7-4: loans published before 18.10 (no verification at all) stay investable."""
    loan, _security, _documents = _loan_with_documents(admin_user)
    assert proofs.proofs_apply_to(loan) is False
    assert proofs.investment_problem(loan) == ""


def test_proof_documents_show_their_names_and_open_for_admins_only(admin_user: Model) -> None:
    """Audit S7-8: title, type, date and full id; a permission-checked, audited open action."""
    loan, security, documents = _loan_with_documents(admin_user)
    _verify(security, documents)
    status = proofs.security_proof_status(security)
    assert [item["title"] for item in status["documents"]] == [
        "Land register extract 2026",
        "Mortgage note",
    ]
    assert status["documents"][0]["id"] == documents[0]
    assert status["history"][0]["proofs"][0]["document"]["title"] == "Land register extract 2026"

    staff = Client()
    staff.force_login(cast(Any, _verifier("open-verifier@example.test")))
    url = f"/api/v1/loans/admin/securities/{security.id}/documents/{documents[0]}/"
    opened = staff.get(url)
    assert opened.status_code == 200, opened.content
    assert opened.json()["display_name"] == "Land register extract 2026"
    assert AuditEvent.objects.filter(action="loan.security_document_opened").count() == 1
    unrelated = _document(admin_user, cast(Any, loan).borrower, "Unrelated")
    assert (
        staff.get(f"/api/v1/loans/admin/securities/{security.id}/documents/{unrelated}/")
    ).status_code == 404

    investor = Client()
    investor.force_login(
        get_user_model().objects.create_user(
            email="nosy@example.test",
            full_name="Nosy",
            account_type="natural_person_lender",
            status="active",
        )
    )
    assert investor.get(url).status_code == 403


def test_the_verification_history_is_append_only_in_the_database(admin_user: Model) -> None:
    """Audit S7-9: ORM and raw SQL changes are refused."""
    _loan, security, documents = _loan_with_documents(admin_user)
    _verify(security, documents)
    verification = LoanSecurityVerification.objects.get(security=security)
    with pytest.raises((AppendOnlyViolation, DatabaseError)), transaction.atomic():
        verification.note = "changed"
        verification.save()
    with pytest.raises((AppendOnlyViolation, DatabaseError)), transaction.atomic():
        LoanSecurityVerification.objects.filter(pk=verification.pk).update(note="changed")
    table = LoanSecurityVerification._meta.db_table
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"UPDATE {table} SET note = 'raw' WHERE id = %s", [verification.pk.hex])
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {table} WHERE id = %s", [verification.pk.hex])
    verification.refresh_from_db()
    assert verification.note == ""


def test_full_primary_path_with_both_gates_on(admin_user: Model, settings: Any) -> None:
    """Audit step 7 (D2): declarations and security proofs both required, end to end."""
    settings.COMPLIANCE_DECLARATIONS_REQUIRED = True
    primary: Any = import_module("backend.apps.marketplace_primary.services")
    helpers: Any = import_module("backend.apps.marketplace_primary.tests.test_primary_marketplace")
    declarations: Any = import_module("backend.apps.kyc_compliance.declarations")
    loan, security, documents = _loan_with_documents(admin_user)
    _verify(security, documents)
    publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    investor = cast(
        Model,
        get_user_model().objects.create_user(
            email="both-gates@example.test",
            full_name="Both Gates",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    helpers._approve_financial_access(investor)
    helpers._declare_deposit(admin_user, investor, amount_minor=10_000_00, idempotency_key="bg")
    command = primary.CreatePrimaryInvestmentOrderCommand(
        actor=investor, loan_id=str(loan.pk), amount_minor=1_000_00, idempotency_key="bg-order"
    )
    with pytest.raises(primary.MarketplacePrimaryValidationError, match="declarations"):
        primary.create_primary_investment_order(command)
    declarations.submit_declaration(
        declarations.SubmitDeclarationCommand(
            actor=investor,
            data={
                "beneficial_owner_is_self": True,
                "sources_of_funds": ["salary"],
                "pep_status": "no",
                "yearly_volume_band": "10k_50k",
            },
        )
    )
    order = primary.create_primary_investment_order(command)
    acceptance = helpers._create_primary_acceptance(
        investor, order_id=str(order.id), idempotency_key="bg-accept"
    )
    allocated = primary.allocate_primary_order_from_balance(
        primary.AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            **helpers._sandbox_ack(order),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="bg-allocate",
            **helpers._sensitive_code_payload(investor, "primary_investment"),
        )
    )
    assert str(allocated.status) in {"balance_allocated", "partially_allocated"}
