"""IP of Webby-Soft SRL. 18.3: bank names for IBANs (SIX bank master for CH and LI).

A Swiss or Liechtenstein IBAN carries the bank's IID in positions 5 to 9; its name comes from the
SIX bank master. Other IBANs have no public master here: the investor may type the bank name.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass

from django.db import transaction

from backend.apps.platform_core.models import SwissBankMasterEntry

SIX_COUNTRIES = frozenset({"CH", "LI"})
_IID_HEADERS = ("iid", "bc-nr", "bc nr", "clearing")
_NAME_HEADERS = (
    "name of bank/institution",
    "bank/institution",
    "bank/institut",
    "bankname",
    "name",
)
_BIC_HEADERS = ("bic", "swift")
_PLACE_HEADERS = ("place", "ort", "domicile", "lieu")


class BankMasterError(ValueError):
    pass


def compact_iban(iban: str) -> str:
    return "".join(str(iban).split()).upper()


def iban_iid(iban: str) -> str:
    """The IID of a CH or LI IBAN without leading zeros, or "" for another IBAN."""
    compact = compact_iban(iban)
    if compact[:2] not in SIX_COUNTRIES or len(compact) < 9 or not compact[4:9].isdigit():
        return ""
    return str(int(compact[4:9]))


def uses_bank_master(iban: str) -> bool:
    return compact_iban(iban)[:2] in SIX_COUNTRIES


def bank_names_for_ibans(ibans: Iterable[str]) -> dict[str, str]:
    """Bank name per IBAN from the SIX master (only CH and LI IBANs with a known IID)."""
    by_iid: dict[str, list[str]] = {}
    for iban in ibans:
        iid = iban_iid(iban)
        if iid:
            by_iid.setdefault(iid, []).append(iban)
    if not by_iid:
        return {}
    names = dict(
        SwissBankMasterEntry.objects.filter(iid__in=list(by_iid)).values_list("iid", "bank_name")
    )
    return {iban: names[iid] for iid, items in by_iid.items() if iid in names for iban in items}


@dataclass(frozen=True, slots=True)
class BankMasterImportResult:
    rows: int
    created: int
    updated: int


def _column(header: list[str], candidates: tuple[str, ...], *, exact_first: bool = True) -> int:
    lowered = [cell.strip().lower() for cell in header]
    for candidate in candidates:
        if exact_first and candidate in lowered:
            return lowered.index(candidate)
    for index, cell in enumerate(lowered):
        if any(cell.startswith(candidate) for candidate in candidates):
            return index
    return -1


@transaction.atomic
def import_six_bank_master(text: str) -> BankMasterImportResult:
    """Import the SIX bank master CSV (semicolon or comma separated, with a header row)."""
    sample = text[:4096]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise BankMasterError("The file is empty.")
    header = rows[0]
    iid_index = _column(header, _IID_HEADERS)
    name_index = _column(header, _NAME_HEADERS)
    if iid_index < 0 or name_index < 0:
        raise BankMasterError("The file needs an IID column and a bank name column.")
    bic_index = _column(header, _BIC_HEADERS)
    place_index = _column(header, _PLACE_HEADERS)
    created = updated = 0
    seen: set[str] = set()
    for row in rows[1:]:
        if len(row) <= max(iid_index, name_index):
            continue
        raw_iid = row[iid_index].strip()
        name = row[name_index].strip()
        if not raw_iid.isdigit() or not name:
            continue
        iid = str(int(raw_iid))
        if iid in seen or len(iid) > 5:
            # The first row of an IID is its head office.
            continue
        seen.add(iid)
        defaults = {
            "bank_name": name[:255],
            "bic": row[bic_index].strip().upper()[:11] if 0 <= bic_index < len(row) else "",
            "place": row[place_index].strip()[:128] if 0 <= place_index < len(row) else "",
        }
        _entry, was_created = SwissBankMasterEntry.objects.update_or_create(
            iid=iid, defaults=defaults
        )
        created += int(was_created)
        updated += int(not was_created)
    return BankMasterImportResult(rows=len(seen), created=created, updated=updated)
