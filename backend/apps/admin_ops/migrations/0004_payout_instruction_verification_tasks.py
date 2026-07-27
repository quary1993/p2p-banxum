from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("admin_ops", "0003_unique_reconciliation_snapshot_admin_task")]

    operations = [
        migrations.AlterField(
            model_name="admintask",
            name="task_type",
            field=models.CharField(
                choices=[
                    ("kyc_manual_review", "KYC manual review"),
                    ("account_access_review", "Account access review"),
                    ("borrower_onboarding", "Borrower onboarding"),
                    ("loan_setup", "Loan setup"),
                    ("payment_reconciliation", "Payment reconciliation"),
                    ("payout_instruction_verification", "Payout instruction verification"),
                    ("fx_settlement", "FX settlement"),
                    ("document_review", "Document review"),
                    ("email_delivery_failure", "Email delivery failure"),
                    ("reporting", "Reporting"),
                    ("support", "Support"),
                    ("other", "Other"),
                ],
                max_length=64,
            ),
        ),
        migrations.AddConstraint(
            model_name="admintask",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    related_object_type="InvestorPayoutInstruction",
                    task_type="payout_instruction_verification",
                ),
                fields=("task_type", "related_object_type", "related_object_id"),
                name="unique_payout_instruction_verification_task",
            ),
        ),
    ]
