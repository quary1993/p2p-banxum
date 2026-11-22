# IP of Webby-Soft SRL. Audit step 5 (D7): Garanta's part of penalty X on its own ledger account.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0017_engine_servicing_18_6"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ledgeraccount",
            name="account_type",
            field=models.CharField(
                choices=[
                    ("collection_cash", "Collection cash"),
                    ("investor_balance_liability", "Investor balance liability"),
                    ("garanta_accrued_revenue", "Garanta accrued revenue"),
                    ("suspense_unmatched_cash", "Suspense/unmatched cash"),
                    ("withdrawal_payable", "Withdrawal payable"),
                    ("refund_payable", "Refund payable"),
                    ("loan_funding_escrow", "Loan funding escrow"),
                    ("borrower_disbursement_payable", "Borrower disbursement payable"),
                    ("platform_fee_revenue", "Platform fee revenue"),
                    ("fx_clearing", "FX clearing"),
                    ("fx_fee_revenue", "FX fee revenue"),
                    ("fx_gain_loss", "FX gain/loss"),
                    ("recovery_distribution_payable", "Recovery distribution payable"),
                    (
                        "originator_settlement_payable",
                        "Loan Originator settlement payable",
                    ),
                    (
                        "originator_servicing_payable",
                        "Loan Originator servicing payable",
                    ),
                    (
                        "undistributed_fractions",
                        "Undistributed investor cent fractions",
                    ),
                    (
                        "garanta_recovery_receivable",
                        "Garanta recovery expenses repaid by the borrower",
                    ),
                    ("garanta_penalty_income", "Garanta part of penalty X"),
                ],
                max_length=64,
            ),
        ),
    ]
