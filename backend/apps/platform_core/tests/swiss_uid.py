"""IP of Webby-Soft SRL. 18.9 test helper: valid synthetic Swiss UIDs (mod-11 check digit)."""

from __future__ import annotations

from itertools import count

_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4)
_SEQUENCE = count(10_000_000)


def uid_for(base: int) -> str:
    """The first valid UID at or after the 8-digit ``base`` (bases with check digit 10 skip)."""
    value = base
    while True:
        digits = f"{value % 100_000_000:08d}"
        check = 11 - sum(int(d) * w for d, w in zip(digits, _WEIGHTS, strict=True)) % 11
        if check == 11:
            check = 0
        if check != 10:
            text = f"{digits}{check}"
            return f"CHE-{text[0:3]}.{text[3:6]}.{text[6:9]}"
        value += 1


def next_test_uid() -> str:
    """A new valid UID on each call (one borrower per UID in tests)."""
    return uid_for(next(_SEQUENCE) * 7 % 90_000_000 + 10_000_000)
