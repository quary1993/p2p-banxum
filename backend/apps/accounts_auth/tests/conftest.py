from __future__ import annotations

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_auth_throttle_cache() -> None:
    cache.clear()
