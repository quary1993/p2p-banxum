# Investor Portal

Status: Draft. Updated with operating-model, identity, balance, FX, marketplace, servicing, recovery waterfall, document/tax, communication, and authentication decisions on 2026-06-01.

## Purpose

Define the user-facing portal where investors onboard, assess loans, invest, monitor portfolio performance, receive documents, manage funds, and handle tax/reporting outputs.

## Scope

- Natural-person lender self-service onboarding and eligibility.
- Natural-person lender portal support. Legal-entity lenders are admin-created/off-platform onboarded and can behave like regular lender accounts once Garanta creates and KYB/AML-approves accounts for them.
- KYC/AML status visibility for natural-person lenders. Legal-entity lender KYC/AML status is admin-recorded/offline.
- Generic P2P lending risk acknowledgements and disclosures.
- Marketplace browsing.
- Multi-currency investor balances.
- Deposits, withdrawals, and balance ageing reminders.
- Currency exchange.
- Investment order placement.
- Secondary-market buying and selling.
- Portfolio dashboard.
- Investment payment instructions and transaction history.
- Repayment and performance reporting.
- Investor documents.
- Annual lender tax information statement available to all investors.
- Notifications, statements, and support.
- Optional marketing communication consent capture.

## Core User Journeys

### Onboard

1. Register account.
2. Accept registration-time platform terms by checkbox/clickwrap.
3. Complete profile.
4. Complete mandatory phone verification.
5. Optionally consent to marketing communications/newsletters.
6. Complete KYC/AML if natural-person lender.
7. Acknowledge generic P2P lending risk disclosures where required by the flow.
8. Receive dashboard, deposit, balance, FX, and investment access if approved.
9. Add withdrawal bank details where allowed.

Legal-entity lenders do not self-register. Their registration and KYC/KYB/AML are handled off-platform, and their platform accounts/records are created by admin. When Garanta creates and KYB/AML-approves accounts for them, they behave like regular lenders for balances and transactions, except onboarding/KYC evidence is admin-recorded rather than completed through Didit.

### Discover Loan

1. Before login, browse preview listing data.
2. After registration-time KYC approval, browse full loan data.
3. Filter by product type, duration, yield, rating, geography, sector, collateral, and availability.
4. Open loan detail page.
5. Review borrower/entity details, loan terms, risk rating, documents, repayment schedule, collateral, fees, and disclosures.
6. Mark interest or create investment order.

### Invest

1. Enter investment amount.
2. Validate minimum amount, maximum remaining loan capacity, available eligible balance, and exposure warnings.
3. Confirm KYC/AML remains valid and no compliance block applies.
4. Show available same-currency balance and deposit option if balance is insufficient.
5. Show fees, expected cash flows, risks, and required acknowledgements.
6. Accept primary-market investment terms/contracts, risk disclosure, and required acknowledgements by checkbox/clickwrap.
7. Reserve or debit available investor balance for the order according to allocation rules.
8. Generate investment-time PDF documents from the template/data snapshot and send them by email.
9. Receive order status and downloadable documents.

Deposit instructions should warn lenders to send the intended currency to the matching currency IBAN. Cross-currency bank transfers are not advised because banks may auto-convert and charge fees; the platform reconciles only the amount received in the credited balance currency with the correct payment reference.

Investors cannot cancel orders. Pending orders remain open until the loan funding target is reached, the campaign is closed, or platform rules close them. Each investor may have up to 50 pending orders at launch, subject to final configuration.

### Manage Balances

1. View balances by currency.
2. View balance source entries with received timestamp, source type, remaining amount, reinvestment deadline, withdrawal deadline, and penalty status.
3. View a per-currency breakdown of balance available for investment/reinvestment, balance that must be withdrawn, balance that is FX-eligible while still inside applicable ageing windows, and balance in penalty/frozen status.
4. Deposit funds to enabled currency collection accounts after KYC approval.
5. Withdraw available balances to verified bank account.
6. Use eligible balances for primary-market investments, secondary-market purchases, or currency exchange.
7. Receive explicit errors when trying to invest/reinvest with balance source entries older than 30 days.
8. Receive ageing reminders on days 25, 46, 53, 58, 59, and 60 for unconsumed balance source entries.
9. See day-60 notice that balance is subject to penalties if not withdrawn.
10. If no usable IBAN is available after day 60, see a blocking banner requiring an IBAN before further financial actions are unlocked, while keeping read-only access to portfolio, documents, tax information statements, notices, and messages.

Balance funds are non-interest-bearing. Registration-time terms must explain that Garanta Finanzgruppe AG cannot extend the 60-day regulatory/compliance holding limit.

### Exchange Currency

1. Open the currency-exchange menu section.
2. Select source currency, target currency, and amount.
3. Review a live executable quote, platform FX fee, final rate, source debit, target credit, and 1-minute quote expiry countdown.
4. Accept FX terms by checkbox/clickwrap before the executable quote expires, or refresh the quote after expiry.
5. Submit exchange.
6. Receive the target-currency balance instantly in the platform.
7. The target-currency source inherits the 30/60-day ageing deadlines from the consumed source balance. If multiple source entries are consumed, the target entry uses the earliest consumed investment and withdrawal deadlines.
8. See exchange status and ledger entries.

FX is an auxiliary settlement function, not a trading or speculative feature. Launch FX fee is 1.5%, configurable by superadmin. Enabled currencies start with CHF and EUR and are configurable by superadmin. Launch FX pairs are CHF/EUR and EUR/CHF only, with more pairs configurable later.

No minimum exchange amount applies. The launch maximum conversion limit is CHF 100,000 per investor per day or equivalent in another currency, configurable by admin. Admin externally settles aggregate FX deltas at end of day or the next morning. Background-polled FX rates may be shown for display only, but execution uses a fresh Yahoo Finance live quote fixed for 1 minute and subject to sanity checks.

Website balances and ordinary amounts display 2 decimals. During FX quote and confirmation, the investor may see exchange details with 4 decimals before confirming.

### Monitor Portfolio

1. View principal outstanding, expected interest, realized interest, arrears, defaults, and pending transfer statuses.
2. Drill into loan-level performance, including current loan status and days past due where applicable.
3. View received balance-credit history, including partial installment, full installment, multiple-installment, late/default recovery, and early repayment distributions. Recovery entries should show the lender credited amount and available split between principal, contractual interest, default/penalty interest, recovery costs/fees where disclosed, other penalties/costs, and rounding difference.
4. Receive email notification when a lender balance credit is made.
5. View admin-published public notes on late, defaulted, recovery, or operationally changed loans where admin has added them.
6. Download investor statements and tax documents.
7. Manage reinvestment preferences if supported.

### Use Secondary Market

1. View eligible holdings that can be offered for sale.
2. For seller listings, list an entire holding only and set a sale price as a discount or premium percentage of current principal balance.
3. If the holding is current/performing, submit the listing directly after system checks and seller/listing terms acceptance.
4. If the holding is late, overdue, restructured, under observation, in default, in recovery, under legal enforcement, subject to a payment incident, or otherwise non-standard, submit a listing request for Garanta admin approval before it becomes visible.
5. For purchases, review required disclosures, loan status, days past due where applicable, current principal balance, sale price, discount/premium, accrued interest, fees, and settlement consequences.
6. Accept required secondary-market buyer terms and risk acknowledgements by checkbox/clickwrap. For approved non-standard listings, accept an additional risk acknowledgement before purchase.
7. Generate secondary-market listing/purchase PDFs from the template/data snapshot and send them by email where applicable.
8. Confirm listing, sale, or purchase.
9. Complete assignment transfer and settlement.
10. See updated portfolio and documents.

The secondary market is a bulletin-board claim/participation transfer mechanism. Sellers may list only entire holdings; splitting or partially transferring one holding is not allowed. If the seller has multiple separate holdings in the same project, each holding may be listed separately.

Sellers can set their own sale price as a discount or premium percentage of current principal balance. Accrued interest up to settlement is calculated separately, daily, pro rata, and belongs to the seller up to transfer date for current/performing loans/projects. Future interest after settlement belongs to the buyer.

Launch secondary-market fees are 0.25% maker/seller fee and 0.75% taker/buyer fee, both charged at settlement.

Fees are calculated on the agreed transfer price, excluding accrued interest, and rounded half-up to the nearest cent/minor currency unit. Minimum fee support is configurable.

Listings must show the transferred holding's current principal balance, sale price, discount or premium, accrued interest, seller fee, seller net proceeds, buyer fee, and buyer total cost.

Holdings in non-performing or otherwise non-standard loans/projects may be sold only after Garanta admin approval, with clear status disclosure and additional buyer acknowledgement.

## Dashboard Content

- Pending investment transfers.
- Available balances by currency.
- Ageing balance source entries requiring investment, reinvestment, or withdrawal.
- Invested principal.
- Outstanding principal.
- Expected interest.
- Received repayments.
- Late principal/interest.
- Weighted average yield.
- Weighted average term.
- Diversification by borrower, product, sector, rating, and maturity.
- Pending orders.
- Pending withdrawals.
- Pending currency exchanges.
- Required actions.

## Investor Documents and Tax Outputs

- Platform terms.
- Risk disclosures.
- Generic P2P lending risk acknowledgement document.
- Investment terms and acknowledgements.
- Per-order loan claim assignment document.
- Secondary-market reassignment document, where applicable.
- Secondary-market seller/listing terms, where applicable.
- Payment instructions.
- Deposit instructions.
- Withdrawal confirmations.
- Currency-exchange confirmations.
- Investor statements.
- Repayment statements.
- Annual lender tax information statement.
- Refund or recovery notices where applicable.

Investor documents are English-only at launch. Accepted/generated transaction documents can be downloaded from the portal after the relevant primary investment or secondary-market purchase and are sent by email at transaction time.

## Loan Detail Requirements

- Borrower/entity summary.
- Legal borrower name if disclosure policy permits.
- Loan purpose.
- Collateral/backing type.
- Collateral value, if investor-facing disclosure policy permits.
- Calculated LTV when collateral value is non-zero and LTV is displayable.
- Collateral description, if investor-facing disclosure policy permits.
- Requested amount and funded amount.
- Interest rate or expected return.
- Term and repayment type.
- Fees.
- Risk rating and rating explanation.
- Collateral/guarantees if any.
- Key financial metrics.
- Published borrower documents, if uploaded by admin: borrower presentation, borrower financial PDF, and admin-named generic borrower documents.
- Required investor documents and acknowledgements.
- Investment limits.
- Risk warnings.
- Funding deadline.
- Allocation method.

Public preview fields before login are borrower, amount, interest, period, loan type, status, borrower country, and loan currency.

Optional borrower/entity financial fields must be hidden completely when admin has not declared them. Do not show empty labels or placeholder values.

## Generic Risk Warnings

Final wording must be approved by legal and compliance. Initial risk-warning categories:

- Loss of some or all invested capital.
- Borrower default and delayed repayment.
- Real estate valuation and collateral enforcement risk where the loan is real-estate backed.
- Illiquidity and limited or unavailable secondary-market exit.
- Secondary-market price may differ from principal outstanding.
- No guaranteed return.
- No deposit protection.
- Balance ageing, withdrawal deadline, penalties, and no extension of the 60-day limit.
- Currency exchange rate and execution risk.
- Platform, operational, payment, and servicing risk.
- Concentration risk.
- Tax and cross-border regulatory risk.
- Fees may reduce returns.
- Past performance and risk grades do not guarantee future performance.

Basic generic acknowledgement text for planning and placeholder templates:

"I understand that investing through BANXUM involves lending-related risks. I may lose some or all of the amount invested. Borrowers may pay late, pay only part of the expected amount, or default. Collateral, guarantees, or security may not fully cover losses and may take time and cost to enforce. Expected returns are not guaranteed, past performance and risk ratings do not guarantee future results, and secondary-market sale may be unavailable or only possible at a lower price. I understand that fees, taxes, currency exchange, platform operations, payment processing, and cross-border factors may affect my net return. I have read the relevant risk disclosures and investment documents before investing."

This text is not final legal wording. It is a generic placeholder for product design, template scaffolding, and acceptance mechanics until Garanta uploads the final legally approved risk acknowledgement/risk disclosure document.

## Controls

- Block investing until onboarding and compliance status are valid.
- Block investing when user jurisdiction or compliance status is ineligible.
- Natural-person self-service lender registration is available for Switzerland and EU/EEA at launch, subject to compliance and operational restrictions.
- Show only preview listing data before login.
- Preview listing data before login is limited to borrower, amount, interest, period, loan type, status, borrower country, and loan currency.
- Show full loan data only after registration-time KYC/AML approval, subject to final jurisdiction and eligibility restrictions.
- Block terms/contracts acceptance, deposit instructions, balance access, withdrawal, FX, and investment actions until natural-person lender KYC/AML is valid.
- Block dashboard, deposit, balance, FX, primary-market, and secondary-market access until registration-time KYC/AML is valid.
- Block legal-entity lender financial actions until admin-recorded KYB/AML approval is complete and no compliance hold applies.
- Use email magic-link login for investor/client portal access at launch.
- Require mandatory phone verification for natural-person investors at launch.
- Provide support-facing offline account-access recovery for lost or bouncing email access, using identity re-verification and verified phone/account evidence before admin updates email/login access.
- Keep investor sessions long-lived unless the investor logs out, admin restricts access, the session is revoked, or a security event requires re-authentication.
- Require fresh email-code confirmation before sensitive/financial actions, including withdrawals, withdrawal bank-account changes, currency exchange, primary-market investments, secondary-market listings, and secondary-market purchases.
- Show investor balances by enabled currency.
- Track balance source entries with received timestamp, source type, remaining amount, reinvestment deadline, withdrawal deadline, and penalty status.
- Consume balances FIFO within each currency.
- Block investment/reinvestment from balance source entries older than 30 days.
- Allow primary-market investment when the source entries are pledged/allocated inside their 30-day investment window, even if the loan funding deadline is later than the source entries' day-30 investment deadline.
- Show explicit errors and per-currency balance breakdowns for investable, withdraw-required, FX-eligible, and penalty/frozen balances.
- Send balance ageing reminders on days 25, 46, 53, 58, 59, and 60.
- Apply day-60 penalty treatment according to env/deployment configuration and legal/compliance policy.
- If a usable IBAN exists at day 60, support admin forced withdrawal.
- If no usable IBAN exists after day 60, freeze financial actions except declaring/updating a usable IBAN and show a blocking banner; keep read-only access to portfolio, documents, tax information statements, notices, and messages.
- Provide a separate currency-exchange menu section.
- Credit target-currency balance instantly after an accepted non-expired FX quote and inherit the target-currency source ageing deadlines from the consumed source balance entries.
- Show FX quote expiry clearly and require a refreshed quote after the 1-minute lock expires.
- Enforce enabled launch pairs CHF/EUR and EUR/CHF, no minimum exchange amount, and the configured per-investor daily maximum conversion limit.
- Show normal balances/amounts with 2 decimals and FX confirmation details with up to 4 decimals before confirmation.
- Show lender monetary actions and payment instructions clearly, with email communication for relevant monetary actions.
- Show currency-specific IBAN and payment reference for each deposit or required external funding action.
- Do not show pending orders as reserved capacity or funded progress until balance/funds are allocated.
- Enforce the launch pending order limit, assumed to be 50 per investor.
- Do not provide investor cancellation for orders.
- Show exposure metrics and concentration warnings, but do not enforce hard concentration limits in v1.
- Enforce product eligibility restrictions.
- Require current terms acceptance.
- Use checkbox/clickwrap acceptance for v1 investor terms, risk disclosures, assignment documents, and secondary-market documents.
- Record document/template version, data snapshot, timestamp, user, acceptance context, and available technical evidence for each checkbox/clickwrap acceptance.
- Generate primary-investment and secondary-market purchase PDFs at transaction time and send them by email.
- Allow investors to download accepted/generated documents from the portal after the relevant transaction.
- Make annual lender tax information statements available to all investors.
- Capture optional marketing communication consent during registration or profile flow, without exposing full notification-preference management in v1.
- Expose support email in an appropriate help/FAQ/footer location.
- Provide clear risk and fee disclosures.
- Require explicit risk-warning acknowledgement before each primary-market investment and secondary-market purchase.
- Audit all investment orders, acknowledgements, order closures, refunds, repayment notifications, and document downloads.
- Audit all deposits, balance credits, withdrawals, FX quotes, FX acceptances, FX executions, ageing reminders, and penalty applications.
- Audit forced withdrawals and penalty-mode freezes/unfreezes.
- Do not expose internal admin distribution artifacts or bank statement attachments directly to lenders unless a later disclosure policy allows it.
- Show portfolio loan status and days past due when a loan is late/defaulted.
- Show admin-published public loan notes to affected investors when available.
- Allow current/performing secondary-market listings to publish automatically after system checks.
- Route late, overdue, restructured, under-observation, default, recovery, legal-enforcement, payment-incident, or otherwise non-standard secondary-market listing requests to admin approval before publication.
- Require additional buyer acknowledgement for approved non-standard secondary-market purchases.

## Dependencies

- Identity, KYC, KYB, and AML.
- Marketplace, Investments, and Allocations.
- Payments, Ledger, Custody, and Reconciliation.
- Loan Servicing and Repayments.
- Documents, Contracting, and E-Signature.
- Communications and Notifications.

## Q/A Backlog

1. Updated by KYC-DEC-003: unauthenticated users may see preview listing data; full authenticated dashboard/marketplace access requires registration-time KYC approval.
2. Answered by Operating Model DEC-004, KYC-DEC-001, and MKT-DEC-008: retail, professional, and institutional lenders may be supported; self-service registration is natural persons only; legal-entity lenders are admin-created/off-platform and investments are entered by admin.
3. Answered by MKT-DEC-011: launch minimum primary-market investment is 1,000 CHF/EUR, configurable by superadmin; maximum is the remaining amount/cap available on the loan.
4. Updated by MKT-DEC-001: primary-market orders are first-come-first-served based on balance reservation/allocation timestamp or bank value date of validated external funds.
5. Answered by MKT-DEC-004: investors cannot cancel orders.
6. Superseded by PAY-DEC-003/PAY-DEC-017/PAY-DEC-018: investors have multi-currency website balances, can deposit/withdraw/exchange, and receive repayment/SM proceeds as balance credits subject to ageing deadlines.
7. Answered by marketplace/admin TODO: auto-invest and automated reinvestment are future scope, not launch scope.
8. Updated by KYC-DEC-003 and ORIG-DEC-003: full loan data requires registration-time KYC approval; optional borrower financial fields are hidden when not declared.
9. Answered by DOC-DEC-001 and FIN-DEC-001: investor statements, repayment statements, and annual lender tax information statement for all investors are required; generated/accepted transaction documents are downloadable and emailed.
10. Answered by MKT-DEC-006/MKT-DEC-007/MKT-DEC-009/MKT-DEC-020: secondary-market selling and buying are available at launch as full-holding bulletin-board transfers; sellers set discount/premium price as a percentage of current principal balance; accrued interest to settlement belongs to seller and future interest belongs to buyer; non-performing/non-standard listings require admin approval and additional buyer acknowledgement.
11. Answered by ACC-DEC-001: investor/client portal login uses email magic links, and phone verification is mandatory for natural-person investors.
