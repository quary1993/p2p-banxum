# IP of Webby-Soft SRL.
"""Swiss-borrower investor limit: the rule itself (owner decision 2026-10-16).

A loan to a Swiss borrower may have at most ``max_investors`` investors (platform setting
``investment.swiss_borrower_max_investors``, default 20; 0 switches the limit off). So that
the places left can still fill the loan, the minimum for a new investor goes up
(plan/09 MKT-DEC-028):

    places_left = max_investors - investors
    minimum_now = min(remaining, max(minimum, ceil(remaining / places_left)))

The share ``ceil(remaining / places_left)`` is rounded up to whole currency units
(multiples of 100 minor units). An investor who already invests in the loan does not take
a new place: their minimum is the normal minimum, capped by the remaining capacity. With
no place left a new investor is refused (``swiss_investor_limit``).

Money is in integer minor units. Which loans the limit applies to and who its investors
are is read by ``backend.apps.marketplace_primary.investor_limit``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SWISS_BORROWER_MAX_INVESTORS_SETTING = "investment.swiss_borrower_max_investors"
SWISS_BORROWER_MAX_INVESTORS_DEFAULT = 20
SWISS_INVESTOR_LIMIT_CODE = "swiss_investor_limit"
WHOLE_UNIT_MINOR = 100


def swiss_investor_limit_message(max_investors: int) -> str:
    return f"This loan to a Swiss company already has the maximum of {max_investors} investors."


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def new_investor_minimum_minor(
    *,
    minimum_minor: int,
    remaining_minor: int,
    places_left: int,
) -> int | None:
    """What a new investor must invest now, or None when no place is left."""
    if places_left <= 0:
        return None
    remaining = max(0, remaining_minor)
    share = _ceil_div(remaining, places_left)
    share = _ceil_div(share, WHOLE_UNIT_MINOR) * WHOLE_UNIT_MINOR
    return min(remaining, max(minimum_minor, share))


@dataclass(frozen=True, slots=True)
class InvestorLimit:
    """The investor limit of one loan at one moment.

    ``max_investors`` is None when no limit applies (not a Swiss borrower, or the
    platform setting is 0). ``investor_ids`` are the loan's investors when it applies.
    """

    max_investors: int | None
    investor_ids: frozenset[str] = field(default_factory=frozenset)

    @property
    def applies(self) -> bool:
        return self.max_investors is not None

    @property
    def investors_count(self) -> int:
        return len(self.investor_ids)

    @property
    def places_left(self) -> int | None:
        if self.max_investors is None:
            return None
        return max(0, self.max_investors - len(self.investor_ids))

    def is_investor(self, investor_user_id: str | None) -> bool:
        return investor_user_id is not None and str(investor_user_id) in self.investor_ids

    def refuses_new_investor(self, investor_user_id: str | None) -> bool:
        """True when this investor would need a place and none is left."""
        return self.applies and not self.is_investor(investor_user_id) and self.places_left == 0

    def investor_minimum_minor(
        self,
        *,
        investor_user_id: str | None,
        minimum_minor: int,
        remaining_minor: int,
    ) -> int:
        """The minimum this investor must invest now (no investor id: a new investor).

        Without a limit (or with nothing left to invest) this is the loan's normal
        minimum. A new investor when no place is left gets the capped normal minimum
        here; callers refuse them first with ``refuses_new_investor``.
        """
        if not self.applies or remaining_minor <= 0:
            return minimum_minor
        capped_minimum = min(minimum_minor, remaining_minor)
        if self.is_investor(investor_user_id):
            return capped_minimum
        new_minimum = new_investor_minimum_minor(
            minimum_minor=minimum_minor,
            remaining_minor=remaining_minor,
            places_left=int(self.places_left or 0),
        )
        return capped_minimum if new_minimum is None else new_minimum

    def transfer_refused(self, *, buyer_user_id: str, seller_stays_investor: bool) -> bool:
        """A whole-holding transfer to a new investor must not raise the count above the limit.

        The buyer takes the seller's place when the seller sells their last holding of
        the loan; otherwise the buyer needs a free place.
        """
        if not self.applies or self.is_investor(buyer_user_id):
            return False
        return seller_stays_investor and self.places_left == 0
