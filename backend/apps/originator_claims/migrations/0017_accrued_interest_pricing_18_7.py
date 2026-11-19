# IP of Webby-Soft SRL. 18.7: price rule, day-count convention and price reference of offers.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("originator_claims", "0016_originator_about"),
    ]

    operations = [
        migrations.AddField(
            model_name="originatorloanprofile",
            name="interest_convention",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="originatorloanprofile",
            name="price_accrual_start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="originatorloanprofile",
            name="price_next_due_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="originatorloanprofile",
            name="price_reference_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="originatorloanprofile",
            name="pricing_rule",
            field=models.CharField(
                choices=[
                    ("boundary_installment", "Boundary installment (before 18.7)"),
                    ("accrued_interest", "Principal plus accrued interest (18.7)"),
                ],
                default="boundary_installment",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="originatorclaimevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("originator_created", "Originator created"),
                    ("originator_updated", "Originator updated"),
                    ("import_validated", "Import validated"),
                    ("loan_created", "Loan created"),
                    ("opportunity_published", "Opportunity published"),
                    ("opportunity_closed", "Opportunity closed"),
                    ("opportunity_held", "Opportunity held"),
                    ("opportunity_resumed", "Opportunity resumed"),
                    ("funding_round_closed", "Funding round closed"),
                    ("funding_round_close_failed", "Funding round close failed"),
                    (
                        "subscription_activation_overdue",
                        "Subscription activation overdue",
                    ),
                    ("subscription_activated", "Subscription activated"),
                    ("subscription_cancelled", "Subscription cancelled"),
                    ("quote_created", "Quote created"),
                    ("claim_purchased", "Claim purchased"),
                    ("repayment_recorded", "Repayment recorded"),
                    ("servicing_status_changed", "Servicing status changed"),
                    ("settlement_recorded", "Settlement recorded"),
                    (
                        "offer_failed",
                        "Offer failed (payment or due date before settlement)",
                    ),
                ],
                max_length=64,
            ),
        ),
    ]
