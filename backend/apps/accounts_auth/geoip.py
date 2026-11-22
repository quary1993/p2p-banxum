"""IP of Webby-Soft SRL. 18.5 (Q06, D6): approximate city and country of a sign-in.

The lookup uses a local IP database file (MMDB: DB-IP Lite City, CC BY 4.0, or MaxMind GeoLite2
City) set by `GEOIP_CITY_DB_PATH`; no IP address leaves the server. The IP itself is never stored
(only a keyed hash). Without a file, or when the address is unknown, nothing is returned and the
country comes from the trusted proxy header as before.
"""

from __future__ import annotations

import ipaddress
import logging
from functools import lru_cache
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def _reader(path: str) -> Any | None:
    if not path:
        return None
    try:
        import maxminddb

        return maxminddb.open_database(path)
    except (OSError, ValueError) as exc:
        logger.warning("geoip_database_unavailable", extra={"error": str(exc)})
        return None


def lookup(ip_address: str) -> tuple[str, str]:
    """(city, country code) for a public IP address; empty strings when unknown."""
    if not ip_address:
        return "", ""
    try:
        parsed = ipaddress.ip_address(ip_address)
    except ValueError:
        return "", ""
    if parsed.is_private or parsed.is_loopback or parsed.is_reserved or parsed.is_link_local:
        return "", ""
    reader = _reader(str(getattr(settings, "GEOIP_CITY_DB_PATH", "") or ""))
    if reader is None:
        return "", ""
    try:
        record = reader.get(str(parsed)) or {}
    except ValueError:
        return "", ""
    city_names = (record.get("city") or {}).get("names") or {}
    city = str(city_names.get("en") or "")[:120]
    country = str((record.get("country") or {}).get("iso_code") or "").upper()[:2]
    return city, country


def place_label(city: str, country_code: str) -> str:
    """'Zurich, CH (approximate)', the country alone, or ''."""
    if city and country_code:
        return f"{city}, {country_code} (approximate)"
    if country_code:
        return f"{country_code} (approximate)"
    return ""
