"""IP of Webby-Soft SRL. Shared FX test setup."""

from __future__ import annotations

from typing import Any

import pytest

from backend.apps.fx.tests.factories import set_fx_enabled


@pytest.fixture(autouse=True)
def fx_switched_on(request: Any) -> None:
    """FX is off by default since 2026-10-16; the FX test packs exercise it switched on.

    Tests of the switch itself call ``set_fx_enabled(False)``.
    """
    if request.node.get_closest_marker("django_db") is None:
        return
    request.getfixturevalue("db")
    set_fx_enabled(True)
