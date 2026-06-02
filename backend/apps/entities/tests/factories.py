from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from django.db.models import Model


def create_user(
    *,
    email: str,
    account_type: str = "admin",
    status: str = "active",
    is_staff: bool = True,
    is_superuser: bool = False,
) -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            password="AdminPass123!" if is_staff else None,
            full_name=email.split("@", maxsplit=1)[0].replace("-", " ").title(),
            account_type=account_type,
            status=status,
            is_staff=is_staff,
            is_superuser=is_superuser,
        ),
    )
