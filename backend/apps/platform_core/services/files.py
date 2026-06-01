from __future__ import annotations

from dataclasses import dataclass

from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.models import StoredFile
from backend.apps.platform_core.models.files import FileAccessScope, FileScanStatus


@dataclass(frozen=True, slots=True)
class RegisterStoredFileCommand:
    storage_key: str
    original_filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    created_by: ActorRef
    owner: ActorRef | None = None
    access_scope: str = FileAccessScope.OWNER


def register_stored_file(command: RegisterStoredFileCommand) -> StoredFile:
    owner = command.owner or command.created_by
    return StoredFile.objects.create(
        storage_key=command.storage_key,
        original_filename=command.original_filename,
        content_type=command.content_type,
        size_bytes=command.size_bytes,
        checksum_sha256=command.checksum_sha256,
        created_by_type=command.created_by.actor_type,
        created_by_id=command.created_by.actor_id,
        owner_type=owner.actor_type,
        owner_id=owner.actor_id,
        access_scope=command.access_scope,
    )


def mark_file_scan_clean(stored_file: StoredFile) -> StoredFile:
    stored_file.scan_status = FileScanStatus.CLEAN
    stored_file.save(update_fields=["scan_status", "updated_at"])
    return stored_file


def can_access_stored_file(stored_file: StoredFile, actor: ActorRef) -> bool:
    if stored_file.scan_status != FileScanStatus.CLEAN:
        return False
    if stored_file.access_scope == FileAccessScope.PUBLIC:
        return True
    if stored_file.access_scope == FileAccessScope.INTERNAL:
        return actor.is_internal
    return stored_file.owner_type == actor.actor_type and stored_file.owner_id == actor.actor_id
