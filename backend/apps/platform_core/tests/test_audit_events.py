from __future__ import annotations

import pytest

from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.models import AuditEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event


@pytest.mark.django_db
def test_audit_events_are_append_only() -> None:
    event = record_audit_event(
        AuditCommand(
            actor=ActorRef("admin", "admin-1"),
            action="test.action",
            target_type="Thing",
            target_id="thing-1",
            metadata={"field": "value"},
        )
    )

    event.action = "changed"
    with pytest.raises(AppendOnlyViolation):
        event.save()

    with pytest.raises(AppendOnlyViolation):
        AuditEvent.objects.filter(id=event.id).update(action="changed")

    with pytest.raises(AppendOnlyViolation):
        event.delete()
