from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from backend.apps.accounts_auth.models import User
from backend.apps.platform_core.domain.access import is_admin_actor, is_superadmin_actor


class IsAdminPortalUser(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return isinstance(user, User) and is_admin_actor(user)


class IsSuperAdminUser(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return isinstance(user, User) and is_superadmin_actor(user)
