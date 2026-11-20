"""IP of Webby-Soft SRL. Audit S4-1 (Q06): the one place that turns an IP address into a keyed hash.

Authentication and public-form records never store an IP address itself. They store this hash:
an HMAC-SHA-256 with a key derived from ``SECRET_KEY`` and a purpose label, so a copy of the
database cannot be turned back into addresses by hashing the address space. The same address
gives the same hash inside one purpose, which is enough to compare two records.
"""

from __future__ import annotations

import hashlib
import hmac

from django.conf import settings

# Sign-in history and every other authentication record (comparable with each other).
ACCOUNT_IP_PURPOSE = "accounts-sign-in-ip:v1"
# Public forms and the newsletter.
PUBLIC_IP_PURPOSE = "communications-public-ip:v1"


def keyed_ip_hash(ip_address: str | None, *, purpose: str = ACCOUNT_IP_PURPOSE) -> str:
    """The keyed hash of an IP address ("" for no address)."""
    address = str(ip_address or "").strip()
    if not address:
        return ""
    pepper = hashlib.sha256(f"{settings.SECRET_KEY}:{purpose}".encode()).digest()
    return hmac.new(pepper, address.encode("utf-8"), hashlib.sha256).hexdigest()
