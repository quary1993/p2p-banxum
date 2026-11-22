# IP of Webby-Soft SRL.
"""Swiss-borrower creditor limit: the rule applied to one loan (18.9; replaces MKT-DEC-028).

Since 18.9 (Q03, E-02) a Swiss borrower (one UID) is in one creditor mode
(``platform_core.domain.creditor_regime``): in "sandbox" mode there is no creditor limit (the
borrower's total stays below CHF 500,000); in "10/20" mode a financing may have at most 10
relevant creditors and the borrower at most 20. Where the limit applies, a participation that
takes a new place must invest at least

    min(R, max(minimum, round up to whole units of max(0, P - F) / N))

(``P`` success threshold, ``F`` allocated, ``R`` remaining, ``N`` places left under all limits).
An investor already in the financing adds with the normal minimum, capped by the remaining
capacity. With no place left a new creditor is refused (``swiss_investor_limit``).

Money is in integer minor units. Which loans the limit applies to and who the creditors are is
read by ``backend.apps.marketplace_primary.investor_limit``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SWISS_BORROWER_MAX_INVESTORS_SETTING = "investment.swiss_borrower_max_investors"
SWISS_BORROWER_MAX_INVESTORS_DEFAULT = 20
SWISS_INVESTOR_LIMIT_CODE = "swiss_investor_limit"
WHOLE_UNIT_MINOR = 100


def swiss_investor_limit_message(max_investors: int) -> str:
    return (
        "This loan to a Swiss company has no place left for a new creditor (10/20 mode: at most "
        f"{max_investors} creditors per financing and 20 per borrower)."
    )


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def new_investor_minimum_minor(
    *,
    minimum_minor: int,
    remaining_minor: int,
    places_left: int,
    threshold_minor: int = 0,
    allocated_minor: int = 0,
) -> int | None:
    """What a new creditor must invest now, or None when no place is left (18.9 formula)."""
    if places_left <= 0:
        return None
    remaining = max(0, remaining_minor)
    missing = max(0, threshold_minor - allocated_minor)
    share = _ceil_div(missing, places_left) if missing else 0
    share = _ceil_div(share, WHOLE_UNIT_MINOR) * WHOLE_UNIT_MINOR
    return min(remaining, max(minimum_minor, share))


@dataclass(frozen=True, slots=True)
class InvestorLimit:
    """The creditor limit of one loan at one moment.

    ``max_investors`` (creditors per financing) is None when no limit applies (not a Swiss
    borrower, or the borrower is in sandbox mode). ``investor_ids`` are the financing's investors;
    ``borrower_creditor_ids`` every relevant creditor of the borrower UID (investors of its active
    loans, Loan Originators keeping a part, external non-bank creditors).
    """

    max_investors: int | None
    investor_ids: frozenset[str] = field(default_factory=frozenset)
    borrower_creditor_ids: frozenset[str] = field(default_factory=frozenset)
    borrower_max_creditors: int | None = None
    threshold_minor: int = 0
    allocated_minor: int = 0
    mode: str = ""

    @property
    def applies(self) -> bool:
        return self.max_investors is not None

    @property
    def investors_count(self) -> int:
        return len(self.investor_ids)

    def _borrower_places_left(self) -> int | None:
        if self.borrower_max_creditors is None:
            return None
        return max(0, self.borrower_max_creditors - len(self.borrower_creditor_ids))

    def places_left_for(self, investor_user_id: str | None) -> int | None:
        """Places this investor could take: the financing's, and the borrower's for a new one."""
        if self.max_investors is None:
            return None
        financing = max(0, self.max_investors - len(self.investor_ids))
        borrower = self._borrower_places_left()
        if borrower is None or (
            investor_user_id is not None and str(investor_user_id) in self.borrower_creditor_ids
        ):
            return financing
        return min(financing, borrower)

    @property
    def places_left(self) -> int | None:
        """Places left for a creditor new to the borrower."""
        return self.places_left_for(None)

    def is_investor(self, investor_user_id: str | None) -> bool:
        return investor_user_id is not None and str(investor_user_id) in self.investor_ids

    def refuses_new_investor(self, investor_user_id: str | None) -> bool:
        """True when this investor would need a place and none is left."""
        return (
            self.applies
            and not self.is_investor(investor_user_id)
            and self.places_left_for(investor_user_id) == 0
        )

    def investor_minimum_minor(
        self,
        *,
        investor_user_id: str | None,
        minimum_minor: int,
        remaining_minor: int,
    ) -> int:
        """The minimum this investor must invest now (no investor id: a new investor).

        Without a limit (or with nothing left to invest) this is the loan's normal minimum. A
        new investor when no place is left gets the capped normal minimum here; callers refuse
        them first with ``refuses_new_investor``.
        """
        if not self.applies or remaining_minor <= 0:
            return minimum_minor
        capped_minimum = min(minimum_minor, remaining_minor)
        if self.is_investor(investor_user_id):
            return capped_minimum
        new_minimum = new_investor_minimum_minor(
            minimum_minor=minimum_minor,
            remaining_minor=remaining_minor,
            places_left=int(self.places_left_for(investor_user_id) or 0),
            threshold_minor=self.threshold_minor,
            allocated_minor=self.allocated_minor,
        )
        return capped_minimum if new_minimum is None else new_minimum

    def transfer_refused(
        self,
        *,
        buyer_user_id: str,
        seller_stays_investor: bool,
        seller_stays_borrower_creditor: bool | None = None,
    ) -> bool:
        """A whole-holding transfer to a new creditor must not raise the counts above the limit.

        Each count is checked on its own. In the financing, the buyer takes the seller's place
        when the seller sells their last holding of the loan; otherwise the buyer needs a free
        place. In the borrower count, a buyer already a creditor of the borrower needs nothing;
        otherwise the buyer takes the seller's place only when the seller stops being a creditor
        of the borrower (no holding left in any of its financings), else needs a free place.
        ``seller_stays_borrower_creditor`` defaults to ``seller_stays_investor``.
        """
        if not self.applies or self.is_investor(buyer_user_id):
            return False
        if seller_stays_borrower_creditor is None:
            seller_stays_borrower_creditor = seller_stays_investor
        financing_left = max(0, int(self.max_investors or 0) - len(self.investor_ids))
        if seller_stays_investor and financing_left == 0:
            return True
        if str(buyer_user_id) in self.borrower_creditor_ids:
            return False
        borrower_left = self._borrower_places_left()
        return bool(seller_stays_borrower_creditor and borrower_left == 0)
