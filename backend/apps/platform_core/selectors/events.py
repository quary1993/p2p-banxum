from __future__ import annotations

from django.db.models import QuerySet

from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.models.events import OutboxStatus


def pending_outbox_messages() -> QuerySet[OutboxMessage]:
    return OutboxMessage.objects.filter(status=OutboxStatus.PENDING).order_by("created_at", "id")
