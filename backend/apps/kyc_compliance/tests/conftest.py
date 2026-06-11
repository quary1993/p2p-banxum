from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _force_mock_didit_sessions(settings: Any) -> None:
    settings.DIDIT_SESSION_PROVIDER = "mock"
