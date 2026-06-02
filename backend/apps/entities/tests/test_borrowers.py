from __future__ import annotations

from typing import Any, cast

import pytest
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client

from backend.apps.entities.models import (
    BorrowerDocumentType,
    BorrowerEntity,
    BorrowerEntityEvent,
    BorrowerEntityType,
    BorrowerKybStatus,
)
from backend.apps.entities.services import (
    AddBorrowerDocumentCommand,
    BorrowerAuthorizationError,
    BorrowerValidationError,
    CreateBorrowerEntityCommand,
    UpdateBorrowerEntityCommand,
    add_borrower_document,
    borrower_can_transact,
    borrower_investor_disclosure,
    create_borrower_entity,
    update_borrower_entity,
)
from backend.apps.entities.tests.factories import create_user
from backend.apps.platform_core.domain.access import actor_ref_for_user
from backend.apps.platform_core.models import AuditEvent, DomainEvent, StoredFile
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.platform_core.models.files import FileAccessScope
from backend.apps.platform_core.services.files import (
    RegisterStoredFileCommand,
    mark_file_scan_clean,
    register_stored_file,
)


@pytest.fixture
def admin_user() -> Model:
    return create_user(email="admin@example.test")


@pytest.fixture
def investor() -> Model:
    return create_user(
        email="investor@example.test",
        account_type="natural_person_lender",
        is_staff=False,
    )


def _stored_file(admin_user: Model, *, storage_key: str = "borrowers/file.pdf") -> StoredFile:
    return register_stored_file(
        RegisterStoredFileCommand(
            storage_key=storage_key,
            original_filename="file.pdf",
            content_type="application/pdf",
            size_bytes=100,
            checksum_sha256="a" * 64,
            created_by=actor_ref_for_user(admin_user),
            access_scope=FileAccessScope.INTERNAL,
        )
    )


@pytest.mark.django_db
def test_admin_can_create_borrower_with_optional_financial_disclosure(admin_user: Model) -> None:
    borrower = create_borrower_entity(
        CreateBorrowerEntityCommand(
            actor=admin_user,
            legal_name="Garanta Real Estate SPV AG",
            year_founded=2018,
            entity_type=BorrowerEntityType.SPECIAL_PURPOSE_VEHICLE,
            kyb_status=BorrowerKybStatus.APPROVED,
            country="Switzerland",
            financials_currency="chf",
            assets_minor=12_000_000_00,
            liabilities_minor=4_000_000_00,
            revenue_last_year_minor=900_000_00,
            profit_last_year_minor=120_000_00,
            note="KYB approved offline.",
        )
    )

    assert borrower.legal_name == "Garanta Real Estate SPV AG"
    assert borrower.financials_currency == "CHF"
    assert borrower.can_transact is True
    assert BorrowerEntityEvent.objects.filter(borrower=borrower, event_type="created").exists()
    assert AuditEvent.objects.filter(action="borrower.created", target_id=str(borrower.id)).exists()
    assert DomainEvent.objects.filter(
        event_type="BorrowerEntityCreated",
        aggregate_id=str(borrower.id),
    ).exists()


@pytest.mark.django_db
def test_non_admin_cannot_create_borrower(investor: Model) -> None:
    with pytest.raises(BorrowerAuthorizationError):
        create_borrower_entity(
            CreateBorrowerEntityCommand(
                actor=investor,
                legal_name="Should Fail AG",
                year_founded=2020,
            )
        )


@pytest.mark.django_db
def test_financial_amounts_require_currency_and_nonnegative_assets(admin_user: Model) -> None:
    with pytest.raises(BorrowerValidationError):
        create_borrower_entity(
            CreateBorrowerEntityCommand(
                actor=admin_user,
                legal_name="Missing Currency AG",
                year_founded=2020,
                assets_minor=100_00,
            )
        )

    with pytest.raises(BorrowerValidationError):
        create_borrower_entity(
            CreateBorrowerEntityCommand(
                actor=admin_user,
                legal_name="Negative Assets AG",
                year_founded=2020,
                financials_currency="CHF",
                assets_minor=-1,
            )
        )


@pytest.mark.django_db
def test_kyb_status_change_requires_note_or_evidence(admin_user: Model) -> None:
    borrower = create_borrower_entity(
        CreateBorrowerEntityCommand(
            actor=admin_user,
            legal_name="Pending Borrower AG",
            year_founded=2021,
        )
    )

    with pytest.raises(BorrowerValidationError):
        update_borrower_entity(
            UpdateBorrowerEntityCommand(
                actor=admin_user,
                borrower_id=str(borrower.id),
                kyb_status=BorrowerKybStatus.APPROVED,
            )
        )

    updated = update_borrower_entity(
        UpdateBorrowerEntityCommand(
            actor=admin_user,
            borrower_id=str(borrower.id),
            kyb_status=BorrowerKybStatus.APPROVED,
            evidence_summary="Offline KYB reviewed and approved.",
        )
    )

    assert updated.kyb_status == BorrowerKybStatus.APPROVED
    assert borrower_can_transact(updated) is True
    assert BorrowerEntityEvent.objects.filter(
        borrower=borrower,
        event_type="kyb_status_changed",
    ).exists()


@pytest.mark.django_db
def test_borrower_document_visibility_requires_clean_file(admin_user: Model) -> None:
    borrower = create_borrower_entity(
        CreateBorrowerEntityCommand(
            actor=admin_user,
            legal_name="Disclosure Borrower AG",
            year_founded=2019,
            country="Switzerland",
        )
    )
    stored_file = _stored_file(admin_user)
    document = add_borrower_document(
        AddBorrowerDocumentCommand(
            actor=admin_user,
            borrower_id=str(borrower.id),
            stored_file_id=str(stored_file.id),
            document_type=BorrowerDocumentType.PRESENTATION,
            display_name="Borrower presentation",
            investor_visible=True,
        )
    )

    disclosure_before_scan = borrower_investor_disclosure(borrower)
    mark_file_scan_clean(stored_file)
    disclosure_after_scan = borrower_investor_disclosure(borrower)

    assert document.investor_visible is True
    assert disclosure_before_scan == {
        "legal_name": "Disclosure Borrower AG",
        "year_founded": 2019,
        "country": "Switzerland",
    }
    assert disclosure_after_scan["documents"][0]["display_name"] == "Borrower presentation"
    assert AuditEvent.objects.filter(
        action="borrower.document_added",
        target_id=str(borrower.id),
    ).exists()


@pytest.mark.django_db
def test_borrower_admin_api_create_filter_update_document_and_disclosure(
    client: Client,
    admin_user: Model,
) -> None:
    client.force_login(cast(Any, admin_user))
    stored_file = _stored_file(admin_user, storage_key="borrowers/api-file.pdf")
    mark_file_scan_clean(stored_file)

    create_response = client.post(
        "/api/v1/entities/admin/borrowers/",
        data={
            "legal_name": "API Borrower AG",
            "year_founded": 2017,
            "entity_type": BorrowerEntityType.SWISS_COMPANY,
            "country": "Switzerland",
        },
        content_type="application/json",
    )
    borrower_id = create_response.json()["id"]
    list_response = client.get(
        "/api/v1/entities/admin/borrowers/",
        data={"q": "API Borrower", "country": "Switzerland"},
    )
    update_response = client.patch(
        f"/api/v1/entities/admin/borrowers/{borrower_id}/",
        data={
            "kyb_status": BorrowerKybStatus.APPROVED,
            "evidence_summary": "Approved offline.",
        },
        content_type="application/json",
    )
    document_response = client.post(
        f"/api/v1/entities/admin/borrowers/{borrower_id}/documents/",
        data={
            "stored_file_id": stored_file.id,
            "document_type": BorrowerDocumentType.FINANCIALS,
            "display_name": "Financials 2025",
            "investor_visible": True,
        },
        content_type="application/json",
    )
    disclosure_response = client.get(
        f"/api/v1/entities/admin/borrowers/{borrower_id}/investor-disclosure-preview/"
    )
    events_response = client.get(f"/api/v1/entities/admin/borrowers/{borrower_id}/events/")

    assert create_response.status_code == 201
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert update_response.status_code == 200
    assert update_response.json()["can_transact"] is True
    assert document_response.status_code == 201
    assert disclosure_response.status_code == 200
    assert "assets_minor" not in disclosure_response.json()
    assert disclosure_response.json()["documents"][0]["display_name"] == "Financials 2025"
    assert events_response.status_code == 200
    assert [event["event_type"] for event in events_response.json()] == [
        "created",
        "kyb_status_changed",
        "document_added",
    ]


@pytest.mark.django_db
def test_borrower_entity_events_are_append_only(admin_user: Model) -> None:
    borrower = create_borrower_entity(
        CreateBorrowerEntityCommand(
            actor=admin_user,
            legal_name="Append Only Borrower AG",
            year_founded=2016,
        )
    )
    event = BorrowerEntityEvent.objects.get(borrower=borrower, event_type="created")

    event.note = "changed"
    with pytest.raises(AppendOnlyViolation):
        event.save()
    with pytest.raises(AppendOnlyViolation):
        BorrowerEntityEvent.objects.filter(id=event.id).update(note="changed")
    with pytest.raises(AppendOnlyViolation):
        BorrowerEntityEvent.objects.filter(id=event.id).delete()

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE entities_borrowerentityevent SET note = %s WHERE id = %s",
                ["changed", event.id],
            )

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM entities_borrowerentityevent WHERE id = %s",
                [event.id],
            )


@pytest.mark.django_db
def test_investor_cannot_use_borrower_admin_api(client: Client, investor: Model) -> None:
    client.force_login(cast(Any, investor))

    response = client.get("/api/v1/entities/admin/borrowers/")

    assert response.status_code == 403
    assert BorrowerEntity.objects.count() == 0
