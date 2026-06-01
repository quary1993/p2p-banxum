from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet
from django.conf import settings


def _fernet() -> Fernet:
    configured_key = getattr(settings, "AUTH_DELIVERY_SECRET_ENCRYPTION_KEY", "")
    if configured_key:
        return Fernet(configured_key.encode("ascii"))

    key_material = f"{settings.SECRET_KEY}:accounts-auth-delivery-secret:v1".encode()
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(key_material).digest())
    return Fernet(derived_key)


def encrypt_delivery_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_delivery_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")


def digest_secret(secret: str) -> str:
    pepper = getattr(settings, "AUTH_SECRET_DIGEST_PEPPER", "")
    key_material = f"{settings.SECRET_KEY}:{pepper}:accounts-auth-digest:v1".encode()
    return hmac.new(key_material, secret.encode("utf-8"), hashlib.sha256).hexdigest()
