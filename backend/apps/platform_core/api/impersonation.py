from __future__ import annotations

from typing import cast

from django.db.models import Model
from rest_framework.request import Request

from backend.apps.platform_core.services.impersonation import (
    READONLY_IMPERSONATION_HEADER,
    ReadOnlyImpersonationError,
    resolve_readonly_impersonation,
)


def readonly_read_actor_from_request(request: Request) -> tuple[Model, Model]:
    """Return (subject actor, audit actor) for read-only impersonated requests."""
    audit_actor = cast(Model, request.user)
    token = request.headers.get(READONLY_IMPERSONATION_HEADER, "")
    if not token:
        return audit_actor, audit_actor
    subject_actor, _context = resolve_readonly_impersonation(actor=audit_actor, token=token)
    return subject_actor, audit_actor


__all__ = [
    "READONLY_IMPERSONATION_HEADER",
    "ReadOnlyImpersonationError",
    "readonly_read_actor_from_request",
]
