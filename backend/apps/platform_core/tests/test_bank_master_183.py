"""IP of Webby-Soft SRL. 18.3: bank names from the SIX bank master (CH and LI IBANs)."""

from __future__ import annotations

import pytest

from backend.apps.platform_core.services.bank_master import (
    BankMasterError,
    bank_names_for_ibans,
    iban_iid,
    import_six_bank_master,
    uses_bank_master,
)

pytestmark = pytest.mark.django_db

SIX_SAMPLE = (
    "Group;IID;New IID;SIC-IID;Headquarters;Name of bank/institution;Place;BIC\n"
    "01;100;;;100;Schweizerische Nationalbank;Bern;SNBZCHZZXXX\n"
    "01;100;;;100;Schweizerische Nationalbank (branch);Zürich;\n"
    "06;4835;;;4835;Example Bank AG;Zürich;EXAMCHZZ\n"
)


def test_the_six_file_gives_the_bank_name_of_ch_and_li_ibans() -> None:
    result = import_six_bank_master(SIX_SAMPLE)
    assert (result.rows, result.created, result.updated) == (2, 2, 0)
    # The head office (first row of an IID) wins; a new import updates the names.
    assert import_six_bank_master(SIX_SAMPLE).updated == 2
    assert iban_iid("CH56 0483 5012 3456 7800 9") == "4835"
    assert iban_iid("DE89 3704 0044 0532 0130 00") == ""
    assert uses_bank_master("li21 0881 0000 2324 013a a") is True
    assert bank_names_for_ibans(["CH5604835012345678009", "DE89370400440532013000"]) == {
        "CH5604835012345678009": "Example Bank AG"
    }
    with pytest.raises(BankMasterError):
        import_six_bank_master("just;some;columns\n1;2;3\n")


# Audit S2-7: the fields of the SIX Bank Master v3 record description (institution rows and
# concatenation rows, where "New IID" replaces an IID that is no longer valid).
SIX_V3_HEADER = (
    "Group;IID;Valid on;Entry type;New IID;SIC IID;Headquarters;IID type;QR IID belongs to;"
    "Bank or institution name;Street name;Building number;Post code;Town name;Country;BIC\n"
)


def _v3_row(iid: str, *, name: str = "", entry: str = "BankMaster", new_iid: str = "") -> str:
    kind = "HEADQUARTERS" if entry == "BankMaster" else ""
    return (
        f"06;{iid};2026-11-20;{entry};{new_iid};;{iid if name else ''};{kind};;{name};"
        f"Bahnhofstrasse;1;8001;Zürich;CH;{'EXAMCHZZXXX' if name else ''}\n"
    )


def test_an_old_iid_gives_the_name_of_its_new_iid() -> None:
    from django.apps import apps

    text = (
        SIX_V3_HEADER
        + _v3_row("4835", name="Example Bank AG")
        # A merger: 8401 is replaced by 4835; an even older IID 777 was replaced by 8401.
        + _v3_row("8401", entry="BankMasterConcatenated", new_iid="4835")
        + _v3_row("777", entry="BankMasterConcatenated", new_iid="8401")
    )
    result = import_six_bank_master(text)
    assert (result.rows, result.concatenated, result.valid_on) == (3, 2, "2026-11-20")
    assert bank_names_for_ibans(["CH9308401000000000001", "CH9300777000000000001"]) == {
        "CH9308401000000000001": "Example Bank AG",
        "CH9300777000000000001": "Example Bank AG",
    }
    audit = apps.get_model("platform_core", "AuditEvent").objects.get(action="bank_master.imported")
    assert audit.metadata["sha256"] == result.sha256
    assert (audit.metadata["concatenated"], audit.metadata["valid_on"]) == (2, "2026-11-20")


def test_a_new_file_replaces_the_master_and_removes_iids_no_longer_listed() -> None:
    import_six_bank_master(
        SIX_V3_HEADER + _v3_row("4835", name="Example Bank AG") + _v3_row("9000", name="Gone AG")
    )
    result = import_six_bank_master(SIX_V3_HEADER + _v3_row("4835", name="Example Bank AG"))
    assert (result.rows, result.updated, result.removed) == (1, 1, 1)
    assert bank_names_for_ibans(["CH9309000000000000001"]) == {}


def test_a_concatenation_loop_is_refused_and_changes_nothing() -> None:
    import_six_bank_master(SIX_V3_HEADER + _v3_row("4835", name="Example Bank AG"))
    loop = (
        SIX_V3_HEADER
        + _v3_row("4835", name="Example Bank AG")
        + _v3_row("8401", entry="BankMasterConcatenated", new_iid="8402")
        + _v3_row("8402", entry="BankMasterConcatenated", new_iid="8401")
    )
    with pytest.raises(BankMasterError, match="concatenation loop"):
        import_six_bank_master(loop)
    with pytest.raises(BankMasterError, match="no new IID"):
        import_six_bank_master(
            SIX_V3_HEADER + _v3_row("8401", entry="BankMasterConcatenated", new_iid="")
        )
    assert bank_names_for_ibans(["CH5604835012345678009"]) == {
        "CH5604835012345678009": "Example Bank AG"
    }
