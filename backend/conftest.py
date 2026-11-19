"""IP of Webby-Soft SRL. Test-wide settings."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _no_password_breach_lookup(settings: Any) -> None:
    """Tests never call the breached-password service (18.5); its own tests turn it on."""
    settings.AUTH_PASSWORD_BREACH_CHECK_ENABLED = False


@pytest.fixture(autouse=True)
def _bind_test_codes_at_first_use() -> Iterator[None]:
    """18.5 operation binding in the domain tests.

    Most domain tests get an email code from ``platform_core.tests.factories`` before they
    build the operation. Such a code is marked "bound at first use": the first module that
    checks it gives it the fingerprint of the operation it is running, then the real check
    runs (normalized details, fingerprint comparison, single use). Every caller therefore still
    builds valid operation details in every test. The binding itself (code requested for other
    details is refused) is tested with codes issued for explicit details, which this hook
    never touches.
    """
    services: Any = __import__("backend.apps.accounts_auth.services", fromlist=["x"])
    models: Any = __import__("backend.apps.accounts_auth.models", fromlist=["x"])
    factories: Any = __import__("backend.apps.platform_core.tests.factories", fromlist=["x"])
    original = services.consume_sensitive_action_code

    def consume(command: Any) -> Any:
        expected = getattr(command, "expected_operation_fingerprint", None)
        if expected:
            models.SensitiveActionCode.objects.filter(
                id=command.code_id,
                operation_fingerprint="",
                operation_summary=factories.TEST_BOUND_AT_USE_SUMMARY,
            ).update(operation_fingerprint=expected)
        return original(command)

    # An own patcher: a test's ``monkeypatch.undo()`` must not remove this hook.
    patcher = pytest.MonkeyPatch()
    patcher.setattr(services, "consume_sensitive_action_code", consume)
    yield
    patcher.undo()
