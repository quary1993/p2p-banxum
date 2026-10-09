"""Investors download the borrower documents listed on a loan page (audit FRONTCODE-27)."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client

from backend.apps.marketplace_primary.services import (
    MarketplacePrimaryAuthorizationError,
    MarketplacePrimaryValidationError,
    download_marketplace_borrower_document,
    get_full_marketplace_loan,
)
from backend.apps.marketplace_primary.tests.test_primary_marketplace import (
    _approve_financial_access,
    _create_published_loan,
)
from backend.apps.platform_core.models import AuditEvent, StoredFile

PDF_BYTES = b"%PDF-1.4\n% borrower financials\n"


@pytest.fixture
def admin_user() -> Model:
    return cast(
        Model,
        get_user_model().objects.create_user(
            email="docs-admin@example.test",
            password="AdminPass123!",
            full_name="Docs Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def investor() -> Model:
    return cast(
        Model,
        get_user_model().objects.create_user(
            email="docs-investor@example.test",
            full_name="Docs Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )


@pytest.fixture
def media_root(settings: Any, tmp_path: Path) -> Path:
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


def _borrower_document(
    admin_user: Model,
    borrower: Any,
    media_root: Path,
    *,
    name: str,
    investor_visible: bool = True,
    scan_status: str = "clean",
    content: bytes = PDF_BYTES,
) -> Any:
    storage_key = f"borrowers/{borrower.pk}/{name}.pdf"
    path = media_root / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    stored_file = StoredFile.objects.create(
        storage_key=storage_key,
        original_filename=f"{name}.pdf",
        content_type="application/pdf",
        size_bytes=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        scan_status=scan_status,
        owner_type="borrower",
        owner_id=str(borrower.pk),
        created_by_type="admin",
        created_by_id=str(admin_user.pk),
    )
    return apps.get_model("entities", "BorrowerDocument").objects.create(
        borrower=borrower,
        document_type="financials",
        display_name=name,
        stored_file=stored_file,
        investor_visible=investor_visible,
        created_by_admin_id=admin_user.pk,
        created_by_account_type="admin",
    )


@pytest.mark.django_db
def test_investor_downloads_a_listed_borrower_document(
    admin_user: Model, investor: Model, media_root: Path
) -> None:
    _approve_financial_access(investor)
    loan = cast(Any, _create_published_loan(admin_user))
    document = _borrower_document(admin_user, loan.borrower, media_root, name="Financials 2025")

    listed = get_full_marketplace_loan(actor=investor, loan_id=str(loan.pk))
    assert [item["id"] for item in listed["borrower_disclosure"]["documents"]] == [str(document.pk)]
    payload = download_marketplace_borrower_document(
        actor=investor, loan_id=str(loan.pk), document_id=str(document.pk)
    )

    assert payload["content_type"] == "application/pdf"
    assert payload["content_encoding"] == "base64"
    assert base64.b64decode(payload["content"]) == PDF_BYTES
    assert payload["filename"] == "Financials-2025.pdf"
    assert payload["content_sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()
    audit = AuditEvent.objects.get(action="marketplace.borrower_document_downloaded")
    assert audit.target_id == str(document.pk)
    assert audit.metadata["investor_user_id"] == str(investor.pk)


@pytest.mark.django_db
def test_borrower_document_download_follows_the_listing_rules(
    admin_user: Model, investor: Model, media_root: Path
) -> None:
    loan = cast(Any, _create_published_loan(admin_user))
    other_loan = cast(Any, _create_published_loan(admin_user))
    listed = _borrower_document(admin_user, loan.borrower, media_root, name="Presentation")
    internal = _borrower_document(
        admin_user, loan.borrower, media_root, name="Internal memo", investor_visible=False
    )
    unscanned = _borrower_document(
        admin_user, loan.borrower, media_root, name="Unscanned", scan_status="quarantined"
    )
    changed = _borrower_document(admin_user, loan.borrower, media_root, name="Changed")
    (media_root / changed.stored_file.storage_key).write_bytes(b"tampered")

    # No financial access (KYC, phone): no download.
    with pytest.raises(MarketplacePrimaryAuthorizationError):
        download_marketplace_borrower_document(
            actor=investor, loan_id=str(loan.pk), document_id=str(listed.pk)
        )
    _approve_financial_access(investor)
    for document_id, loan_id in (
        (internal.pk, loan.pk),
        (unscanned.pk, loan.pk),
        (listed.pk, other_loan.pk),
    ):
        with pytest.raises(MarketplacePrimaryValidationError, match="Document not found"):
            download_marketplace_borrower_document(
                actor=investor, loan_id=str(loan_id), document_id=str(document_id)
            )
    with pytest.raises(MarketplacePrimaryValidationError, match="not available"):
        download_marketplace_borrower_document(
            actor=investor, loan_id=str(loan.pk), document_id=str(changed.pk)
        )
    # A draft loan is not readable, so neither are its documents.
    loan.status = "draft"
    loan.save(update_fields=["status"])
    with pytest.raises(MarketplacePrimaryValidationError):
        download_marketplace_borrower_document(
            actor=investor, loan_id=str(loan.pk), document_id=str(listed.pk)
        )


@pytest.mark.django_db
def test_borrower_document_download_api(
    client: Client, admin_user: Model, investor: Model, media_root: Path
) -> None:
    loan = cast(Any, _create_published_loan(admin_user))
    document = _borrower_document(admin_user, loan.borrower, media_root, name="Financials")
    url = f"/api/v1/marketplace/primary/loans/{loan.pk}/documents/{document.pk}/"

    assert client.get(url).status_code in {401, 403}
    client.force_login(cast(Any, investor))
    assert client.get(url).status_code == 403
    _approve_financial_access(investor)
    response = client.get(url)
    assert response.status_code == 200
    assert base64.b64decode(response.json()["content"]) == PDF_BYTES
