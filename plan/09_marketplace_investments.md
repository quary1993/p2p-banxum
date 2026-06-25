# Marketplace, Investments, and Allocations

Status: Draft. Updated with operating-model, identity, balance, FX, marketplace, secondary-market bulletin-board transfer, recovery, and document decisions on 2026-05-29.

## Purpose

Define how approved loans are listed, discovered, funded, allocated, closed, and converted into contractual investor exposure.

## Scope

- Loan listing publication.
- Marketplace visibility rules.
- Investor eligibility checks.
- Investment order creation.
- Allocation and oversubscription.
- Funding thresholds and deadlines.
- Order final closure and expiry.
- Loan closing.
- Investor confirmations.
- Secondary-market transfers.

## Decisions

### MKT-DEC-001: Primary Allocation Method

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta product / operations.

Decision:
Primary-market allocation is first-come-first-served.

A pending order has no effect on the loan cap until sufficient investor balance is reserved/allocated or received funds are validated. The ordering basis is the balance allocation timestamp or the bank value date of received funds where external deposit timing is relevant.

Rationale:
This keeps allocation simple while supporting both investor balances and manually confirmed external deposits.

Follow-ups:
Define tie-break behavior when multiple payments share the same bank value date.

### MKT-DEC-002: Marketplace Visibility Before Login and Registration-Time KYC

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta product / compliance.

Decision:
Unauthenticated visitors may see a preview of marketplace listings. Full marketplace/dashboard access requires registration-time terms acceptance and KYC/AML approval.

Public preview fields before login:

- Borrower.
- Amount.
- Interest.
- Period.
- Loan type.
- Status.
- Borrower country.
- Loan currency.

Rationale:
This allows investors to evaluate opportunities early while keeping full loan data, balances, deposits, FX, and investment functionality behind onboarding controls.

Follow-ups:
Confirm final labels and whether public preview should remain available in all launch jurisdictions.

### MKT-DEC-003: Investor Commitment Point

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta product / legal / operations.

Decision:
The investor becomes committed when investor balance is allocated/reserved to the order or external funds are received and matched/validated by admin, provided the loan target is met or Garanta decides to proceed with an admin-approved partial amount. If the loan does not proceed, funds are returned, released back to investor balance, or otherwise handled under the balance ageing policy.

Pending orders are intents until sufficient balance is allocated/reserved or external funds are validated. They do not affect the loan funding amount and do not create a valid funded order until allocation/validation occurs.

Rationale:
The commitment model follows actual balance allocation or validated settlement rather than simple order submission.

Follow-ups:
Legal wording should define the exact moment of contractual effectiveness and how it relates to assignment documentation at closing.

### MKT-DEC-004: No Investor Cancellation

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta product / legal / operations.

Decision:
Investors cannot cancel investment orders. A pending order has no effect until sufficient balance is allocated/reserved or admin validates received funds. Pending orders remain open until the loan funding target is reached, the campaign is closed, or the order is otherwise closed by platform rules.

To prevent spam, each investor may have a limited number of pending orders. Launch assumption: 50 pending orders per investor.

Rationale:
Because pending orders do not reserve capacity until balance/funds are allocated, cancellation is not required for funding control. A pending-order cap prevents abuse and operational clutter.

Follow-ups:
Confirm whether the 50 pending-order cap is global, per currency, or per loan.

### MKT-DEC-005: Oversubscription Handling

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta product / finance / operations.

Decision:
When a received lender payment would exceed the remaining loan cap, the system informs admin that the amount surpasses the cap and calculates:

- The portion that can be registered to the valid open order.
- The excess amount that should be returned.

If the full payment exceeds the remaining cap because no capacity remains, the order is automatically closed in a final non-invested status and admin is alerted to return the full amount.

Rationale:
This preserves first-come-first-served allocation while ensuring surplus funds are not silently retained or allocated incorrectly.

Follow-ups:
Define exact final status labels, refund/balance-credit reason codes, and whether admin can override partial allocation in exceptional cases.

### MKT-DEC-006: Secondary Market Availability

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta product / operations / legal.

Decision:
The secondary market is available at launch.

Rationale:
Secondary-market support is part of the expected platform experience and should be designed into launch workflows, settlement, documents, and investor portal actions.

Follow-ups:
Confirm launch restrictions by jurisdiction if needed. V1 does not enforce hard investor-class segmentation.

### MKT-DEC-007: Secondary Market Seller Pricing

Status: Accepted.
Date: 2026-05-16. Updated 2026-05-29.
Owner: Garanta product / operations / legal.

Decision:
Secondary-market sellers can set their own sale price for the full holding being transferred. The sale price may be at a discount or premium to the current principal balance of that holding.

The sale price is defined as a percentage of current principal balance. The platform must clearly display the discount or premium compared with current principal balance.

Accrued interest up to the settlement date is calculated separately, daily, pro rata, and belongs to the seller up to the transfer date if the loan/project is current/performing. Future interest after settlement belongs to the buyer.

Future interest is not included in the transfer price and belongs to the buyer after settlement.

Rationale:
Seller-defined discount/premium pricing supports flexible exits while the separate accrued-interest calculation makes the economics clear between seller and buyer.

Follow-ups:
Finalize legal display wording for discount/premium and accrued-interest disclosure.

### MKT-DEC-008: Legal-Entity Lender Offline Investments

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta product / operations.

Decision:
Legal-entity lenders are registered/onboarded offline and created by admin. When Garanta creates and KYB/AML-approves legal-entity lender accounts, they behave like regular lender accounts for balances, primary-market investing, secondary-market activity, FX, withdrawals, ageing, reminders, and penalties. Their KYC/KYB/AML is admin-recorded off-platform rather than completed through Didit.

Admin must also be able to manually add investments in loans from the lender database in the admin interface where Garanta operates a legal-entity lender without self-service action.

Rationale:
Legal-entity lender onboarding/KYC/AML remains off-platform, while the platform should treat approved legal-entity lender accounts consistently in financial ledger, balances, servicing, payment, and reporting records.

Follow-ups:
Define admin fields, evidence requirements, whether the single legal-entity representative login is enabled case by case or by default, and when manually added legal-entity lender investments use the same order/payment status model as self-service orders.

### MKT-DEC-009: Non-Performing and Non-Standard Loans on Secondary Market

Status: Accepted.
Date: 2026-05-16. Updated 2026-05-29.
Owner: Garanta product / operations / legal.

Decision:
Defaulted loans are not offered to investors on the primary market. If a loan becomes late or defaulted after it is active, lenders continue to see it in their portfolio and may seek to list their holdings on the secondary market through the non-standard listing workflow.

Only holdings related to current/performing loans/projects may be listed automatically on the secondary market.

If the loan/project is late, overdue, restructured, under observation, in default, in recovery, under legal enforcement, subject to a payment incident, or has any other status different from normal performing status, the seller may only submit a listing request. The listing becomes visible on the secondary market only after explicit Garanta admin approval.

Admin approval must be saved in the audit log with approval date, approving admin, reason, and disclosure note. Garanta may reject or remove any such listing at its discretion.

For approved non-standard listings, the buyer must see a clear warning and confirm an additional risk acknowledgement before purchase. The listing page must display loan status, days past due if applicable, recovery/default status, last payment date, and any public admin note.

Rationale:
Primary-market listings should only include eligible live opportunities, while secondary-market transfers for impaired or non-standard holdings require admin review, explicit disclosure, and additional buyer acknowledgement.

Follow-ups:
Define exact status disclosure wording, buyer acknowledgement text, and standard admin disclosure-note templates.

### MKT-DEC-010: Balance-Funded Primary and Secondary Market Activity

Status: Accepted.
Date: 2026-05-20.
Owner: Garanta product / finance / operations.

Decision:
Primary-market investments and secondary-market purchases can be funded from investor balances. Investors may deposit funds into balances before investing, receive repayments into balances, receive secondary-market seller proceeds into balances, and use balances for reinvestment, withdrawal, or currency exchange.

Rationale:
The product model now includes multi-currency investor balances rather than only transaction-specific external transfers.

Follow-ups:
Define exact balance reservation/debit timing, ordering timestamp, partial allocation handling, insufficient-balance handling, and ageing treatment for released or unallocated funds.

### MKT-DEC-011: Primary-Market Investment Limits

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / operations / superadmin.

Decision:
Launch minimum primary-market investment amount is:

- 1,000 CHF.
- 1,000 EUR.

The minimum investment amount is configurable by superadmin.

The maximum investment amount is the maximum remaining amount/cap available on the loan. There is no separate per-investor hard maximum at launch beyond available eligible balance, remaining loan capacity, eligibility, and compliance rules.

Rationale:
This keeps launch investment limits simple and aligned with the loan capacity model.

### MKT-DEC-012: Borrower Opportunity Source

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta operations.

Decision:
Borrower/loan opportunities are entered directly by Garanta admins in v1.

Brokers, introducers, or third-party submitter workflows are not supported in v1.

Rationale:
Borrower onboarding and loan origination are offline/admin-operated at launch.

### MKT-DEC-013: Launch Listing Visibility

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / compliance.

Decision:
Private, invitation-only, or segmented marketplace listings are not supported in v1.

Published listings are visible to all eligible investors, subject to the public preview/authenticated full-data rules, jurisdiction/compliance restrictions, and investor eligibility checks.

Rationale:
All-eligible-investor visibility keeps launch marketplace behavior simple.

### MKT-DEC-014: Published Listing Edits

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta operations / product / legal.

Decision:
Before a loan has committed investments, admin may edit any listing/loan field subject to mandatory-field validation and audit logging.

After a loan has committed investments, admin may only reduce the total loan amount. Admin cannot increase the total loan amount after committed investments exist.

When admin lowers the total amount after committed investments exist, the system requires admin to write a custom investor message explaining the change and reason. Affected investors are notified. Re-acceptance is not required at launch.

Rationale:
Before commitments, the listing remains operationally editable. After investor commitment, investor economics and disclosure stability matter; only lowering the target amount is allowed, with notification and reason capture.

### MKT-DEC-015: Generic Investor Confirmations

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / legal.

Decision:
Primary-market investment, secondary-market purchase, and secondary-market listing confirmations remain generic checkbox/clickwrap acceptance flows at this planning stage.

The exact checkbox labels and acknowledgements are deferred to legal/template drafting and tracked in Admin TODO.

Rationale:
The platform should support the required acceptance mechanics now, while final legal wording remains a legal/compliance deliverable.

### MKT-DEC-016: Secondary-Market Direct Purchase Matching

Status: Accepted.
Date: 2026-05-22. Updated 2026-05-29.
Owner: Garanta product / operations.

Decision:
Secondary-market v1 uses direct buyer acceptance of a listed price.

No admin approval or mediation is required for a current/performing holding that passes automatic listing checks. The sale should execute immediately after buyer eligibility checks, sufficient eligible balance/funds, required checkbox/clickwrap document acceptance, fee calculation, and system validation pass.

For non-standard holdings under MKT-DEC-009, admin approval is required before the listing becomes visible. Once approved and visible, the buyer can purchase directly after eligibility, balance/funds, required additional risk acknowledgement, document acceptance, fee calculation, and system validation pass.

Required documents are accepted by checkbox/clickwrap and made available for on-demand generation/download according to the document module. Legal terms and transaction-agreement PDFs are not emailed by default.

Rationale:
Direct acceptance keeps the bulletin-board secondary market simple and usable while admin approval gates non-performing or otherwise non-standard listings before buyer purchase.

### MKT-DEC-017: Secondary-Market Fees

Status: Accepted.
Date: 2026-05-22. Updated 2026-05-29.
Owner: Garanta product / finance / operations.

Decision:
Launch secondary-market fees are:

- Maker/seller fee: 0.25%.
- Taker/buyer fee: 0.75%.

Both fees are charged at settlement. The maker fee is charged to the seller side and deducted from seller proceeds. The taker fee is charged to the buyer side as part of the settlement amount/cost.

Maker/seller and taker/buyer fees are calculated on the agreed transfer price, excluding accrued interest. Fees are rounded to the nearest cent/minor currency unit using standard half-up rounding. Minimum fee support is configurable; launch may use no minimum fee unless Garanta configures one.

Settlement formulas:

- Seller fee = transfer price x maker/seller fee rate, rounded half-up, subject to any configured minimum fee.
- Buyer fee = transfer price x taker/buyer fee rate, rounded half-up, subject to any configured minimum fee.
- Seller net proceeds = transfer price + accrued interest - seller fee.
- Buyer total cost = transfer price + accrued interest + buyer fee.

The interface must clearly display:

- Current principal balance of the transferred holding.
- Sale price.
- Discount or premium.
- Accrued interest.
- Seller/maker fee.
- Seller net proceeds.
- Buyer/taker fee.
- Buyer total cost.

Rationale:
Charging both sides at settlement keeps secondary-market economics explicit and aligns fee recognition with the completed transfer.

Follow-ups:
Finalize legal display wording and any non-zero minimum fee configuration.

### MKT-DEC-018: Risk Acknowledgements and Exposure Metrics Instead of Hard Concentration Limits

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / compliance / operations.

Decision:
V1 uses generic P2P lending risk acknowledgements and transaction-specific document acceptance rather than a detailed investor suitability questionnaire.

The platform does not enforce hard concentration limits at launch. It should calculate and display/report exposure metrics, such as exposure by loan, borrower, country, sector, collateral type, risk rating, maturity, and defaulted loan where available.

Rationale:
Generic acknowledgements and exposure transparency are enough for the first version while Garanta finalizes legal/compliance policy. Hard concentration controls can be added later if required.

Follow-ups:
Garanta must create and upload the final legally approved risk acknowledgement/risk disclosure document before production use.

### MKT-DEC-019: Funding Deadline and Partial Funding Principal

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / finance / operations.

Decision:
Every primary-market loan has an admin-set funding deadline. Draft/admin planning records may carry a funding deadline up to 60 days. A loan cannot be published/opened to investors if the funding deadline is in the past or more than 29 calendar days from the Europe/Zurich business date; the launch publishable default is therefore 29 calendar days from that business date.

If admin accepts a partially funded loan, the accepted funded amount becomes the final loan principal. The repayment schedule is generated or regenerated from that accepted funded principal. The borrower success fee applies to the accepted funded principal, and the borrower repays the accepted funded principal plus agreed interest.

Rationale:
This keeps partial funding economically clear and avoids borrower schedules based on unfunded amounts.
The publication cutoff keeps open campaigns compatible with the investor-balance ageing model: an investor may pledge a balance source entry only while that entry is inside its 30-day investment/reinvestment window, and the loan campaign itself may remain open for up to 29 days. This prevents Garanta from holding uninvested client money past the 60-day operating limit without treating the loan funding deadline as part of the source entry's day-30 pledge eligibility.

Follow-ups:
Final legal terms must disclose the partial-funding treatment and investor notification rule.

### MKT-DEC-020: Secondary-Market Bulletin Board and Full-Holding Transfers

Status: Accepted.
Date: 2026-05-29.
Owner: Garanta product / operations / legal.

Decision:
Garanta's secondary market must operate as a claim/participation transfer mechanism between users, structured as a bulletin board and not as a regulated trading venue.

The seller may list only an entire holding, not a fraction of a holding. If a lender has multiple separate holdings in the same project from different investments or allocations, each holding may be listed separately, but each listing must transfer that holding in full.

Splitting, partial sales, and partial transfers of a single holding are not allowed.

A current/performing holding may be listed immediately after purchase or assignment. There is no minimum holding period. No separate minimum secondary-market transfer size applies; the listed holding only needs a positive current principal balance.

Each completed secondary-market transfer must generate legal transfer evidence and accounting entries for any Garanta secondary-market fees.

Rationale:
Full-holding transfers keep the legal assignment chain, servicing ownership, lender distributions, and accounting entries simpler while preserving secondary liquidity through listing each separate holding.

## Marketplace Lifecycle

1. Listing prepared by operations after a complete loan record exists.
2. Listing reviewed by operations, compliance, or credit where policy requires.
3. Listing published.
4. Unauthenticated visitors browse preview listing data.
5. KYC-approved logged-in users browse full loan data.
6. Eligible investors place pending orders.
7. Investor allocates available balance or receives deposit instructions if more funds are needed.
8. Funding progress updates only from allocated balance or admin-validated received funds.
9. Loan reaches full funding, an admin-approved partial close, or expires.
10. Oversubscription handling runs if needed.
11. Final closing approvals complete.
12. Contracts become effective.
13. Funds are released according to the payments module.
14. Per-order assignment documents are generated from the template/data snapshot and made available to investors.

## Primary Investment Lifecycle

1. Investor creates a pending order for a specific loan and amount.
2. Pending order counts toward the investor pending-order cap but does not reserve loan capacity until balance/funds are allocated.
3. Investor accepts primary-market investment terms/contracts by checkbox/clickwrap.
4. Investor funds the order from available same-currency balance or deposits funds to the relevant currency collection account.
5. Admin matches and validates received external funds where applicable.
6. Allocated balance or validated funds are allocated first-come-first-served against remaining loan capacity.
7. If capacity remains, the order becomes a funded/validated order for the accepted amount.
8. If only part of the payment fits within remaining capacity, the order is accepted for the fitting portion and the excess is marked refund due.
9. If no capacity remains, the order is closed in a final non-invested status and the full received amount is marked refund due.
10. If the campaign does not proceed, validated/allocated funds are released back to investor balance or withdrawn/refunded according to policy and balance ageing rules.

## Legal Instrument

Based on Operating Model DEC-005, investor exposure is structured as a pro-rata assignment of receivables or loan claims.

Launch requirements:

- Marketplace terminology should describe investments as loan claim exposure or assigned receivables, not notes, bonds, fund units, deposits, or managed portfolio products.
- Allocation must determine each lender's pro-rata share of the funded loan claim.
- Closing must generate or reference the legal assignment documentation for each lender.
- In v1, the claim assignment document is generated per investment order.
- Servicing, repayments, late payments, defaults, and recoveries must preserve each lender's pro-rata economics unless the contract says otherwise.
- Secondary sale or reassignment rights are in scope, subject to the secondary market design.

## Secondary Market

Based on Operating Model DEC-008, the platform will support a secondary market.

Launch requirements:

- Secondary market is a bulletin-board claim/participation transfer mechanism, not a regulated trading venue.
- Secondary market is available at launch.
- Only an entire holding may be listed. A single holding cannot be split, partially sold, or partially transferred.
- Multiple separate holdings in the same project may each be listed separately, but each listing transfers the selected holding in full.
- Listed holdings must have a positive current principal balance.
- No minimum holding period applies for current/performing holdings.
- No separate secondary-market minimum transfer size applies.
- Sellers define the sale price as a percentage of current principal balance and may offer a discount or premium.
- The platform displays current principal balance, sale price, discount/premium, accrued interest, seller fee, seller net proceeds, buyer fee, and buyer total cost.
- Accrued interest up to settlement is calculated separately, daily, pro rata, and belongs to the seller up to transfer date for current/performing loans/projects.
- Future interest after settlement belongs to the buyer.
- Maker/taker fees are calculated on transfer price excluding accrued interest, rounded half-up to the nearest cent/minor unit, with configurable minimum-fee support.
- Current/performing holdings may be listed automatically after system checks.
- Late, overdue, restructured, under-observation, default, recovery, legal-enforcement, payment-incident, or otherwise non-performing/non-standard holdings require an admin-approved listing request before becoming visible.
- Approved non-standard listings require buyer warning and additional risk acknowledgement before purchase.
- Buyer eligibility checks before purchase or transfer.
- Secondary-market assignment or reassignment documentation generated for each secondary-market purchase.
- Secondary-market seller/listing terms accepted when a seller lists a holding.
- Settlement through Garanta's collection account or investor balances under PAY-DEC-009, with maker/taker fees deducted before net proceeds are credited to the seller balance.
- Launch secondary-market fees are 0.25% maker/seller fee and 0.75% taker/buyer fee, both charged at settlement.
- Settlement should normally be much faster than 60 days from buyer-fund receipt or balance reservation and must not exceed the 60-day maximum operational period.
- Servicing record update after transfer.
- Disclosure of late, default, operational loan change, recovery, impairment, or non-standard listing status.
- Transfer restrictions by jurisdiction if enabled.

## Listing Data

- Loan ID.
- Product type.
- Loan purpose.
- Collateral/backing type.
- Collateral value, if investor-facing disclosure policy permits.
- Calculated LTV when collateral value is non-zero and LTV is displayable.
- Collateral description, if investor-facing disclosure policy permits.
- Borrower/entity disclosure data.
- Requested amount.
- Minimum close amount.
- Amount available.
- Currency.
- Term.
- Repayment schedule.
- Interest rate/return.
- Risk grade.
- Collateral/guarantee summary.
- Fees.
- Key documents.
- Funding deadline.
- Investor eligibility restrictions.
- Risk warnings.

Optional borrower financial fields must be omitted from the marketplace listing when admin has not declared them.

## Investment Order States

- Pending: investor has initiated the order, but no balance/funds have been allocated.
- Payment received pending validation: funds appear to have arrived and await admin matching/validation.
- Balance allocated pending validation: investor balance has been reserved/debited for the order and awaits final allocation/validation.
- Funded/validated: admin has matched received funds or allocated investor balance and the order counts toward loan funding.
- Partially funded/validated: part of the received amount fits within remaining loan capacity and the excess is refund due.
- Excess refund or balance release due: surplus amount must be returned, credited, or released to investor balance according to policy.
- Fully excess/refund or balance release due: no amount fits within remaining loan capacity; the order is closed in a final non-invested status and the full amount must be returned, credited, or released to investor balance according to policy.
- Closed invested: the order forms part of the funded loan after full or partial loan close.
- Closed not invested: the order has no investment effect because the campaign did not proceed, no capacity remained, or the platform closed it under rules.
- Refunded/balance released: funds have been returned or released back to investor balance.
- Expired/closed unfunded: pending order closed because the loan reached target, campaign closed, or platform rules closed it.

## Allocation Methods

Launch method:

- First-come-first-served.

Later methods may include pro-rata at close, manual allocation, priority tiers, auction-based pricing, and auto-invest allocation, but they are out of launch scope.

## Balance and Funding Account Model

Launch uses one segregated collection account/IBAN per enabled currency. Investors may deposit into investor balances and use those balances for primary-market investments, secondary-market purchases, withdrawals, and currency exchange.

Each loan is single-currency. Cross-currency transfers are not advised, but Garanta does not block them from the platform side if the correct amount arrives in the correct collection account with the correct client/payment identifier.

If a loan does not reach full funding by the funding deadline or approaches the 60-day holding limit, admin decides whether to release funds back to investor balances/withdraw funds or proceed with a partial funding amount. If the loan proceeds partially funded, lenders must be notified. Lender reconfirmation is not required because partial funding consent will be included in the initial terms of service.

Investor balance entries are subject to the 30-day investment/reinvestment and 60-day withdrawal/holding rules defined in the payments module.

## Controls

- Investor must be eligible at order time and closing time.
- Investor class may be retail, professional, or institutional, with product eligibility and disclosure rules applied per class.
- V1 does not implement a hard suitability questionnaire or hard concentration limits. Generic risk acknowledgements and exposure metrics are used at launch.
- Natural-person lender KYC/AML must be valid before full marketplace/dashboard, deposit, balance, FX, or investment access.
- Legal-entity lender KYB/AML must be approved before manual/admin-entered investments, balance use, FX, withdrawals, or secondary-market activity.
- Borrower KYB/AML must be approved before loan publication, funding close, disbursement, repayment processing, or other platform transaction activity involving the entity.
- KYC-approved logged-in users may see full loan data; unauthenticated users see only preview listing data.
- Investor acknowledgements must be current.
- Pending orders do not reserve loan capacity and do not affect the funding progress amount until balance/funds are allocated.
- Each investor may have up to 50 pending orders at launch, subject to final configuration.
- Balance-funded orders may use only eligible balance source entries that are still inside the 30-day investment/reinvestment window at allocation/pledge time.
- The platform does not require the loan funding deadline to fall before the consumed source entry's 30-day investment deadline. The source entry only has to be pledged before day 30; the loan's own maximum funding period is capped separately so allocated cash remains inside the 60-day operating limit.
- If available aggregate balance includes source entries older than 30 days, the platform must show an explicit error and a per-currency breakdown of investable versus withdraw-only balance.
- Amount limits are enforced. Exposure metrics and concentration warnings are shown/reported, but hard concentration limits are not enforced at launch.
- First-come-first-served allocation is based on bank value date of validated received funds or balance reservation/allocation timestamp for balance-funded orders.
- Orders cannot exceed available amount after validation/allocation; excess funds are returned, credited, or released to balance according to policy.
- Investors cannot cancel orders.
- Before committed investments exist, admin may edit all listing fields subject to validation/audit. After committed investments exist, admin may only lower total loan amount, must enter a custom investor message and reason, and investor notification is enough.
- Closing requires operational, compliance, credit, and payment readiness checks.
- Closing must respect the maximum 60-day project settlement holding period defined by the operating model.
- Closing can proceed at a partial funding amount after admin approval and lender notification.
- If a loan closes partially funded, the accepted funded amount becomes the final loan principal and the schedule is based on that amount.
- Listing publication is blocked by missing mandatory structured loan information, including collateral type, collateral value, interest rate, repayment schedule, or mandatory borrower fields.
- Secondary-market buyers must pass eligibility checks and accept required disclosures before transfer.
- Secondary-market buyer acceptance of a current/performing listed price can settle directly without admin approval when eligibility, balance/funding, document acceptance, fee, and validation checks pass.
- Secondary-market non-standard listing requests require admin approval before publication if the related loan/project is not normal performing, including late, overdue, restructured, under observation, default, recovery, legal enforcement, payment incident, or any other non-performing/non-standard status.
- Non-standard listing approval is audit logged with approval date, approving admin, reason, and disclosure note.
- Garanta may reject or remove non-standard listings at its discretion.
- Buyers of approved non-standard listings must see a clear warning and accept an additional risk acknowledgement before purchase.
- Non-standard listing pages show loan status, days past due if applicable, recovery/default status, last payment date, and any public admin note.
- Secondary-market settlement charges 0.25% maker/seller fee to seller proceeds and 0.75% taker/buyer fee to the buyer side.
- Secondary-market fees are calculated on the agreed transfer price excluding accrued interest and rounded half-up to the nearest cent/minor currency unit. Minimum fee support is configurable.
- Secondary-market sellers must accept seller/listing terms before publishing a listing.
- Secondary-market sellers can set their own discount or premium price as a percentage of current principal balance.
- Secondary-market sellers may list only entire holdings. Partial sales or partial transfers of one holding are not allowed.
- Accrued interest up to settlement belongs to the seller; future interest after settlement belongs to the buyer.
- The interface displays current principal balance, sale price, discount/premium, accrued interest, seller fee, seller net proceeds, buyer fee, and buyer total cost.
- Secondary-market transfers must preserve the assigned-claim legal structure and servicing audit trail.
- Primary investment and secondary-market purchase documents are accepted by checkbox/clickwrap in v1.
- Primary investment assignment documents are generated per investment order.
- Secondary-market reassignment documents are generated per secondary-market purchase.
- Legal-entity lender accounts are admin-created after off-platform onboarding and behave like regular lender accounts for balances/transactions once KYB/AML-approved and active.
- Legal-entity lender investments can also be entered manually by admin from the lender database where needed.
- All order and allocation decisions are auditable.

## Dependencies

- Investor Portal.
- Loan Product Catalog and Configuration.
- Payments, Ledger, Custody, and Reconciliation.
- Documents, Contracting, and E-Signature.
- Communications and Notifications.

## Q/A Backlog

1. Updated by MKT-DEC-001/MKT-DEC-010: primary allocation is first-come-first-served based on balance reservation/allocation timestamp or bank value date of validated external funds.
2. Updated by MKT-DEC-003/MKT-DEC-010: pending orders are intents only; commitment follows balance allocation or matched/validated external funds and a full or admin-approved partial close.
3. Answered by PAY-DEC-008: admin decides refund all or proceed with partial funding and notify lenders.
4. Answered by MKT-DEC-005: accepted portion is allocated and excess returned; if no capacity remains, order closes final non-invested and full refund is due.
5. Answered by MKT-DEC-013: v1 has no private, invitation-only, or segmented listings; published listings are visible to all eligible investors.
6. Answered by MKT-DEC-014: before committed investments, all fields can be edited; after committed investments, only total amount can be lowered with a custom investor message/reason and notification.
7. Answered by MKT-DEC-015: keep generic checkbox/clickwrap confirmations for now; exact labels/acknowledgements are legal/template TODOs.
8. Answered by MKT-DEC-003: investor commitment is tied to sent/validated funds and successful full or admin-approved partial close; exact legal wording remains open.
9. Answered by launch scope/admin TODO: auto-invest is future scope and not included at launch.
10. Partly answered by DOC-DEC-005: assignment documentation is generated per investment order in v1; exact legal template remains open.
11. Answered by MKT-DEC-006: secondary market is available at launch.
12. Answered by MKT-DEC-007/MKT-DEC-009/MKT-DEC-016/MKT-DEC-017/MKT-DEC-020: secondary market is a bulletin-board claim/participation transfer mechanism; seller may list only an entire holding; seller sets price as a discount/premium percentage of current principal balance; accrued interest to settlement belongs to seller and future interest belongs to buyer; launch fees are 0.25% maker/seller and 0.75% taker/buyer, calculated on transfer price excluding accrued interest and rounded half-up; current/performing listings can settle directly after checks, while non-performing/non-standard listings require admin approval, disclosure note, and additional buyer acknowledgement before purchase.
