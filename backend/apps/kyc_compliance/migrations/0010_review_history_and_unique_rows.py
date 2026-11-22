# IP of Webby-Soft SRL. Audit S7-6: one unresolved necessary review and one current
# re-verification per investor; the review keeps the events that joined it (step 7, D4).
# Re-audit R7-1: earlier duplicate rows are merged first (no row deleted).

from collections import defaultdict

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def merge_duplicate_rows(apps, schema_editor):
    """Re-audit R7-1: rows the earlier schema allowed are merged before the unique rules.

    Unresolved necessary reviews of one investor: the oldest stays, takes the triggers and the
    history of the others, and stays open if one of them was open; the others are closed with a
    note that names the review they joined. Current re-verifications: the newest stays; the
    others are marked replaced. No row is deleted.
    """
    review_model = apps.get_model("kyc_compliance", "ComplianceReview")
    reverification_model = apps.get_model("kyc_compliance", "InvestorReverification")
    now = timezone.now()
    reviews = defaultdict(list)
    for review in (
        review_model.objects.filter(necessary=True)
        .exclude(status="closed")
        .order_by("created_at", "id")
    ):
        reviews[review.user_id].append(review)
    for group in reviews.values():
        if len(group) < 2:
            continue
        kept, others = group[0], group[1:]
        any_open = any(item.status == "open" for item in group)
        triggers = list(kept.triggers or [])
        events = list(kept.trigger_events or [])
        for other in others:
            triggers.extend(item for item in other.triggers or [] if item not in triggers)
            events.append(
                {
                    "type": "merged_by_migration",
                    "review_id": str(other.id),
                    "triggers": list(other.triggers or []),
                    "opened_reason": other.opened_reason,
                    "status": other.status,
                    "opened_at": other.created_at.isoformat(),
                    "at": now.isoformat(),
                }
            )
            other.status = "closed"
            other.closed_at = now
            other.outcome_note = (
                f"Merged into review {kept.id} by migration 0010 (one unresolved necessary "
                "review per investor)."
            )
            other.save(update_fields=["status", "closed_at", "outcome_note", "updated_at"])
        if any_open:
            kept.status = "open"
        kept.triggers = triggers
        kept.trigger_events = events
        kept.save(update_fields=["status", "triggers", "trigger_events", "updated_at"])
    current = defaultdict(list)
    for row in reverification_model.objects.filter(
        completed_at__isnull=True, replaced_at__isnull=True
    ).order_by("-created_at", "-id"):
        current[row.user_id].append(row)
    for group in current.values():
        for older in group[1:]:
            older.replaced_at = now
            older.save(update_fields=["replaced_at", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("kyc_compliance", "0009_recovery_identity_check"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="compliancereview",
            name="trigger_events",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(merge_duplicate_rows, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="compliancereview",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("necessary", True), models.Q(("status", "closed"), _negated=True)
                ),
                fields=("user",),
                name="kyc_one_unresolved_necessary_review",
            ),
        ),
        migrations.AddConstraint(
            model_name="investorreverification",
            constraint=models.UniqueConstraint(
                condition=models.Q(("completed_at__isnull", True), ("replaced_at__isnull", True)),
                fields=("user",),
                name="kyc_one_current_reverification",
            ),
        ),
    ]
