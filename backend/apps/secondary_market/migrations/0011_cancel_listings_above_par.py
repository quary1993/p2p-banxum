"""Owner decision 2026-10-16 (row 4): no premium, a sale price is par or a discount.

New listings and edits are refused above 100% of the current principal. This migration
cancels every open listing that is still priced above par (``price_bps`` > 10,000), the
same way migration 0009 cancelled listings for rule C18: no money moves (a listing
reserves nothing), the holding stays with the seller, the listing keeps a reason, an
append-only ``auto_cancelled`` event from the system actor is recorded, and the seller
gets the usual notice (email outbox topic shown in the portal). Listings at par or a
discount are not touched.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import migrations
from django.utils import timezone

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
PAR_PRICE_BPS = 10_000
OPEN_STATUSES = ("active", "approval_requested")
NOTICE_TOPIC = "email.secondary_market_listing_status"
SOURCE_TYPE = "par_rule_migration"
REASON = (
    "Cancelled automatically because the sale price was above par. A listing can be at "
    "most 100% of the principal (par). You can list the holding again at par or a discount."
)


def cancel_listings_above_par(apps, schema_editor):
    listing_model = apps.get_model("secondary_market", "SecondaryMarketListing")
    event_model = apps.get_model("secondary_market", "SecondaryMarketListingEvent")
    outbox_model = apps.get_model("platform_core", "OutboxMessage")
    user_model = apps.get_model("accounts_auth", "User")
    now = timezone.now()
    listings = (
        listing_model.objects.select_related("loan")
        .filter(status__in=OPEN_STATUSES, price_bps__gt=PAR_PRICE_BPS)
        .order_by("created_at", "id")
    )
    for listing in listings:
        previous_status = str(listing.status)
        metadata = dict(listing.metadata or {})
        metadata[SOURCE_TYPE] = {
            "previous_status": previous_status,
            "price_bps": int(listing.price_bps),
            "cancelled_at": now.isoformat(),
        }
        # queryset.update(): a system lifecycle change, not a seller edit.
        listing_model.objects.filter(pk=listing.pk).update(
            status="cancelled",
            cancelled_by_user_id=None,
            cancelled_at=now,
            cancellation_reason=REASON,
            listed_at=None,
            metadata=metadata,
            updated_at=now,
        )
        event_model.objects.create(
            listing_id=listing.pk,
            holding_id=listing.holding_id,
            loan_id=listing.loan_id,
            seller_user_id=listing.seller_user_id,
            event_type="auto_cancelled",
            actor_user_id=SYSTEM_ACTOR_ID,
            actor_account_type="system",
            previous_status=previous_status,
            new_status="cancelled",
            note=REASON,
            metadata={
                "source_type": SOURCE_TYPE,
                "loan_id": str(listing.loan_id),
                "price_bps": int(listing.price_bps),
                "maximum_price_bps": PAR_PRICE_BPS,
            },
            idempotency_key=f"secondary-par-rule-migration:{listing.pk}",
        )
        seller = user_model.objects.filter(pk=listing.seller_user_id).only("email").first()
        email = str(getattr(seller, "email", "") or "").strip().lower()
        if not email:
            continue
        outbox_model.objects.get_or_create(
            idempotency_key=f"email:secondary-listing:{listing.pk}:par-rule-migration",
            defaults={
                "topic": NOTICE_TOPIC,
                "payload": {
                    "user_id": str(listing.seller_user_id),
                    "email": email,
                    "subject": f"{settings.PLATFORM_BRAND_NAME} secondary-market listing cancelled",
                    "body_text": (
                        f"We cancelled your secondary-market listing for loan "
                        f"{listing.loan.title}. {REASON}\n\n"
                        "No money was moved. You keep the holding in your portfolio."
                    ),
                    "template_key": "secondary_market.listing_status.v1",
                    "metadata": {
                        "listing_id": str(listing.pk),
                        "holding_id": str(listing.holding_id),
                        "loan_id": str(listing.loan_id),
                        "price_bps": int(listing.price_bps),
                        "reason": SOURCE_TYPE,
                    },
                },
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts_auth", "0008_emaillogintoken_superseded_at"),
        ("platform_core", "0007_storyimage"),
        ("secondary_market", "0010_secondary_fee_defaults_2026_10_16"),
    ]

    operations = [
        migrations.RunPython(cancel_listings_above_par, migrations.RunPython.noop),
    ]
