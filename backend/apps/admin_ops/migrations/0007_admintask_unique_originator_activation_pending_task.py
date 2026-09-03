from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("admin_ops", "0006_admintask_unique_loan_funding_close_failure_task"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="admintask",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("related_object_type", "OriginatorSubscriptionActivationPending"),
                    ("task_type", "loan_setup"),
                ),
                fields=("task_type", "related_object_type", "related_object_id"),
                name="unique_originator_activation_pending_task",
            ),
        ),
    ]
