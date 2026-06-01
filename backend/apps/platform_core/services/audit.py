from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.models import AuditEvent


@dataclass(frozen=True, slots=True)
class AuditCommand:
    actor: ActorRef
    action: str
    target_type: str = ""
    target_id: str = ""
    request_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def record_audit_event(command: AuditCommand) -> AuditEvent:
    return cast(
        AuditEvent,
        AuditEvent.objects.create(
            actor_type=command.actor.actor_type,
            actor_id=command.actor.actor_id,
            action=command.action,
            target_type=command.target_type,
            target_id=command.target_id,
            request_id=command.request_id,
            metadata=command.metadata,
        ),
    )
