"""Cancel open listings that product rule C18 no longer allows.

Holdings of loans that are late, in default or time-extended are not listable, and
there is no admin approval workflow any more (plan/09 MKT-DEC-009). This migration
cancels every listing still waiting for approval and every open listing whose loan is
not performing. No money moves: a listing reserves nothing. Each cancellation keeps a
reason, gets an append-only ``auto_cancelled`` event from the system actor, and the
seller gets the usual in-app notice (email outbox topic shown in the portal).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import migrations
from django.db.models import Q
from django.utils import timezone

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
PERFORMING_LOAN_STATUS = "active"
NOTICE_TOPIC = "email.secondary_market_listing_status"


def _reason(*, previous_status: str, loan_status: str) -> str:
    if loan_status == "late":
        return "Cancelled automatically because the loan is late. Late loans cannot be listed."
    if loan_status == "defaulted":
        return (
            "Cancelled automatically because the loan is in default. "
            "Loans in default cannot be listed."
        )
    if previous_status == "approval_requested":
        return (
            "Cancelled automatically because listing approval was retired. "
            "Only loans that are paid on time can be listed."
        )
    return f"Cancelled automatically because the loan status changed to {loan_status}."


def cancel_late_or_defaulted_listings(apps, schema_editor):
    listing_model = apps.get_model("secondary_market", "SecondaryMarketListing")
    event_model = apps.get_model("secondary_market", "SecondaryMarketListingEvent")
    outbox_model = apps.get_model("platform_core", "OutboxMessage")
    user_model = apps.get_model("accounts_auth", "User")
    now = timezone.now()
    listings = (
        listing_model.objects.select_related("loan")
        .filter(
            Q(status="approval_requested")
            | (Q(status="active") & ~Q(loan__status=PERFORMING_LOAN_STATUS))
        )
        .order_by("created_at", "id")
    )
    for listing in listings:
        previous_status = str(listing.status)
        loan_status = str(listing.loan.status)
        reason = _reason(previous_status=previous_status, loan_status=loan_status)
        metadata = dict(listing.metadata or {})
        metadata["c18_rule_migration"] = {
            "previous_status": previous_status,
            "loan_status": loan_status,
            "cancelled_at": now.isoformat(),
        }
        # queryset.update(): a system lifecycle change, not a seller edit.
        listing_model.objects.filter(pk=listing.pk).update(
            status="cancelled",
            cancelled_by_user_id=None,
            cancelled_at=now,
            cancellation_reason=reason,
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
            note=reason,
            metadata={
                "source_type": "c18_rule_migration",
                "loan_id": str(listing.loan_id),
                "loan_status": loan_status,
                "price_bps_preserved": int(listing.price_bps),
            },
            idempotency_key=f"secondary-c18-rule-migration:{listing.pk}",
        )
        seller = user_model.objects.filter(pk=listing.seller_user_id).only("email").first()
        email = str(getattr(seller, "email", "") or "").strip().lower()
        if not email:
            continue
        outbox_model.objects.get_or_create(
            idempotency_key=f"email:secondary-listing:{listing.pk}:c18-rule-migration",
            defaults={
                "topic": NOTICE_TOPIC,
                "payload": {
                    "user_id": str(listing.seller_user_id),
                    "email": email,
                    "subject": f"{settings.PLATFORM_BRAND_NAME} secondary-market listing cancelled",
                    "body_text": (
                        f"We cancelled your secondary-market listing for loan "
                        f"{listing.loan.title}. {reason}\n\n"
                        "No money was moved. You keep the holding in your portfolio."
                    ),
                    "template_key": "secondary_market.listing_status.v1",
                    "metadata": {
                        "listing_id": str(listing.pk),
                        "holding_id": str(listing.holding_id),
                        "loan_id": str(listing.loan_id),
                        "loan_status": loan_status,
                        "reason": "c18_rule_migration",
                    },
                },
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts_auth", "0007_user_investor_reference"),
        ("platform_core", "0007_storyimage"),
        ("secondary_market", "0008_listing_automatic_refresh_events"),
    ]

    operations = [
        migrations.RunPython(
            cancel_late_or_defaulted_listings,
            migrations.RunPython.noop,
        ),
    ]
