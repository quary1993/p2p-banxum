from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from backend.apps.accounts_auth.models import User
from backend.apps.accounts_auth.services import is_admin_account, is_superadmin_account


class IsAdminPortalUser(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return isinstance(user, User) and user.can_login and is_admin_account(user)


class IsSuperAdminUser(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return isinstance(user, User) and user.can_login and is_superadmin_account(user)
