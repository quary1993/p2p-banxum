# IP of Webby-Soft SRL. Audit S7-6: one unresolved necessary review and one current
# re-verification per investor; the review keeps the events that joined it (step 7, D4).

from django.conf import settings
from django.db import migrations, models


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
