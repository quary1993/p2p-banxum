# BANXUM Loan Originator CSV imports

These files are operator examples for importing an existing final-borrower loan
owned by a Loan Originator. They are not seed data and must not be edited into
production records without reconciling them to the originator's signed contract,
bank evidence, and servicing system.

## Files

- `originator_equal_installments.csv`
- `originator_bullet_periodic_interest.csv`
- `originator_amortizing_principal_interest.csv`
- `originator_interest_only_then_bullet.csv`
- `originator_interest_only_then_amortizing.csv`
- `originator_historical_prepayment.csv`

The historical-prepayment example shows how a payment made before BANXUM
publication is preserved while the future schedule is replaced by the
post-prepayment schedule.

## Encoding and units

- Encode the file as UTF-8 CSV with a comma delimiter.
- Dates use ISO `YYYY-MM-DD` and are interpreted as Europe/Zurich business dates.
- Every monetary field is an integer in the loan currency's minor units. For CHF
  and EUR, `105099` means `1,050.99`. Do not use decimal points, thousands
  separators, currency symbols, negative values, or formulas.
- Keep the header exactly as shown below, in this order. Unknown, missing,
  duplicated, or additional columns are rejected.
- Fields that do not apply to a row must be empty. A value in an unused field is
  rejected rather than silently ignored.

```csv
row_type,reference,installment_number,accrual_start_date,due_date,value_date,payment_type,opening_principal_minor,principal_minor,interest_minor,penalty_minor,fee_minor,total_minor,closing_principal_minor,resulting_principal_minor
```

## Schedule rows

Use `row_type=schedule` for every contractual installment, including historical
installments. Required fields are:

- `installment_number`: unique consecutive integer starting at 1.
- `accrual_start_date`: first date of the contractual accrual interval.
- `due_date`: due date, strictly after the accrual start and strictly increasing
  across installments.
- `opening_principal_minor`: principal before the installment.
- `fee_minor`: non-negative Garanta legal-cost/recovery-fee amount due in the
  first universal payment-waterfall tier. It is not the private originator
  premium fee and is not payable to investors or the originator.
- `penalty_minor`, `interest_minor`, `principal_minor`: non-negative amounts due
  in the remaining universal tiers, in that order.
- `total_minor`: exact sum of the four components.
- `closing_principal_minor`: opening principal less principal due.

Leave `reference`, `value_date`, `payment_type`, and
`resulting_principal_minor` empty on schedule rows.

The selected repayment type is checked against the principal pattern:

- `equal_installments` and `amortizing_principal_interest`: every contractual
  installment repays positive principal.
- `bullet_periodic_interest` and `interest_only_then_bullet`: all principal is
  repaid in the final installment only.
- `interest_only_then_amortizing`: principal is zero during the declared
  interest-only period and positive in every later installment.

BANXUM validates the imported cash-flow amounts; it does not silently regenerate
or "correct" an originator schedule.

## Payment rows

Use `row_type=payment` for every payment received on or before the import
`as_of_date`. Required fields are:

- `reference`: stable unique bank/servicing reference.
- `value_date`: bank value date, never after the import `as_of_date`.
- `payment_type`: `regular` or `repayment_in_advance`.
- `fee_minor`, `penalty_minor`, `interest_minor`, `principal_minor`: non-negative
  applied components in the universal waterfall order: Garanta legal
  costs/recovery fee, penalty, contractual interest, then principal.
- `total_minor`: positive and equal to the exact component sum.
- `resulting_principal_minor`: outstanding principal after this payment.

Leave `installment_number`, `accrual_start_date`, `due_date`,
`opening_principal_minor`, and `closing_principal_minor` empty on payment rows.

Payments are processed in value-date/reference order. Starting from the declared
original principal, every payment's principal must fit within the running
outstanding amount and its `resulting_principal_minor` must match exactly.
For each newly appended payment, BANXUM recomputes the due amount in every tier
from the immutable prior import and the current schedule. The imported split is
evidence, not allocation authority. The replacement import is rejected if it
pays principal while a higher tier remains due, or otherwise relabels cash to
bypass the universal order. A zero-due tier is skipped without changing that
order.

## Whole-file reconciliation

An import is accepted only when all of these are true:

- At least one schedule row exists.
- Imported payment references are unique.
- Original principal less all imported principal payments equals the computed
  current outstanding principal.
- If principal remains outstanding, at least one schedule row is due after the
  import `as_of_date`.
- Future scheduled principal sums exactly to the current outstanding principal.
- Future opening and closing principal form one continuous chain ending at zero.
- The final schedule due date is the legal maturity date.

The importer records the source CSV, SHA-256, source filename, validation
summary, imported amounts, admin actor, and immutable schedule/payment rows.

## Creating and revising a loan

1. Create or select the Loan Originator after completing off-platform KYB/AML.
2. Enter the loan's contractual terms, anonymized investor disclosure, target
   effective annual yield, minimum investment, and optional originator-fee
   override.
3. Set `as_of_date` to the date through which the CSV is complete and upload the
   full schedule plus every payment through that date.
4. Review current outstanding principal, maturity, unsold principal, coupon,
   target yield, and daily price before publishing.
5. Do not publish if the loan is repaid, impaired, on hold, or has 30 or fewer
   calendar days to maturity.

After publication, a borrower repayment is recorded with a replacement CSV. The
replacement must preserve every previously imported payment exactly, append
exactly the declared new payment reference/value date/components, and reconcile
the new future schedule to the resulting principal. A repayment creates a new
immutable revision; it does not rewrite historical import evidence.

## Operational warning

Do not edit a published opportunity merely to make a CSV pass. A discrepancy is
an originator reconciliation exception. Put the opportunity on hold, compare the
contract, originator servicing export, and bank evidence, then upload a corrected
revision with an auditable explanation.
