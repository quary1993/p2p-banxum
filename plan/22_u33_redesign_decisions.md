# U33 Redesign Reconciliation Decisions

Status: Approved product decisions, current at 2026-11-08 (group 2 approved 2026-11-04, group 3 completed 2026-11-08).
Source: "Lot 113 - Register of reconciliation decisions with Vlad" (Romanian original, received 2026-11-09), answering the 39 items of `BANXUM_redesign_nov3_decisions` (design package `website_redesign_nov3`, edition "Banxum unified U33", 3 Nov 2026).
Owner: Banxum product (decisions); Vlad (implementation).

## How These Decisions Apply

- The decisions below replace the conflicting rules of the U33 design and the conflicting platform decisions listed under "Supersedes". The rest of the approved U33 design and behaviour stays.
- "Approved" means a product decision. It is not an implementation, a legal check or a backend audit. Open confirmations are listed in each decision.
- Item numbers 1-39 match the reconciliation file. Each decision is listed once.
- For items 29 and 39 the follow-up work is approved, not a visual result and not the removal of features.
- The implementation order is in `IMPLEMENTATION_PLAN.md`, "Phase 17: U33 Redesign and Reconciliation Decisions".

| Group | Topic | Items |
| --- | --- | --- |
| 1 | Access, security and profile | 1, 25, 26, 27, 28 |
| 2 | Money and bank accounts | 2, 3, 4, 5, 33 |
| 3 | Product and security (collateral) | 15, 16, 21, 38 |
| 4 | Minimum, interest and repayment | 8, 10, 11 |
| 5 | States and exceptions | 9, 22, 29 |
| 6 | Resale and fees | 6, 7, 12 |
| 7 | Credit file and contracts | 13, 14, 20, 23, 24 |
| 8 | Smart Invest, saved items and notifications | 17, 18, 19, 30 |
| 9 | Localization | 31, 32 |
| 10 | Public area, identity, texts and resources | 34, 35, 36, 37, 39 |

## Group 1 - Access, Security and Profile

### U33-DEC-01: Sign-In and Confirmation of Operations

Status: Approved (new solution). Open implementation confirmations below.
Supersedes: ACC-DEC-001 (magic-link login), ACC-DEC-008 (email code for sensitive actions), ACC-DEC-009 (email code + PIN).

Decision:

- Investor login uses a **password plus a second factor: an SMS code or an authenticator-app code**, chosen by the investor. Two-factor authentication is mandatory. The method is enrolled and verified once; the investor does not type a phone number at each login. Both methods are not required. No passkeys and no magic link as an alternative login.
- Investments, withdrawals, bank account changes and resale actions need a review step and **only the personal PIN**, inside the authenticated session. Each investment is confirmed separately. Agreement checkboxes are unchecked by default.
- The server authorization is bound to the exact operation, amount and destination; it expires and can be used once. Changed data needs a new confirmation. The PIN is reusable; the authorization is not.
- Attempt limits, audit logging and alerts stay.

Recovery:

| Case | Procedure |
| --- | --- |
| Forgotten password, second factor available | Expiring single-use link to the verified email **plus the configured second factor**, before the new password. The link alone does not authenticate. |
| Forgotten PIN | Password + configured second factor, then a new PIN. PIN-only confirmation of operations does not remove the protection of recovery. |
| Forgotten password and PIN | Password recovery, then PIN recovery, as above. |
| Second factor not available / not enough access | Assisted recovery: identity verification, controlled enrolment and revocation of the old access. No bypass by email or by an unverified phone. |

- Changing the second-factor method or the verified phone needs access/identity control and a notification. Email alone cannot switch off the second factor. Every reset is notified.
- Password recovery or factor replacement revokes old sessions and tokens. A PIN reset invalidates unfinished authorizations. Recovery never executes transactions.

To clarify with Vlad: the operational procedure, migration of existing accounts, the SMS service and the recovery implementation. SMS is more exposed than an authenticator app (including number takeover). The PIN alone is not a new second factor. A security review stays necessary, without silently adding a code to each operation.

### U33-DEC-25: Sessions, Sign-In History and Security Alerts

Status: Approved (design).
Supersedes: ACC-DEC-007 (device list was "nice to have").

Decision:

- Security settings show the device/browser, approximate location, last activity and the current session. The investor can close one session or all other sessions, with real revocation of access.
- The sign-in history keeps date/time, device, approximate location, method and result, also after sessions end.
- Email alerts for a new device/browser and for important security changes, independent of marketing consent.
- The existing mechanisms are adapted to U33-DEC-01. IP location is not GPS; fields and history retention must match the real data and the privacy rules. Verification covers real revocation and alert triggering, not only the interface.

### U33-DEC-26: Changes to Personal Data

Status: Approved (Vlad's platform).
Confirms: ACC-DEC-006 support recovery, COMMS-DEC-006.

Decision:

- Verified personal data, including email, phone and address, cannot be edited freely. The platform shows the available information and a "Contact support to change" access.
- The team verifies the identity and makes the authorized change. An email request alone is not proof of identity.
- No invented missing fields. A change is never shown as done before it is confirmed. Corrections stay possible, and the procedure is aligned with access recovery (U33-DEC-01).

### U33-DEC-27: Self-Declaration and Periodic Review

Status: Approved (extension). Operational/compliance details open.
Supersedes in part: KYC-DEC-007 (no platform monitoring).

Decision:

- Didit stays. The relevant declarations are added to onboarding and to the profile: beneficial owner of the funds, source of funds, PEP status and expected yearly volume. A "yes" to PEP leads to a review; the platform does not force a "I am not a PEP" declaration.
- The admin keeps the declaration, its date, changes, review result and any requested additions.
- A re-verification date can be set per investor, with notification and update of the required data/verification. Handling can be manual. A full continuous-monitoring system is not required.

To define (operations/compliance): exact fields, responsibilities, escalation and periodicity. Automatic yearly re-verification is not approved. The Didit result does not automatically approve the declarations or count as compliance approval.

### U33-DEC-28: Account Closure

Status: Approved (Vlad's platform).
Confirms: ACC-DEC-006.

Decision:

- The "Close account" button sends a **request** to the team. The team checks balances, investments and open obligations before closing. The confirmation that the request was received is separate from the confirmation of the actual closure.
- No promise of instant closure or of deleting all records. Records and operations needed to settle obligations are kept.

## Group 2 - Money and Bank Accounts (approved 2026-11-04)

### U33-DEC-02: Where Repayments Are Paid

Status: Approved (Vlad's platform).
Confirms: PAY-DEC-005.

Decision:

- Principal, interest and recoveries go to the **Banxum balance**, not directly to the investor's IBAN. The investor reinvests by explicit confirmation or asks for a withdrawal. Money not invested follows U33-DEC-03.
- CHF/EUR and the principal/interest components stay separate.
- All functional effects and texts in the platform, public site, schedules, reports and notifications that say "paid directly to the bank account" are adapted. This is not only a wording change.

### U33-DEC-03: Return Deadline and Return Notices

Status: Approved (mixed variant).
Supersedes: the 58-day return of PAY-DEC-017 (2026-10-16) and the reminder days 25/46/53/56/57/58.

Decision:

- Money not invested is returned after **56 days**, with notices **10 days and 3 days before** the return, then a confirmation of the return. The concrete date is shown. Urgent notices about the IBAN stay separate.
- A reservation does not reset or silently extend the period. The project for which money is reserved must close before the last allowed holding day; reservation eligibility follows the 56-day deadline.
- Vlad must specify the day counting, the moment the return starts and the handling of non-business days, so that the buffer before day 60 is real. The change is not a number swap in the interface with the old behaviour kept. The legal framing of holding money is confirmed separately.

### U33-DEC-04: Impossible Return and Penalty

Status: Approved (adapted solution).
Supersedes: the 1% daily penalty and penalty mode of PAY-DEC-017 / PAY-DEC-022.

Decision:

- The **1% daily penalty is removed**.
- A bank account is verified before the first investment. The last valid IBAN needed for the return cannot be removed while there is money to return.
- If a return fails or the IBAN becomes invalid: a clear message, correction/verification of the data and intervention by the team. Money past its deadline does not become available for reinvestment again. Support and the documents needed to fix the situation stay accessible.
- States and procedure follow the 56 days and are validated operationally and legally: a simple block or a fee does not solve an exceeded deadline.

### U33-DEC-05: Bank Accounts and Deposits

Status: Approved (Vlad's platform, with adaptations).
Updates: PAY-DEC-022 payout-IBAN controls.

Decision:

- Several verified bank accounts in the investor's own name; one **default return account per currency**. "Verified" and "Pending verification" are shown separately.
- Adding or changing an account is confirmed with the PIN (U33-DEC-01). The destination becomes usable after the holder is verified. The transfer reference, name or email does not replace that verification. Unidentified or unclear deposits are checked by hand before they become available.
- The general 48-hour block of the design is removed. Holder checks, confirmations and change notifications stay.

### U33-DEC-33: Currency Exchange

Status: Approved (the existing function stays switched off).
Confirms: PAY-DEC-018 as switched off on 2026-10-16.

Decision: CHF and EUR are separate, with no implicit conversion. The FX code can stay, with no active FX offer or fee. Switching it on later needs a separate decision, the display of rate and costs, confirmation and verification.

## Group 3 - Product and Security (completed 2026-11-08)

### U33-DEC-15: Banxum Co-Investment

Status: Approved (new/adapted function).

Decision:

- Banxum may co-invest from its own funds **case by case, with no obligation and no minimum percentage**. No participation does not block publication.
- The actual participation is identified by entity, amount, status and operation reference, separate from an intention to participate and from the share kept by an originator.
- No priority, identical terms or guaranteed recovery are implied. Terms and timing are confirmed contractually/operationally. Public statements that promise participation in every loan are corrected.

### U33-DEC-16: Risk Ratings

Status: Approved (design).
Supersedes: ORIG-DEC-004 investor visibility; rating criteria of MKT-DEC-026.

Decision:

- No risk ratings or risk classes in the investor experience: public site, platform, filters, Smart Invest, reports and generated documents. Financial data, securities, late payments and Default stay.
- Existing ratings may stay passively in the admin **only if this costs nothing extra**; their use, completion or development is not planned. They never influence filtering or matching in a hidden way. Migration of existing preferences removes the rating criteria explicitly, without investing automatically.

### U33-DEC-21: Several Securities and Structured Details

Status: Approved (design).
Supersedes: PROD-DEC-002 / PROD-DEC-003 (one collateral item per loan).

Decision:

- A loan can have several securities, managed separately: type of asset/right, holder/guarantor, rank, status, value, valuation date/source and appraiser, insurance and relevant documents, only where they apply. For personal/corporate undertakings: scope and limit of the undertaking.
- The opportunity, the credit file and the filters use the same data. Asset value, loan and prior-ranking debt are kept separate; a cumulative ratio is labelled as such. The guarantor's wealth is never added to the property value, and the same asset is never counted twice.
- The existing taxonomy is reconciled, including vehicles, inventory, pledged securities and cash where they really exist. "Mixed" is split into its securities, "Other" needs a description, and "asset-backed" does not replace the identification of the right. No invented data at migration; this does not approve new products. Mandatory eligibility is in U33-DEC-38.

Implemented 2026-11-10 (Phase 17.4): `plan/07_loan_product_catalog.md` PROD-DEC-003 note. A vehicle type is not added (no vehicle loans exist today); existing "mixed" records stay until an admin splits them.

### U33-DEC-38: Public Wording and Security Eligibility

Status: Approved (final).
Supersedes: the "unsecured exception" collateral type for new loans (PROD-DEC-002).

Decision:

- Every loan must have **collateral or guarantees, with no unsecured exceptions**; the requirement is not limited to physical assets. The admin does not allow publication of a new ineligible loan. Rights and documents must be verified; a label alone is not proof. History stays factual, with no guarantees invented retroactively.
- The approved wording "Every loan is secured by collateral or guarantees" is published in line with real eligibility. Universal statements about "real assets" are replaced and "Your investment is protected" is removed. This does not mean guaranteed repayment or a risk-free investment.
- Classification follows the concrete right: an invoice is a document; a receivable against a third party can be collateral if validly pledged. The assignment of the financed claim alone does not create an extra security. The debtor's promissory note does not automatically become extra collateral or a third-party guarantee; a third party's aval/undertaking is examined separately. Documents and applicable law are checked, without reopening the product choice.

## Group 4 - Minimum, Interest and Repayment

### U33-DEC-08: Cap for Swiss Borrowers and Minimum Investment

Status: Approved product rule; legal framing to confirm.
Supersedes: MKT-DEC-028 (20 investors per Swiss-borrower loan and the raised "minimum now").

Decision:

- For each **Swiss borrower**, the total of its loans must be **strictly below CHF 500,000**, with no maximum number of lenders in this model. Exactly CHF 500,000 is not eligible. It is not a separate cap per project, and it does not depend on the loan currency or the investor's nationality.
- The places rule and the minimum calculated from the amount to the threshold divided by the places left are removed. The usual minimum of **EUR/CHF 1,000** stays, limited to the amount still available in the project, and the minimum success threshold stays. Reaching the threshold does not mean full funding or immediate closing. The minimum is not a recommendation or a pre-filled amount.
- Admin, checks, displays and resale are adapted. Incompatible Swiss examples are reconciled explicitly, without silent changes.

Before the real implementation: confirm the basis of the total (external loans, repaid principal, undisbursed commitments, assigned claims), the moment of the check, the technical conversion to CHF and the control of simultaneous operations. The control conversion does not switch on FX for investors. Summing Banxum projects alone is not assumed to be enough. The ESTV 46/47 tax reference and FINMA conditions are separate; this rule alone does not prove legal compliance.

### U33-DEC-10: Interest Calculation and Start Date

Status: Approved (final): Actual/365 Fixed.
Supersedes: the monthly rate (annual rate / 12) of PROD-DEC-008 and the schedule engine.

Decision: interest accrues on actual days, on the outstanding principal, with a fixed denominator of **365**, also in leap years:

`Interest = sum(outstanding principal in the interval x annual rate as a decimal x actual days / 365)`

- Intervals are split when principal or rate changes. Principal due but unpaid is not deducted as if repaid; contractual rules apply.
- First/last broken periods, early repayment and mid-period changes use the same formula. 29 February counts; the basis does not become 366.
- Daily calculation is not daily payment, daily capitalization or equal monthly interest. Frequencies are in U33-DEC-11; annual rate / 12 is not used as a general rule.
- Assignment/resale splits rights at the effective date, with no doubled or missing days; the originator's share is separate (U33-DEC-24). Existing/imported contracts keep their convention; an assignment does not change it retroactively.
- Penalties have separate rules: rate, base, start, beneficiaries, cumulation/replacement and day convention per contract. They are not derived from the Due/Late labels, and interest is not capitalized automatically.

Example, constant principal 10,000 at 12%: **15 days = 49.32; 30 days = 98.63; 31 days = 101.92**. For 366 days the unrounded value is 1,203.287671...; 1,203.29 after one final rounding. Rounding individual installments can need a separate adjustment.

To clarify with Vlad: the contractual start date (not the reservation date), inclusion/exclusion of boundary days, the effective date of a balance change, non-business days, intermediate precision, rounding and allocation/adjustment between investors. Tests cover leap years, broken periods, amortization, early/late repayments and assignments; contracts, projections, schedules, transactions and resale must agree.

### U33-DEC-11: Repayment Types and Frequencies

Status: Approved (extension as designed).
Supersedes: PROD-DEC-005 / SERV-DEC-001 (monthly-only launch types).

Decision:

- Base frequencies: **monthly, quarterly, half-yearly, annual**, each with interest-only and principal at the end, or with principal and interest. Separately: full repayment of principal and interest at the end.
- Custom schedules and initial interest-only phases are allowed; relevant existing structures stay, with no artificial limit to three simplified formulas. Configuration belongs to the admin and the contract, not to the investor, who only filters offers. The interface keeps the grouping **Periodic repayments / Payment at maturity**, with the principal structure and real phases explicit.
- Imports keep the real data and phases; an irregular schedule does not get an invented frequency. Admin, calculator, contracts, calendar, opportunities and Smart Invest follow U33-DEC-10; incompatible monthly formulas are not reused. The editor/import and validations for custom schedules are defined with Vlad. Existing contracts are respected.

## Group 5 - States and Exceptions

### U33-DEC-09: Late, Default and Termination

Status: Approved (mixed variant).
Supersedes: SERV-DEC-008 (Late day 5, Default day 16).

Decision:

- Base scenario: **Due** on the due date and during the first 14 days overdue, **Late from day 15**, **Default at 60 days**, with thresholds adaptable to the actual contract. Due does not mean paid or "On schedule"; the real number of overdue days stays correct before Late.
- Default, termination and recovery stages are separate, manageable and visible states/events, with real dates and history. A loan is not terminated automatically just because the label becomes Default. Existing contracts keep their terms; penalties follow the contract, not the visual thresholds.
- Vlad specifies the day boundaries in Europe/Zurich and the link with notifications, reports, resale and U33-DEC-22.

### U33-DEC-22: Late Payment and Recovery Information

Status: Approved (mixed variant).
Updates: RISK-DEC-003 / RISK-DEC-007.

Decision:

- Vlad's existing data, notes and updates are reused, with the **stage-by-stage presentation** of the design. Extra manual administration per case is accepted.
- The admin records the arrears, recovery amounts/dates, events and real stages, including termination, plus the note for investors. The next step/date shows only when known. The investor sees what was done, the current stage and what really comes next; no fictitious automatic progress or invented universal calendar.
- The history stays accessible on request, and updates are still published, including the existing email to the relevant investors. Messages explain Banxum's actions and do not ask the investor to manage the recovery. Recoveries go to the Banxum balance (U33-DEC-02). Stage names and fields follow the real process, with no promises about a team or procedures that do not exist.

Implemented 2026-11-10 (Phase 17.4): `plan/12_risk_collections_recoveries.md` RISK-DEC-003 note. Stage titles are free text with suggested examples; the list of real stage names is in the open questions of Phase 17.

### U33-DEC-29: Missing States and Screens, Including Company Accounts

Status: Approved as later design work. Not declared done and not visually approved.

Decision: the following are prepared later on the existing mechanisms:

| Case | Distinction to keep |
| --- | --- |
| Funding closed, payout to the borrower pending | Separate from Repaying; the interest date follows the contract, not the label. No resale before real eligibility. |
| Funding failed/cancelled | The reservation is released to the Banxum balance, not returned directly to the bank; the holding deadline is checked, and expired funds are not reinvested. |
| Written-off claim | Written off is separate from Default and Repaid and does not mean automatic waiver of rights; later recoveries stay recordable. |
| Restricted/locked/closed account | Reason and remedy that fit the state; access to support/documents as appropriate. Messages before login do not reveal that the account exists. |
| Re-verification in progress | Requirement, stage and any limits follow the U33-DEC-27 process. |
| Security for existing accounts | Migration to password + chosen second factor + PIN, not only PIN setup. |
| Company investor and representative | Team-managed path with verification of the company/representative; no automatic self-service onboarding is implied. |

These are cases/states, not a request for seven new pages. Existing components are reused. The design's `src/create-account.js` already has verification/PIN/company-contact states, and the profile has desktop/mobile verification states; they are completed, not declared missing and not rebuilt by default.

## Group 6 - Resale and Fees

### U33-DEC-06: Resale Price and Premium

Status: Approved (design adjusted on 2026-11-08).
Supersedes: MKT-DEC-007 "par or discount only" (2026-10-16).

Decision:

- The seller sells **the investor's whole position**, without splitting, not the whole loan. The principal price can be **0-102% of the outstanding principal**: discount allowed, premium at most **2%**. Accrued unpaid interest is added separately.
- The slider keeps 0.5 percentage-point steps and the manual amount to the cent, with the real percentage in sync. Discount over 10% -> warning; 20% or more -> stronger warning, with no automatic block. A principal price of zero stays allowed, with no new minimum; the total can include accrued interest.
- Active listings are reconciled explicitly with U33-DEC-06/07; closed trades are not recalculated. The old Help text with 95-105% is corrected.

### U33-DEC-07: Seller Fee

Status: Approved: 2%, with a cap (replaces the old 1% of the design).
Updates: MKT-DEC-017.

Decision:

`Seller fee = min(2% x sale price of the principal, 2% x outstanding principal)`

- **Accrued unpaid interest: "No fees"**, shown next to that component, not only in a tooltip. It is not part of the fee base, and the sale as a whole is not presented as fee-free.
- The buyer pays no fee. The seller fee is charged only when the sale completes. Principal price zero -> fee zero.
- Example: outstanding principal 10,000, principal price 10,200, accrued interest 100 -> the buyer pays 10,300; the capped fee is 200; the seller receives 10,100.
- Fee and net are shown before confirmation. Open listings take the new rule after edit/refresh; these listings and any needed reconfirmation are reconciled explicitly, without recalculating closed trades or silently changing accepted terms.
- Base, cap and interest exclusion are checked even though the current percentage is already 2%. Premium and fee are two separate rules, both 2%.

### U33-DEC-12: Fees and Platform Wording

Status: Approved (own variant).
Updates: PAY-DEC-006 (lender payment fee), PROD-DEC-009 / RISK-DEC-005 (recovery fee).

Decision:

- Investing, holding the account and ordinary repayments/administration are free at launch; the configurable fee on repayments stays zero. **No Banxum recovery fee for the investor.**
- Real, documented external costs (lawyer, court, enforcement) are claimed from the borrower under the contract/law. If they are not covered separately, they may be deducted from recovered amounts. Costs already paid are not deducted twice, and internal Banxum costs are not reclassified as external costs. Distribution order and shared costs follow the applicable rights/documents.
- The platform shows the gross recovered amount, the deducted costs and the net distributed to the Banxum balance. No promise of zero costs, and no separate debit of other investor money. A possible Banxum fee owed by the borrower needs its own basis and decision; no new fee is approved here.
- Resale follows U33-DEC-07; the daily penalty is removed (U33-DEC-04); FX is off (U33-DEC-33). No universal "0 fees" wording. A future repayment fee needs a decision and new terms, shown before agreement and reflected in projections, never retroactively. The contractual transposition of recovery stays to be checked, including cross-border.

## Group 7 - Credit File and Contracts

### U33-DEC-13: Acceptance of the Investment and the Assignment Document

Status: Approved (design with the new authentication). Validation open.
Supersedes: DOC-DEC-003 (no e-signature) for the post-closing assignment declaration; updates DOC-DEC-005.

Decision:

- The investor reviews, accepts and confirms **with the PIN only**; this **is not a QES**.
- At successful closing, one assignment declaration per investment is issued, signed with a **Swiss QES (ZertES)** by the authorized representative of the assigning entity, and stored in **Documents**, accessible to the investor.
- Banxum is the brand; for the Banxum -> investor assignment the legal entity is **Garanta Finanzgruppe AG**. The document identifies the exact parties and signatories. The accepted version, the operation and the confirmation time are recorded. The signed document must be real and downloadable; it is never shown as "signed" before the signature succeeds.

To validate: the contractual and signature chain (including resale), templates, QES integration, archiving and errors. A Banxum QES is not assumed to replace the consent/signature of the previous assignor, and QES is not introduced for the investor's simple confirmation.

### U33-DEC-14: Documents and Acceptance Checkboxes

Status: Approved (Vlad's platform, adapted).
Confirms: MKT-DEC-015, DOC-DEC-001.

Decision:

- Two clear acceptances, unchecked by default: **investment/assignment terms** and **risks**. Resale uses the seller-specific and buyer-specific agreements.
- Documents open before confirmation, with an identifiable version and later access. Vlad's materials are reused if they cover the rights, terms, costs, risks and required information, including confidentiality where it applies. No redundant checkboxes/PDFs just to copy the prototype, and no removal of required content to get two physical documents. The legal set and names are validated; QES stays separate (U33-DEC-13).

### U33-DEC-20: Credit File Content and Administration

Status: Approved (mixed administration, keeping the full approved depth and presentation).
Updates: DOC-DEC-004 / DOC-DEC-006 and the borrower story model.

Decision: the seven chapters stay: Summary, Borrower & business, Financials, Security, Loan terms, Checks & updates, Documents. Navigation, depth and document access stay; simpler administration does not justify a smaller file.

- **Structured data:** historical P&L and balance sheet, the available years/periods, sub-items, the four approved ratios (calculated) and debts explained from the documents. One source for figures; no invented financial data and no business scenarios/projections to fill gaps.
- **Texts and media through templates:** business explanation, intended use of funds, representative, quote and images when they exist, without a separate field for each sentence.
- **Securities and progress:** the structure of U33-DEC-21, checks/updates with source, date and result, the recovery stages of U33-DEC-22.
- **Library:** real documents with metadata for category, period/date, issuer, version, status and access; references lead to the same document.

Content is factual, with no ratings, opinions on the business or subjective assessments. The 16 demo files and PDFs show the standard; 9-12 PDFs per file is not a quota. In production, demo data, images/quotes and documents are replaced with real material, never presented as originals received from companies.

Implemented 2026-11-10 (Phase 17.4): `plan/13_documents_contracting_esign.md` DOC-DEC-004 / DOC-DEC-006 notes. The four ratios are the design's (equity / total assets, financial debt / equity, operating margin, interest coverage).

### U33-DEC-23: Missing Descriptive Fields

Status: Approved (design).

Decision: the borrower's city and number of employees (with the relevant period) are added; for the originator: founding year, city and sector. The admin manages them and the interface shows them when available. Values are not derived automatically from other texts, a missing value is not shown as zero, and an unknown value does not block publication by default.

### U33-DEC-24: Refinancing and Economic Rights on Originator Claims

Status: Approved (Vlad's mechanism, explained in the design). Clarifications open.
Confirms: PROD-DEC-013, MKT-DEC-022, MKT-DEC-025.

Decision:

- The split of interest and, where the contract provides it, of penalty interest with the originator stays, with **percentages set case by case**, no universal percentage. The rate, projections, schedule and first payment shown to the investor reflect only the investor's rights, not automatically the interest paid by the borrower.
- Loan terms show the actual percentages for the investor and the originator, for interest and, where it applies, penalty interest. The split and its effect on the first receipt are explained briefly before confirmation. Old/new refinancing terms and the base schedule/contract stay accessible in Loan terms; Summary identifies the refinancing factually.

Implemented 2026-11-10 (Phase 17.4), display part: Loan terms show the investor's and the originator's shares of interest and, where recorded, of penalty interest; the review step states the split in one line before confirmation. The first installment is explained only with the existing sentence until the open point below is clarified.

To clarify with Vlad: the first installment assigned to the originator (principal, interest, period, rights and effect on the investment price); no generic loss for the investor is approved. Penalties and their beneficiaries are treated separately, not as projected profit or a recovery fee. For originator claims, the existing mechanism excludes investor interest during funding; the exact contractual start date and the split of rights follow U33-DEC-10.

## Group 8 - Smart Invest, Saved Items and Notifications

### U33-DEC-17: Coming Soon and the Opening Alert

Status: Approved (design).

Decision:

- Projects can be visible before opening, with the planned date and an explicit request for an email notification. The admin manages the state and the opening; the alert fires at the real opening, not only when the date passes.
- No investments or reservations before opening, including in the backend. In Smart Invest, Coming soon is separate from available matches, and the open-investment counter does not include it. The opening alert is not duplicated with the Smart Invest alert. The public state stays consistent; opening does not reset the age of money (U33-DEC-03).

Implemented 2026-11-10 (Phase 17.4) for Direct loans: `plan/09_marketplace_investments.md` MKT-DEC-029. Loan Originator claims are an open point. Smart Invest does not list Coming soon matches yet (its matches are open loans only, so the counters already leave Coming soon out).

### U33-DEC-18: Save for Later

Status: Approved (design with automatic alerts).

Decision:

- The opportunity and, optionally, an explicitly chosen amount are saved in the account, available across devices and from Overview. Saving does not reserve money or places, does not check agreements and does not guarantee later availability. The minimum is not selected silently, and the "Closing soonest" sort is not changed to put saved items first.
- On return the platform checks the project state, the minimum, the project's available amount and the personal balance. An incompatible amount is explained, never changed or confirmed silently; a closed project does not become investable through a saved item.
- Approved alerts: automatic **7, 3 and 1 day** before closing, as in-platform notifications and email, not SMS/push. They are independent of marketing and of the Smart Invest pause.

Proposed details, to define with Vlad (not yet approved decisions): only future milestones after saving, no retroactive alerts; de-duplication per event/channel; stop when the item is removed or the project closes/is cancelled, and reschedule when the date changes; time of day and simultaneous operations.

Implemented 2026-11-10 (Phase 17.4) with the proposed details: `plan/09_marketplace_investments.md` MKT-DEC-030. The time of day is the daily job run; it and the proposed details are in the open questions of Phase 17.

### U33-DEC-19: Smart Invest

Status: Approved (final, mixed variant).
Supersedes: MKT-DEC-027 (batch placement); updates MKT-DEC-026 and COMMS-DEC-008.

Decision:

- **Individual confirmation only** for each investment, with the PIN; no batch approval, no discretionary buying, no reservation and no auto-checked agreement.
- The existing matching mechanism and one set of preferences are reused. Criteria: currency, minimum interest, maximum term, several security types, maximum LTV, repayment, country and originator. No ratings and no new purpose/refinancing filters. Setup/editing follows the five approved steps; when editing, the existing preferences are pre-filled and saved at the end. EUR/CHF and "No preference" stay, with coherent selections and no contradictions.
- The usual amount is optional and chosen explicitly. If it is missing, the minimum is not pre-filled. If it exists, it can prepare the amount; it is never raised silently. The usual amount and the balance do not exclude opportunities from matching; the impossibility of investing that amount is explained separately.
- **Pause:** keeps the preferences, stops Smart Invest alerts and removes the marks, counters and recommendations from Overview, Opportunities and the Smart Invest page. Opportunities stay accessible manually; history is not deleted. **Resume:** recalculates the current matches. Coming soon, saved items and notification channels follow U33-DEC-17, U33-DEC-18 and U33-DEC-30.

### U33-DEC-30: Notification Preferences

Status: Approved (Vlad's platform, adapted).
Updates: COMMS-DEC-002, COMMS-DEC-003, COMMS-DEC-008.

Decision:

- Service emails stay on: confirmations, repayments, documents, arrears/recoveries, returns and security. Controls that promise to switch them off individually are removed. No generic mandatory email for every new opportunity.
- Marketing is optional and unchecked at sign-up; the existing control is **Profile & Settings -> Notifications -> News from Banxum**. Marketing is separate from operational alerts and from the opportunity options the investor asked for. The legal classification and unsubscribe procedure are checked; not every message is assumed to be legally mandatory.
- Smart Invest has separate **in-platform / email** controls with real effects per channel, not a copy of one setting. Switching off a channel does not stop matching or service messages; Pause stops Smart Invest alerts on both channels. Financial/service history stays accessible; closing a banner does not delete the event.
- Syncing the marketing control and the email unsubscribe into one preference, and the alternative label "Marketing emails", are detail proposals, not approved renames.

## Group 9 - Localization

### U33-DEC-31: Languages of the Interface, Messages and Documents

Status: Approved (design).
Supersedes: DOC-DEC-002 for the interface and emails (contracts may stay English at first).

Decision: investor platform **EN / Swiss Standard German (de-CH)**; public site **EN / DE / FR**. Desktop/mobile and Light/Dark. English by default on the first visit; the choice is saved in the account. Changing the language keeps the page, the state and the entered data.

- All pages and secondary states, validations, errors, notifications, confirmations and backend emails are translated, including those not in the prototype. German uses "Sie", no "ß", a simple, formal and welcoming tone, consistent across devices.
- Admin-managed content has reviewed language variants: EN/de-CH in the platform and EN/DE/FR where it is public. Figures have one source; a missing translation is flagged in the available language, with no invented content.
- Source documents stay in their original language, clearly marked. Contracts can stay in English at first, announced before acceptance; a German legal translation needs a separate review. Signed PDFs are never machine-translated, and no prevailing legal language is assumed. The English demo PDFs are not real contracts.
- Continuity from the public DE site into the DE platform. From the public FR site the investor chooses EN/DE, with no claim of a French platform. The interface language does not promise human support in the same language.

Implemented 2026-11-10 (Phase 17.8, investor interface): `User.language` (`en` by default, `de-CH`) saved with `PATCH /api/v1/auth/preferences/display/` (audit `account.language_changed`) and shown in `/auth/me/`. The investor area (sign-in, registration, portal) switches between English and Deutsch from Preferences, the account menu and the sign-in header; the page, its state and the entered data stay. English is the default on the first visit; a choice made before sign-in, or `?lang=de|en` from the public site, is kept in the browser and saved in the account after sign-in; afterwards the account's language applies on every device. German texts: the design's approved dictionary (about 830 texts) plus drafted texts for everything else in the investor area (about 1,280, "Sie", no "ß"), loaded as a separate file; dates follow the language ("4. Okt. 2026"); a test checks that every investor-area text has a German entry. The number format stays independent of the language (U33-DEC-32). Waiting for answers (last slice of Phase 17): native review of the drafted German texts, backend emails, notifications and server messages in German, the public site in DE/FR, and language variants of admin-managed content. The public site and the admin console stay English until then.

### U33-DEC-32: Number Format and Time Zone

Status: Approved (mixed variant).

Decision:

- **European `1.234,56` by default; Swiss `1'234.56` as an alternative**, independent of language, with a saved preference. It applies to amounts/percentages in the interface, data entry, notifications/emails and newly generated personal reports. Source documents, signed contracts and documents already issued are not rewritten.
- Input recognizes unambiguous forms; ambiguous values follow the displayed/selected convention or ask for clarification, never guessing the amount. Formatting never changes values or calculations. The same value is checked up to confirmation in both formats, languages and devices.
- One time reference, **Europe/Zurich**, with automatic summer/winter time, not a fixed UTC+1/CET and no personal time-zone selector. Contractual due dates never move by a day by accident. The time zone is mentioned when a cut-off time matters, not next to every date.

Implemented 2026-11-10 (Phase 17.8): `User.number_format` (`european` by default, `swiss`), `PATCH /api/v1/auth/preferences/display/` (audit `account.number_format_changed`), shown in `/auth/me/`. The portal applies the account's choice on sign-in and saves a new choice in the account. Emails and the notification centre convert the canonical amounts ("CHF 1'234.50") and percentages ("7.40%") of each message to the recipient's format when shown (`localize_number_text`); a new account statement of one investor is written in that investor's format (`number_format_context`). Stored messages and issued documents are not rewritten. Dates and times stay Europe/Zurich.

## Group 10 - Public Area, Identity, Texts and Resources

### U33-DEC-34: Brand and Operator Identity

Status: Approved (mixed variant).
Confirms: the BANXUM/Garanta naming rule in `plan/00_index.md` and `plan/01_operating_model_compliance.md`.

Decision:

- The interface uses **Banxum**. A discreet and accessible identification: **"Banxum is a brand of Garanta Finanzgruppe AG"**, with the official address, UID and other official data in the legal area/footer; "Bern, Switzerland" alone is not a complete identification.
- Contracts, signatures and the beneficiary of transfers use the exact legal entity. About/Legal keep company facts, without deriving a banking status, affiliation, licence or guarantee from the brand. Final official data are checked; the operator is not hidden only inside personal contracts.

### U33-DEC-35: Service Promises

Status: Principle approved; operational confirmations needed.

Decision: texts describe the real service, not the prototype's promises at any cost. Bank payments are operated by hand by the team; deadlines are confirmed against that process.

| Area | Requirement / open confirmation |
| --- | --- |
| Withdrawals | Preference for **1-3 business days**, only after confirmation of operational capacity. Processing is separate from bank crediting. **No Banxum fee.** |
| Repayments | Go to the Banxum balance after receipt/reconciliation (U33-DEC-02). The real time is confirmed; "next business day" is not assumed. |
| Help | Form sent by email, with no new ticket system. Real confirmation of receipt, error/retry state, and page/project context without unnecessary sensitive data. No simulated sending. |
| Support | Hours, languages and owner to confirm; Europe/Zurich with summer time. No "shortly" or unassured deadline; receipt confirmation is separate from resolution. |
| Valuations/experts | Identify the author and the real document. No automatic claim that Banxum orders all valuations, that all are independent or externally checked. Use factual names such as "Valuation report". |

### U33-DEC-36: Contact Addresses

Status: Organization approved; actual addresses deferred.

Decision: few coherent channels for investors/support and partnerships. The domain and exact addresses are decided after they are created; the example addresses discussed earlier are not final. Interface, form recipients, senders and email replies are aligned.

### U33-DEC-37: Fonts, Icons and Demo Material

Status: Template purchased; licences to check.

Decision: check the proof of purchase, the licence and the resources actually included: fonts (including Archivo), Nioicon/other icons, images and portraits. It is assumed neither that all are licensed nor that all must be replaced. Material with sufficient rights is kept. Where rights are not confirmed or do not cover the real use/distribution, close visual alternatives with clear rights are chosen, keeping the approved identity. Demo images/quotes/documents do not automatically become production material; the origin and permissions of real ones are checked separately.

### U33-DEC-39: Public Functions That Already Exist in the Platform

Status: Preference for the current public area of the design; individual analysis deferred.

Decision:

- To evaluate later: **Projects/project history, Statistics, How it works, Help/FAQ, Guides, legal pages, newsletter and cookies**. For each, keep, integrate elsewhere or retire; neither removing all nor keeping all of the initial recommendations is approved.
- U33 public shows three projects and access to opportunities, without Vlad's full public catalogue/history. How it works and FAQ are integrated in Home; some legal texts are still demo. Without the catalogue/statistics there is less public visibility of the history; this implication is recorded for the decision, with no pages added automatically.
- Unique content is inventoried before anything is retired. Keeping the public design does not exempt texts from U33-DEC-02, U33-DEC-15 and U33-DEC-34/35. Real legal documents and cookie handling (based on the technologies actually used) are finalized separately; placeholders are never reused as if valid. Extra design is created after the individual choices, not in this round.

## Design To Complete After Reconciliation

Later work, with no implied visual approval. Approved components are reused, covering desktop/mobile, languages and Light/Dark.

| Area | Items | Work |
| --- | --- | --- |
| Access and profile | 1, 25-28 | Authentication/recovery, sessions, verified data, declarations, closure by request |
| Money and accounts | 2-5, 8 | Destination of receipts, returns, IBANs, removal of the old places/dynamic minimum |
| States and recovery | 9, 22, 29 | The seven cases of item 29 and the real recovery stages |
| Resale and costs | 6-7, 12 | Percentage, breakdown, "No fees" on interest, Help correction |
| Contracts and files | 13-14, 20-24 | Separate PIN/QES, acceptances, originator rights, data/securities; mixed administration does not reduce the credit file design |
| Opportunities and alerts | 15-19, 30, 38 | Optional participation, eligibility, Coming soon/Save/Smart Invest states and real notification controls |
| Localization and identity | 31-32, 34-37 | Shared texts/formats, operator, promises, contacts and resources with confirmed rights |
| Extra public pages | 39 | Only after the individual decision for the eight items |

## Clarifications For Implementation

Still to clarify, without changing the approved choices:

| Items | Clarification / owner |
| --- | --- |
| 1, 25-28 | Vlad and the responsible team: recovery/migration, revocations, history retention, declarations and the re-verification calendar |
| 3-5 | Vlad/operations: deadline counting, non-business days, failed return, holder verification and unidentified deposits |
| 8, 21, 38 | Legal/operations + Vlad: basis of the Swiss total, classification and proof of securities, eligibility controls |
| 10-11 | Vlad + contract documents: boundary dates, effective balances, rounding/allocation, separate penalties, custom schedules |
| 6-7, 12-14, 24 | Vlad/legal: active resale listings, external costs, assignment/QES and agreements, first installment/originator rights |
| 17-18, 30 | Vlad/operations: alert events and de-duplication, the details still proposed, preferences and unsubscribe implementation |
| 31-32, 35-37 | Team + Vlad: content/legal translations, format coverage, real deadlines, contacts and licences |
| 29, 39 | Eduard + design: the missing screens and the individual choices on public functions |
