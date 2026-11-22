# IP of Webby-Soft SRL.
"""U33-DEC-06/07: reconcile the open listings with the new price range and seller fee.

New listings can be priced at 0-102% of the outstanding principal, and the seller fee is
``min(rate x sale price of the principal, rate x outstanding principal)``, with no minimum
fee and no fee on accrued interest. Open listings are not repriced and their accepted
terms do not change:

- every open listing is at par or a discount (migration 0011 cancelled the rest), so the
  capped fee is the same amount as the fee the seller accepted;
- the listing keeps the fee rate and the minimum fee it stores until the seller edits it
  or a loan change refreshes it, as before (MKT-DEC-017);
- no money moves and no seller has to confirm again.

Each open listing gets a ``u33_dec_06_07`` metadata entry that records this check. Sold,
cancelled, removed and rejected listings are not touched; closed trades are not
recalculated.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import migrations
from django.utils import timezone

OPEN_STATUSES = ("active", "approval_requested")
METADATA_KEY = "u33_dec_06_07"


def _fee(price_minor: int, fee_bps: int, minimum_fee_minor: int) -> int:
    calculated = Decimal(price_minor) * Decimal(fee_bps) / Decimal(10_000)
    return max(int(calculated.quantize(Decimal("1"), rounding=ROUND_HALF_UP)), minimum_fee_minor)


def plan_listing_reconciliation(listing: Any, now_iso: str) -> dict[str, Any]:
    """The metadata of one open listing after the U33-DEC-06/07 check."""
    principal = int(listing.current_principal_minor)
    price = int(listing.transfer_price_minor)
    fee_bps = int(listing.maker_fee_bps)
    minimum = int(listing.minimum_maker_fee_minor)
    accepted_fee = _fee(price, fee_bps, minimum)
    capped_fee = max(min(_fee(price, fee_bps, 0), _fee(principal, fee_bps, 0)), minimum)
    metadata = dict(listing.metadata or {})
    metadata[METADATA_KEY] = {
        "checked_at": now_iso,
        "price_bps": int(listing.price_bps),
        "maker_fee_bps": fee_bps,
        "minimum_maker_fee_minor": minimum,
        "accepted_fee_minor": accepted_fee,
        "capped_fee_minor": capped_fee,
        "terms_unchanged": accepted_fee == capped_fee,
        "note": (
            "The accepted terms stay. The new price range (0-102%) and the capped seller "
            "fee apply when the seller edits the listing or a loan change refreshes it."
        ),
    }
    return metadata


def reconcile_open_listings(apps: Any, schema_editor: Any) -> None:
    listing_model = apps.get_model("secondary_market", "SecondaryMarketListing")
    now_iso = timezone.now().isoformat()
    for listing in listing_model.objects.filter(status__in=OPEN_STATUSES).iterator():
        # queryset.update() keeps updated_at: the seller did not edit the listing.
        listing_model.objects.filter(pk=listing.pk).update(
            metadata=plan_listing_reconciliation(listing, now_iso)
        )


class Migration(migrations.Migration):
    dependencies = [
        ("secondary_market", "0012_allow_zero_principal_price"),
    ]

    operations = [
        migrations.RunPython(reconcile_open_listings, migrations.RunPython.noop),
    ]
