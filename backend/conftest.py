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
def _media_outside_the_repository(settings: Any, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Uploaded and seeded files (for example the seed proof placeholders) go to a temporary
    folder, never to the repository's media folder. A test may set its own folder."""
    settings.MEDIA_ROOT = str(tmp_path_factory.getbasetemp() / "media")


@pytest.fixture(autouse=True)
def _no_declarations_gate(settings: Any) -> None:
    """Tests of other features invest without declarations and publish without security
    verifications; the 18.10 tests turn these gates on."""
    settings.COMPLIANCE_DECLARATIONS_REQUIRED = False
    settings.SECURITY_PROOFS_REQUIRED = False


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


@pytest.fixture
def row_locks_need_a_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit S1-1: PostgreSQL refuses select_for_update() outside a transaction; SQLite does not
    check it. A test that asks for this fixture fails when the code under test takes a row lock
    without opening its own atomic block (the test case's transaction does not count, because
    production API views open none)."""
    from django.db import connection
    from django.db.models.query import QuerySet

    original = QuerySet.select_for_update
    test_depth = len(connection.atomic_blocks)

    def checked(self: Any, *args: Any, **kwargs: Any) -> Any:
        assert len(connection.atomic_blocks) > test_depth, "select_for_update outside atomic"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "select_for_update", checked)



@pytest.fixture
def pre_cutover_loans(monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit S5-7: a new loan uses the 18.6 engine. Test modules written for the earlier monthly
    schedule (contracts from before the engine) ask for this fixture, so a loan they create
    without a convention keeps the earlier schedule, as the loans of migration 0029 do."""
    from importlib import import_module

    from django.apps import apps

    loans_services: Any = import_module("backend.apps.loans.services")
    legacy = "legacy_monthly"

    def resolve(command: Any) -> str:
        return str(command.interest_convention or legacy)

    monkeypatch.setattr(loans_services, "_resolve_interest_convention", resolve)
    field = apps.get_model("loans", "Loan")._meta.get_field("interest_convention")
    monkeypatch.setattr(field, "_get_default", lambda: legacy, raising=False)


@pytest.fixture
def boundary_offers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit S6-4: a new Loan Originator offer is priced with accrued interest. Test modules
    written for the boundary-installment offers of before 18.7 ask for this fixture, so an offer
    they create without a rule keeps the boundary rule."""
    from importlib import import_module

    originator: Any = import_module("backend.apps.originator_claims.services")
    boundary = originator.OriginatorPricingRule.BOUNDARY_INSTALLMENT

    def resolve(command: Any, *, existing_rule: str | None = None) -> Any:
        return originator.OriginatorPricingRule(command.pricing_rule or boundary)

    monkeypatch.setattr(originator, "_resolve_pricing_rule", resolve)
