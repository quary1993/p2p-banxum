from __future__ import annotations

import pytest

from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.models.files import FileAccessScope
from backend.apps.platform_core.services.files import (
    RegisterStoredFileCommand,
    can_access_stored_file,
    mark_file_scan_clean,
    register_stored_file,
)


@pytest.mark.django_db
def test_stored_file_is_not_accessible_until_scan_is_clean() -> None:
    owner = ActorRef("investor", "inv-1")
    stored_file = register_stored_file(
        RegisterStoredFileCommand(
            storage_key="quarantine/file.pdf",
            original_filename="file.pdf",
            content_type="application/pdf",
            size_bytes=100,
            checksum_sha256="a" * 64,
            created_by=owner,
        )
    )

    assert can_access_stored_file(stored_file, owner) is False

    mark_file_scan_clean(stored_file)

    assert can_access_stored_file(stored_file, owner) is True
    assert can_access_stored_file(stored_file, ActorRef("investor", "other")) is False


@pytest.mark.django_db
def test_internal_files_are_only_available_to_internal_actors_after_clean_scan() -> None:
    stored_file = register_stored_file(
        RegisterStoredFileCommand(
            storage_key="internal/statement.pdf",
            original_filename="statement.pdf",
            content_type="application/pdf",
            size_bytes=100,
            checksum_sha256="b" * 64,
            created_by=ActorRef("admin", "admin-1"),
            access_scope=FileAccessScope.INTERNAL,
        )
    )
    mark_file_scan_clean(stored_file)

    assert can_access_stored_file(stored_file, ActorRef("admin", "admin-2")) is True
    assert can_access_stored_file(stored_file, ActorRef("investor", "inv-1")) is False
