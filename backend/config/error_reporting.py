"""Exception reporting that never prints connection strings."""

# IP of Webby-Soft SRL.

from __future__ import annotations

import re

from django.views.debug import SafeExceptionReporterFilter


class SettingsMaskingExceptionReporterFilter(SafeExceptionReporterFilter):
    """Mask secrets and every URL/DSN setting on debug pages and error reports.

    Django's default filter masks names with API, TOKEN, KEY, SECRET, PASS or
    SIGNATURE only, so ``DATABASE_URL``, ``REDIS_URL`` and ``CELERY_BROKER_URL``
    (which carry passwords) were shown in clear (audit A-51).
    """

    hidden_settings = re.compile(
        "API|TOKEN|KEY|SECRET|PASS|SIGNATURE|PEPPER|AUTH|URL|DSN|DATABASE|BROKER|CACHE",
        flags=re.IGNORECASE,
    )
