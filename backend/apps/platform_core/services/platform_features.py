"""IP of Webby-Soft SRL. Platform feature switches that a superadmin turns on or off.

Each switch is a boolean platform setting. A change goes through the audited settings
service (a new setting version with the reason, and an audit event). A switch without a
row, or with any value other than ``true``, is off (see ``platform_switch_enabled``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction

from backend.apps.platform_core.domain.access import actor_ref_for_user, is_superadmin_actor
from backend.apps.platform_core.models import PlatformSetting, PlatformSettingVersion
from backend.apps.platform_core.selectors.settings import platform_switch_enabled
from backend.apps.platform_core.services.settings import (
    DEFAULT_PLATFORM_SETTINGS,
    SetPlatformSettingCommand,
    set_platform_setting,
)

FX_ENABLED_SETTING_KEY = "fx.enabled"
MAX_REASON_LENGTH = 1000


@dataclass(frozen=True, slots=True)
class PlatformFeature:
    key: str
    label: str
    description: str


PLATFORM_FEATURES: tuple[PlatformFeature, ...] = (
    PlatformFeature(
        key=FX_ENABLED_SETTING_KEY,
        label="Currency exchange (FX)",
        description=(
            "Investors can get FX quotes and exchange CHF and EUR. When off, the FX page "
            "is hidden and every quote and exchange is refused. Past exchanges stay visible."
        ),
    ),
)


class PlatformFeatureError(ValueError):
    pass


class PlatformFeatureAuthorizationError(PlatformFeatureError):
    pass


class PlatformFeatureValidationError(PlatformFeatureError):
    pass


@dataclass(frozen=True, slots=True)
class SetPlatformFeatureCommand:
    actor: Any
    key: str
    enabled: bool
    reason: str


def _require_superadmin(actor: Any) -> None:
    if not is_superadmin_actor(actor):
        raise PlatformFeatureAuthorizationError("Only a superadmin can change platform features.")


def _feature(key: str) -> PlatformFeature:
    for feature in PLATFORM_FEATURES:
        if feature.key == key:
            return feature
    raise PlatformFeatureValidationError("This platform feature does not exist.")


def _setting_description(key: str) -> str:
    for definition in DEFAULT_PLATFORM_SETTINGS:
        if definition.key == key:
            return definition.description
    return ""


def _changed_by_email(version: PlatformSettingVersion) -> str:
    if version.changed_by_type not in {"admin", "superadmin"}:
        return ""
    user = get_user_model().objects.filter(pk=version.changed_by_id).only("email").first()
    return str(getattr(user, "email", "") or "")


def _last_change(key: str) -> dict[str, Any] | None:
    version = PlatformSettingVersion.objects.filter(key=key).order_by("-version").first()
    if version is None:
        return None
    return {
        "version": int(version.version),
        "enabled": version.value is True,
        "changed_at": version.occurred_at,
        "changed_by_type": str(version.changed_by_type),
        "changed_by_id": str(version.changed_by_id),
        "changed_by_email": _changed_by_email(version),
        "reason": str(version.reason),
    }


def _feature_payload(feature: PlatformFeature) -> dict[str, Any]:
    return {
        "key": feature.key,
        "title": feature.label,
        "description": feature.description,
        "enabled": platform_switch_enabled(feature.key),
        "last_change": _last_change(feature.key),
    }


def list_platform_features(*, actor: Any) -> list[dict[str, Any]]:
    """Every platform switch with its state and last change (superadmin only)."""
    _require_superadmin(actor)
    return [_feature_payload(feature) for feature in PLATFORM_FEATURES]


@transaction.atomic
def set_platform_feature(command: SetPlatformFeatureCommand) -> dict[str, Any]:
    """Turn one platform switch on or off through the audited settings service."""
    _require_superadmin(command.actor)
    feature = _feature(str(command.key))
    if type(command.enabled) is not bool:
        raise PlatformFeatureValidationError("Choose on or off.")
    reason = str(command.reason or "").strip()
    if not reason:
        raise PlatformFeatureValidationError("Enter a reason for this change.")
    if len(reason) > MAX_REASON_LENGTH:
        raise PlatformFeatureValidationError(
            f"The reason can be at most {MAX_REASON_LENGTH} characters."
        )
    # Lock the row so two superadmins cannot both record the same change.
    PlatformSetting.objects.select_for_update().filter(key=feature.key).first()
    previous = platform_switch_enabled(feature.key)
    if previous == command.enabled:
        state = "on" if previous else "off"
        raise PlatformFeatureValidationError(
            f"{feature.label} is already {state}. Nothing was changed."
        )
    set_platform_setting(
        SetPlatformSettingCommand(
            actor=actor_ref_for_user(command.actor),
            key=feature.key,
            value=command.enabled,
            value_type="boolean",
            reason=reason,
            description=_setting_description(feature.key),
            metadata={
                "feature": feature.key,
                "previous_enabled": previous,
                "enabled": command.enabled,
                "reason": reason,
                "source": "admin_platform_features",
            },
        )
    )
    return _feature_payload(feature)
