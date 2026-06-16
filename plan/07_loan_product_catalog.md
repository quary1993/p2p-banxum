# Loan Product Catalog and Configuration

Status: Draft. Updated with operating-model, payment, balance/FX, collateral/purpose, and marketplace decisions through 2026-05-20.

## Purpose

Define configurable loan products, terms, fees, eligibility rules, repayment structures, and marketplace presentation rules.

## Scope

- Loan product definitions.
- Borrower eligibility per product.
- Investor eligibility per product.
- Pricing parameters.
- Fees and commissions.
- Repayment types.
- Collateral and guarantee options.
- Listing rules.
- Funding rules.
- Early repayment and late payment policy.

## Product Model

The product model separates loan purpose from collateral/backing.

Launch focus:

- Mixed-purpose loan backed by real estate collateral.
- Mixed-purpose secured loan with configurable collateral.
- Exception loan with non-real-estate backing, if approved by admin policy.

Loan purpose examples:

- SME working capital loan.
- Liquidity loan.
- Refinancing.
- Acquisition financing.
- Project finance.
- Corporate project finance loan.
- Debt consolidation.
- Capex / business expansion.
- Inventory or trade finance.
- Bridge financing.
- Working capital for real estate or non-real-estate business.
- Other admin-defined purpose.

Collateral/backing examples:

- Real estate collateral.
- Guarantee.
- Invoice-backed.
- Asset-backed.
- Cash collateral.
- Securities/financial asset pledge.
- Equipment/machinery.
- Inventory.
- Receivables.
- Share pledge.
- Personal guarantee.
- Corporate guarantee.
- Mixed collateral.
- Unsecured exception.
- Other.

Shared product primitives must not assume that loan purpose determines collateral type, or that every future loan is real-estate backed.

## Decisions

### PROD-DEC-001: Loan Purpose Options

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta product / operations.

Decision:
Admin can select common loan purposes at launch, including working capital, liquidity, refinancing, acquisition financing, project finance, corporate project finance, debt consolidation, capex/business expansion, inventory or trade finance, bridge financing, and other/admin-defined purpose.

Rationale:
Loan purpose is descriptive and operational. It does not determine the collateral/backing flow.

Follow-ups:
Confirm exact labels for the admin picker and any investor-facing wording.

### PROD-DEC-002: Collateral/Backing Options

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta product / credit / operations.

Decision:
Admin can choose common collateral/backing types at launch. Real estate collateral is the default, but admin can select other collateral types. The first version does not change workflow by collateral type.

Collateral options should include real estate, guarantee, invoice-backed, asset-backed, cash collateral, securities/financial asset pledge, equipment/machinery, inventory, receivables, share pledge, personal guarantee, corporate guarantee, mixed collateral, unsecured exception, and other.

Rationale:
Garanta expects most loans to be real-estate backed, but the platform must support exceptions without creating separate workflows in the first version.

Follow-ups:
Confirm exact option labels and whether unsecured exception requires a reason code.

### PROD-DEC-003: V1 Collateral Data Fields

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta product / credit / operations.

Decision:
For all collateral types in v1, the platform captures only:

- Collateral/backing type.
- Collateral value.
- Optional free-text collateral description.

LTV is calculated by the platform from loan principal and collateral value.

No collateral-type-specific field set is required in the first version.

Rationale:
The first version should keep collateral capture simple and consistent across collateral types.

Follow-ups:
Consider richer real estate/property, guarantee, invoice, and asset collateral data models in later releases.

### PROD-DEC-004: Amount and Term Sanity Checks

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta product / operations.

Decision:
Admins define loan amounts and terms. The platform applies broad sanity checks rather than tight product limits. Launch examples: principal must not be less than 1,000 and must not exceed 1,000,000,000 in the loan currency. Term validations should follow the same approach: broad bounds to prevent obvious data-entry errors while preserving admin flexibility.

Rationale:
Admin-created loans need operational flexibility, but the system should prevent obviously invalid values.

Follow-ups:
Define exact minimum and maximum term values and whether amount sanity limits are currency-specific.

### PROD-DEC-005: Repayment Type Options

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta product / operations / finance.

Decision:
Launch repayment types are:

- Bullet principal with periodic interest.
- Amortizing principal and interest.
- Equal installment.
- Interest-only period then bullet.
- Interest-only period then amortizing.

Default is equal installments. The admin picker must include a short description for every repayment type. Custom/manual schedule is not a launch repayment type, but generated schedules may be materially changed through controlled payment or operational events under servicing controls.

Rationale:
Admins need flexibility to model negotiated loan terms, while defaulting to the most common/simple option and avoiding fully free-form repayment products in the first version.

Follow-ups:
Write final admin picker labels and descriptions. Define schedule override permissions, reason codes, and audit requirements in servicing.

### PROD-DEC-006: Interest Rate Source

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta product / operations.

Decision:
Interest rates are set by admin after offline negotiation. Rates are not automatically calculated from risk grade at launch.

Rationale:
Launch pricing is negotiated operationally and recorded in the platform.

Follow-ups:
Define whether multiple interest components are needed in a later version. Launch uses annual nominal interest with monthly installments by default under PROD-DEC-008.

### PROD-DEC-007: Product Configuration Ownership

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta product / technology.

Decision:
The most common product settings should be configurable by superadmin in the UI. Deeper parameters can be changed through deployment/configuration at first. The exact split will be finalized as the product model is implemented.

Rationale:
Superadmin needs practical control over usual product settings without exposing every low-level parameter in the first admin UI.

Follow-ups:
Define which settings are superadmin-editable for launch and which require deployment.

### PROD-DEC-008: Launch Interest, Schedule, Rounding, and Funding Deadline Defaults

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / operations / finance.

Decision:
Launch schedule and funding defaults are:

- Due/late/default day counts use calendar days.
- Interest is entered and displayed as an annual nominal interest rate.
- Monthly installments are the default installment frequency.
- Installment calculations round each installment line to the currency minor unit.
- The final installment absorbs rounding residue.
- Every loan has an admin-set funding deadline.
- Draft/admin planning records may carry a funding deadline up to 60 days.
- A loan cannot be published/opened to investors if the funding deadline is in the past or at/after the 30-day balance-investment cutoff. The launch publishable default is therefore 29 calendar days from the Europe/Zurich business date.

Rationale:
These defaults make schedule generation, arrears status, investor display, and funding-campaign monitoring deterministic for v1 while preserving admin planning flexibility inside a controlled range. The stricter publish-time cutoff prevents an admin from opening a balance-funded campaign whose deadline would make newly available investor balances fail the 30-day investment-window eligibility check at allocation time.

Follow-ups:
If Garanta later needs other day-count conventions, frequencies, or interest structures, add them as explicit product configuration with schedule golden tests.

### PROD-DEC-009: Project Recovery Waterfall Configuration

Status: Accepted.
Date: 2026-06-01.
Owner: Garanta product / operations / finance / legal.

Decision:
Each loan/project must support recovery waterfall configuration for default/recovery handling.

Launch configuration fields:

- Default/penalty interest percentage. This interest starts accruing from the official default declaration date instead of regular contractual interest. Launch interpretation is annual nominal percentage unless the project agreement defines another basis.
- Garanta recovery fee percentage, meaning Garanta's commission for handling recovery.
- Recovery fee base, defaulting to net recovered amount after declared third-party recovery/legal costs unless the project agreement defines another base.
- Recovery waterfall order/version. Unless overridden for a project, the default waterfall is external recovery/legal costs, platform-approved recovery costs including applied Garanta recovery fee, principal, contractual interest accrued until default, default/penalty interest, and other penalties/costs.

At recovery-payment recording time, admin declares third-party recovery costs and chooses whether to apply the configured Garanta recovery fee for that specific payment.

Rationale:
Recovery economics are negotiated/legal terms and may vary by project. The platform needs project-level configuration so recovery events can be calculated deterministically without hardcoding a single global policy.

Follow-ups:
Confirm final legal wording for project recovery fee and default/penalty interest disclosures in loan documentation.

## Product Configuration Fields

- Product name.
- Loan purpose category.
- Eligible borrower types.
- Eligible investor types.
- Allowed jurisdictions.
- Currency.
- Minimum and maximum principal.
- Minimum and maximum term.
- Interest rate type.
- Pricing/risk grade rules.
- Borrower success fee.
- Servicing fee.
- Investor fee.
- Late fee, future/inactive at launch.
- Default/penalty interest percentage for recovery/default period.
- Recovery fee percentage.
- Recovery fee base.
- Recovery waterfall order/version.
- Repayment type.
- Grace period rules.
- Collateral type.
- Collateral value.
- Calculated LTV, system-computed.
- Optional collateral free-text description.
- Minimum funding threshold.
- Maximum funding threshold.
- Funding deadline.
- Allocation method: first-come-first-served at launch.
- Disclosure template.
- Contract template set.

## Repayment Types

- Bullet principal with periodic interest: interest is paid periodically and principal is repaid at maturity.
- Amortizing principal and interest: scheduled payments reduce principal over time and include interest.
- Equal installment: each scheduled payment is the same amount unless adjusted by the loan schedule.
- Interest-only period then bullet: interest is paid during the term and principal is repaid at maturity.
- Interest-only period then amortizing: interest-only payments first, followed by amortizing payments.
- Custom/manual schedule: future repayment type; not available at launch. Admin may still trigger controlled event-driven schedule recalculations under servicing controls.

## Controls

- Product changes are versioned.
- Existing loans preserve the product version used at approval.
- Only approved products can be used for marketplace listings.
- Product changes require approval from authorized roles.
- Fee calculations are testable and auditable.
- Launch currencies are CHF and EUR, with enabled currencies configurable by superadmin and extendable to additional currencies.
- Each loan is single-currency.
- Currency exchange between enabled investor balance currencies is a platform/payment feature, not a loan-product feature.
- Borrower success fee is configurable in the 2% to 4% range and withheld from borrower disbursement after successful full funding or admin-approved partial close. It is stored for accounting/net-revenue reporting, has no investor/client website impact, and does not affect the borrower repayment schedule.
- `lender_payment_fee` should be configurable per lender installment distribution; launch value is 0.
- Default/penalty interest, recovery fee percentage, recovery fee base, and recovery waterfall order are project-level terms used only after default/recovery status.
- Product constraints are enforced in origination and investment flows.
- Default collateral/backing type is real estate collateral, but admin can choose other collateral types.
- V1 collateral capture is limited to collateral type, collateral value, and optional free-text collateral description for all collateral types.
- LTV is calculated by the platform from principal and collateral value.
- If collateral value is 0, the platform warns and does not show LTV. If collateral value is higher than principal, the platform warns and still shows LTV.
- Loan purpose must be configurable independently from collateral/backing type.
- Product configuration must support non-real-estate collateral and unsecured or differently secured loan types later without a schema redesign.
- Interest rate is set by admin based on offline negotiation.
- Amount and term fields use broad sanity checks rather than tight product limits.
- Primary-market minimum investment is 1,000 CHF/EUR at launch and configurable by superadmin.
- Primary-market maximum investment is the remaining amount/cap available on the loan.
- Every loan requires a funding deadline. Launch default is 30 days and the maximum allowed funding deadline is 60 days.
- Primary-market allocation method is first-come-first-served at launch; other allocation methods are future extensions.
- Custom/manual schedule is not a launch repayment type; generated schedules can be changed through controlled payment or operational events with audit trail.
- Common product settings should be configurable by superadmin; deeper parameters may require deployment/configuration.

## Dependencies

- Origination, Credit Review, and Underwriting.
- Marketplace, Investments, and Allocations.
- Loan Servicing and Repayments.
- Documents, Contracting, and E-Signature.
- Accounting, Tax, and Finance Operations.

## Q/A Backlog

1. Answered by Operating Model DEC-006: launch loans are mixed-purpose and usually real-estate backed; purpose and collateral/backing must be modeled separately.
2. Updated by PAY-DEC-001: CHF and EUR at launch, enabled currencies configurable by superadmin and extendable to more currencies.
2a. Answered by PAY-DEC-011: each loan is single-currency.
3. Answered by PROD-DEC-004: admins define amounts/terms with broad sanity checks, e.g. principal between 1,000 and 1,000,000,000 in loan currency; exact term sanity bounds still needed.
4. Answered by PROD-DEC-005: all listed repayment structures available; equal installments default; picker includes descriptions.
5. Answered by PROD-DEC-006: rates are set by admin after offline negotiation.
6. Answered by PAY-DEC-006: borrower success fee 2% to 4%, stored for accounting/net-revenue reporting after full funding or accepted partial close; configurable lender payment fee per installment, launch value 0.
7. Launch assumption: usually real-estate backed/secured, with exceptions possible; future products may be secured, unsecured, guaranteed, or mixed.
8. Answered by PAY-DEC-008/PAY-DEC-014: no fixed minimum funding threshold at launch; admin can proceed with a partial amount case by case and notify lenders.
9. Answered by PROD-DEC-007: common product settings in superadmin UI; deeper parameters may require deployment/configuration.
