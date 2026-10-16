"""Fixtures of the public-site tests: an anonymous API client and a pinned throttle clock."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from backend.apps.platform_core.services import rate_limits

# Start of a UTC day (a multiple of 86400, so also of 600 and 3600) plus one minute: every
# fixed window starts fresh and none rolls over during a test unless the test moves it.
BASE_EPOCH = 1_800_000_000 - (1_800_000_000 % 86_400) + 60


@dataclass
class ThrottleClock:
    now: int = BASE_EPOCH

    def advance(self, seconds: int) -> None:
        self.now += seconds


@pytest.fixture
def throttle_clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[ThrottleClock]:
    cache.clear()
    clock = ThrottleClock()
    monkeypatch.setattr(rate_limits, "current_epoch_seconds", lambda: clock.now)
    yield clock
    cache.clear()


@pytest.fixture
def api_client(throttle_clock: ThrottleClock) -> APIClient:
    return APIClient()
