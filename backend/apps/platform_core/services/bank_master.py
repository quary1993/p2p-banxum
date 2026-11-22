"""IP of Webby-Soft SRL. 18.3: bank names for IBANs (SIX bank master for CH and LI).

A Swiss or Liechtenstein IBAN carries the bank's IID in positions 5 to 9; its name comes from the
SIX bank master. Other IBANs have no public master here: the investor may type the bank name.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterable
from dataclasses import dataclass

from django.db import transaction

from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.models import SwissBankMasterEntry
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event

SIX_COUNTRIES = frozenset({"CH", "LI"})
_IID_HEADERS = ("iid", "bc-nr", "bc nr", "clearing")
_NAME_HEADERS = (
    "name of bank/institution",
    "bank or institution name",
    "bankorinstitutionname",
    "bank/institution",
    "bank/institut",
    "bankname",
    "name",
)
_BIC_HEADERS = ("bic", "swift")
_PLACE_HEADERS = ("place", "town name", "townname", "ort", "domicile", "lieu")
# SIX Bank Master v3: the entry type (BankMaster or BankMasterConcatenated) and the new IID.
_ENTRY_TYPE_HEADERS = ("entry type", "entrytype", "entry_type", "concatenation")
_NEW_IID_HEADERS = ("new iid", "newiid", "new_iid", "neue iid", "nouvel iid")
_VALID_ON_HEADERS = ("valid on", "validon", "valid_on", "gültig ab", "valid from")


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
    # Audit S2-7: old IIDs that now give the name of their new IID, and entries removed
    # because they are no longer in the file.
    concatenated: int = 0
    removed: int = 0
    sha256: str = ""
    valid_on: str = ""


def _column(header: list[str], candidates: tuple[str, ...], *, exact_first: bool = True) -> int:
    lowered = [cell.strip().lower() for cell in header]
    for candidate in candidates:
        if exact_first and candidate in lowered:
            return lowered.index(candidate)
    for index, cell in enumerate(lowered):
        if any(cell.startswith(candidate) for candidate in candidates):
            return index
    return -1


def _cell(row: list[str], index: int) -> str:
    return row[index].strip() if 0 <= index < len(row) else ""


def _iid(value: str) -> str:
    """An IID without leading zeros, or "" when the cell is not a 3- to 5-digit IID."""
    value = value.strip()
    if not value.isdigit():
        return ""
    iid = str(int(value))
    return iid if len(iid) <= 5 else ""


def _resolve(iid: str, concatenations: dict[str, str]) -> str:
    """The current IID of an IID, following "New IID" links; a loop is a file error."""
    seen = [iid]
    while iid in concatenations:
        iid = concatenations[iid]
        if iid in seen:
            chain = " -> ".join([*seen, iid])
            raise BankMasterError(f"The file has a concatenation loop: IID {chain}.")
        seen.append(iid)
    return iid


@transaction.atomic
def import_six_bank_master(text: str) -> BankMasterImportResult:
    """Import the SIX bank master CSV (semicolon or comma separated, with a header row).

    Audit S2-7, SIX Bank Master v3: an institution row ("BankMaster") gives the name of its IID.
    A concatenation row ("BankMasterConcatenated", or any row with a "New IID") says that the
    IID is no longer valid (for example after a merger) and is replaced by the new IID: an IBAN
    with the old IID shows the new institution's name. The file replaces the whole master in
    one transaction: an IID that is no longer in the file is removed.
    """
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
    entry_type_index = _column(header, _ENTRY_TYPE_HEADERS)
    new_iid_index = _column(header, _NEW_IID_HEADERS)
    valid_on_index = _column(header, _VALID_ON_HEADERS)
    institutions: dict[str, dict[str, str]] = {}
    concatenations: dict[str, str] = {}
    valid_on = ""
    for row in rows[1:]:
        iid = _iid(_cell(row, iid_index))
        if not iid:
            continue
        valid_on = valid_on or _cell(row, valid_on_index)
        new_iid = _iid(_cell(row, new_iid_index))
        if new_iid or "concat" in _cell(row, entry_type_index).lower():
            if not new_iid:
                raise BankMasterError(f"The concatenation row of IID {iid} has no new IID.")
            if new_iid != iid:
                concatenations[iid] = new_iid
            continue
        name = _cell(row, name_index)
        if not name or iid in institutions:
            # Older files list branches after the head office: the first row of an IID wins.
            continue
        institutions[iid] = {
            "bank_name": name[:255],
            "bic": _cell(row, bic_index).upper()[:11],
            "place": _cell(row, place_index)[:128],
        }
    entries = {iid: data for iid, data in institutions.items() if iid not in concatenations}
    concatenated = 0
    for old_iid in concatenations:
        current = institutions.get(_resolve(old_iid, concatenations))
        if current is not None:
            entries[old_iid] = current
            concatenated += 1
    if not entries:
        raise BankMasterError("The file has no bank rows.")
    removed, _ = SwissBankMasterEntry.objects.exclude(iid__in=list(entries)).delete()
    created = updated = 0
    for iid, defaults in entries.items():
        _entry, was_created = SwissBankMasterEntry.objects.update_or_create(
            iid=iid, defaults=defaults
        )
        created += int(was_created)
        updated += int(not was_created)
    result = BankMasterImportResult(
        rows=len(entries),
        created=created,
        updated=updated,
        concatenated=concatenated,
        removed=removed,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        valid_on=valid_on,
    )
    record_audit_event(
        AuditCommand(
            actor=ActorRef.system(),
            action="bank_master.imported",
            target_type="SwissBankMaster",
            target_id=valid_on or result.sha256[:16],
            metadata={
                "sha256": result.sha256,
                "valid_on": valid_on,
                "rows": result.rows,
                "created": created,
                "updated": updated,
                "concatenated": concatenated,
                "removed": removed,
            },
        )
    )
    return result
