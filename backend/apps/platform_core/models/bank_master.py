"""IP of Webby-Soft SRL. 18.3: the SIX bank master of Swiss and Liechtenstein banks.

The bank name on the investor's bank card comes from here for CH and LI IBANs (the IID is part of
the IBAN). The platform team imports the official SIX file (``import_six_bank_master``); it is
reference data and is kept across QA resets. Each import replaces the whole master; an IID that
SIX has concatenated to a new IID keeps a row with the new institution's name (audit S2-7).
"""

from __future__ import annotations

from django.db import models

from backend.apps.platform_core.models.base import TimestampedModel


class SwissBankMasterEntry(TimestampedModel):
    # The institution identification (IID), without leading zeros.
    iid = models.CharField(max_length=5, primary_key=True)
    bank_name = models.CharField(max_length=255)
    bic = models.CharField(max_length=11, blank=True)
    place = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ["iid"]

    def __str__(self) -> str:
        return f"{self.iid} {self.bank_name}"
