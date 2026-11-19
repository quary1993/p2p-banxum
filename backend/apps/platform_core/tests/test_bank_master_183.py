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
