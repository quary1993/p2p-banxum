"""IP of Webby-Soft SRL. 18.6 test helper: Default is never automatic any more.

The servicing tests written before 18.6 reached "defaulted" with the status scan alone. Now the
scan stops at Late and the admin declares Default; ``scan_and_declare`` runs the scan and then
declares Default on each scanned loan that the scan left Late with the Default days reached.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from django.apps import apps
from freezegun import freeze_time

from backend.apps.platform_core.domain.loan_status import default_can_be_declared
from backend.apps.platform_core.selectors.settings import loan_status_thresholds
from backend.apps.servicing import engine
from backend.apps.servicing.services import (
    ScanLoanServicingStatusesCommand,
    _first_outstanding_installment_status,
    scan_loan_servicing_statuses,
)


def scan_and_declare(command: ScanLoanServicingStatusesCommand) -> Any:
    result = scan_loan_servicing_statuses(command)
    loans = apps.get_model("loans", "Loan").objects.filter(status="late", product_type="direct")
    if command.loan_ids:
        loans = loans.filter(id__in=[str(value) for value in command.loan_ids])
    for loan in loans:
        _status, days, _outstanding, _row = _first_outstanding_installment_status(
            loan, as_of_date=command.as_of_date, lock_installments=False
        )
        if default_can_be_declared(days, loan_status_thresholds(loan)):
            # Declared on the scan's day, as the automatic Default of the old tests was.
            day = command.as_of_date
            with freeze_time(datetime(day.year, day.month, day.day, 11, 0, tzinfo=UTC)):
                engine.declare_loan_default(
                    engine.DeclareLoanDefaultCommand(
                        actor=command.actor, loan_id=str(cast(Any, loan).pk)
                    )
                )
    return result
