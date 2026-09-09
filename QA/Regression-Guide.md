# BANXUM manual regression guide

Test the website as an investor and as an administrator. Follow the actions below and check the result after each story. Start with successful flows, then test more complicated situations, and finish with mistakes, limits and failures.

Reference release: f185460. Prepared 9 September 2026. Use the current deployed version in the run record. This is a test procedure, not a report of tests already passed.

## Before you start

### Use a safe test environment

Use staging or a dedicated local test environment. Do not declare invented deposits, repayments or bank transfers in a real-money environment. The production QA reset is a separate, explicitly approved maintenance operation, not part of this regression run.

Confirm with the environment owner that the accounts, balances, borrowers, documents and bank evidence are test data. Check whether email, SMS and identity verification use test providers or real providers. QA mode changes time; it does not by itself guarantee that external messages or provider calls are disabled. Only send to mailboxes and phone numbers controlled by the tester.

Do not use the website's fixture preview mode for acceptance testing. Preview screens can show a success message without saving anything. A valid test must persist after a reload and be visible from the other role's browser.

### Accounts and browser sessions

Use separate browser profiles for these identities. Two ordinary tabs share cookies and do not isolate accounts. Private windows may also share one private session.

| Name in this guide | Role and main job |
| --- | --- |
| Admin | Normal operations: borrowers, loans, deposits, payouts, repayments, tasks and reports. Use a regular admin account, not the superadmin, for these checks. |
| User 1 | Main investor; invests in direct and LO loans, receives repayments and sells a holding. |
| User 2 | Second investor; shares loan funding with User 1 and buys User 1's holding. |
| User 3 | Starts verified but empty. Used for empty states, insufficient funds, restrictions and competing purchases. |

These are three investor accounts and one regular Admin account. Registration and superadmin-only tests are outside this run. Borrowers and Loan Originators are company records, not additional login accounts. The Loan Originator does not have a website wallet or login.

Record which test email belongs to each role in your private run notes. Do not put passwords, codes, identity documents or real personal data in this folder or in Git. Use the same three accounts throughout the run. Do not create a fourth investor or change these natural-person accounts into company representatives.

### Files in this folder

- Regression-Guide.docx is the Word version of this guide. Regression-Guide.md is its editable source.
- resources/RUN-DATES.md gives the exact dates for the supplied CSVs.
- resources/lo-import-map.csv gives each upload's required form values, import date, payment reference and prerequisite file.
- resources/valid contains files expected to work in the stated situation.
- resources/invalid contains deliberately incorrect files. Never use them for a successful loan import.
- reference/direct-loans.csv gives direct-loan form entries. It is a worksheet, not an upload file.
- reference/bank-operations.csv gives synthetic amounts and references to type into admin forms. It is not a bank upload.
- reference/expected-lo-a.csv gives exact amounts for the main LO story before any secondary sale or other change.
- templates/results.csv and templates/bug-report.md are blank recording templates. Keep completed copies outside the repository.

The supplied dates start on 2026-09-09. For another start date, ask the environment owner to run the following from the project folder, using a NEW output folder:

```bash
python3 QA/prepare_resources.py --start-date 2026-10-01 --output /tmp/banxum-qa-2026-10-01
```

This only creates local CSVs. It does not contact the website or reset any data. Use the new RUN-DATES.md and map instead of the old resource folder. Use the QA clock date in Europe/Zurich, not the computer's local date. Do not change the device clock. Where a story says advance to a date, this is an environment-owner prerequisite, not a superadmin action for the tester. Pause that story until the owner confirms the date and jobs are ready.

### Starting data and how to repeat a test

Use the manual regression seed on staging, not the generic demo reset. It creates ten unfunded direct loans and ten unfunded LO loans. The private account mapping identifies the tester's Admin and three investor aliases. Admin remains a regular admin. The environment owner handles clock changes and seed restores outside the tester's cases. Never use production for this baseline.

| Account | Starting CHF | Starting EUR | Starting state |
| --- | --- | --- | --- |
| User 1 | 5,000,000.00 | 5,000,000.00 | Active, phone-verified, KYC-approved test investor |
| User 2 | 5,000,000.00 | 5,000,000.00 | Active, phone-verified, KYC-approved test investor |
| User 3 | 0.00 | 0.00 | Active and verified, with no money |
| Admin | No investor wallet | No investor wallet | Existing regular-admin permissions |

Each funded investor can cover any single seeded loan and several loans without help. The current whole catalogue's face principal is also below five million in each currency. A direct loan's funding still resolves after its deadline, even when fully subscribed; an LO round closes when its sellable capacity is filled. Do not advance time to a later loan's deadline before funding the earlier ones.

All three start without holdings, orders, listings, withdrawals, payout IBANs or Smart Invest rules. Seeded money is synthetic ledger money, not a deposit, and does not verify an IBAN. Newly created test identities are explicitly marked synthetic: no real SMS or Didit verification has been performed and no document acceptance is fabricated. Investor login still uses a real email magic link. Check provider delivery before testing. Existing account permissions and verification decisions are preserved rather than silently changed.

Keep User 3 empty for S06 and insufficient-funds cases. When a later story needs User 3 to buy, Admin first gives it just the required test deposit; restore before the next empty-account case. Tests of missing verification need an isolated User 3 compliance branch, not the default verified baseline. Preserved activity from earlier runs may appear as archived history; it must not contribute to current balances or holdings.

Create the two main loans before starting the timed stories:

- QA Direct Main: CHF 10,000, 12% annual interest, three monthly installments, amortizing principal and interest, 50% minimum subscription, loan start on the direct deadline in RUN-DATES.md. Collateral CHF 20,000. User 1 invests CHF 6,000; User 2 invests CHF 4,000.
- QA LO Main: EUR 10,000 original principal, 12% borrower coupon, 70% investor interest participation, 50% penalty participation, 10% skin in the game, EUR 1,000 minimum order. Use lo-a-01-publish.csv and its map values. Post-boundary principal is EUR 8,000; sellable principal is EUR 7,200. User 1 invests EUR 4,000; User 2 invests EUR 3,200.

Create separate copies for competing-purchase, prepayment, late/default, partial-funding and invalid-import tests. Do not apply mutually exclusive payment branches to the same loan.

The regression reset captures a repeatable seed snapshot automatically, before any manual test action. QA mode remains enabled at the seed clock date. Confirm its note says "Manual regression seed baseline" before starting. Finish access and setup stories S01 to S10, skipping the retired story IDs. Do not replace the seed snapshot after creating orders or receiving money.

Use this execution order so the date never needs to move backward:

1. Main successful branch: S11 to S27, then S31 to S34. Check RUN-DATES.md and process due payments in chronological order. Keep any other test loan current if you intend to trade it later.
2. Separate resale branch: restore the seed snapshot. Recreate the main loans using S09 and S10 and any deposit/IBAN prerequisites, repeat the needed funding/disbursement and LO boundary steps, then run S28 to S30. Repeat S31 document checks for those sales. Do not reuse an already-repaid main loan.
3. Complex and edge cases: restore the seed before each independent branch and sign in again. QA mode and its original seed clock stay enabled; do not capture a fresh snapshot. Create that branch's loans before advancing time and repeat only its prerequisites.

For a standalone seeded-loan close, restore first. User 1 funds a direct loan's full remaining amount; the owner prepares the date after that loan's inclusive deadline and Admin verifies the automatic close before recording disbursement. In a separate restored branch, User 2 buys an LO loan's full AVAILABLE principal, not the original face principal; verify immediate close and the later boundary payment. Restore again before partial-funding or insufficient-funds tests. A large wallet must not accidentally turn a partial-funding case into a fully funded case: enter the amounts specified in that story, not Maximum.

Some complex stories require a SMALLER wallet, old sources, or several specific lots (especially C06 to C10 and the insufficient-funds cases). Use empty User 3 for those money-source steps instead of a funded User 1, recording the role substitution. Admin adds only the story's required amounts. Ask the environment owner for aged-source fixtures where stated. Never change or delete journal rows by hand to reduce a seeded balance.

To reset: save evidence and ask the environment owner to restore the seed. No superadmin login is required from the tester. Sign in again after the owner confirms completion. Check User 1 and User 2 have exactly five million of each currency, User 3 has zero, the catalogue has 10 direct and 10 LO unfunded opportunities, and test-created loans and transactions have gone. Perform the same checks after a second restore. The regular Admin account cannot restore the database.

Save screenshots and results outside the database before restoring. Never assume a restored mutation still exists. Repeatable seed restores also reset the QA clock to its original date, so reuse the matching resource pack even if the real calendar moved. If the owner creates a NEW seed or applies database migrations, create a new matching resource pack and baseline; old snapshots cannot be restored across schema changes.

Revert restores the database, not emails already sent, bank movements or file/object storage. It can restore accounts and sessions to their earlier state. Coordinate with other testers because the QA clock and restore affect the whole environment.

### Simple rules to check throughout

- Keep CHF and EUR separate. Never add them into one money total without an explicit conversion.
- Money fields labelled minor units use cents: 100000 means 1,000.00. Rate fields labelled bps use hundredths of a percent: 1200 means 12%; 7000 means 70%.
- Loan interest rate is what the borrower pays annually. Investor yield is the investor-facing rate. On current LO loans it is coupon multiplied by interest participation, not a guaranteed realized return. The main LO example shows 12.00% and 8.40%.
- Direct funding resolves after the last inclusive funding date. At or above the published minimum it closes at the funded amount; below it the round cancels. An admin cannot choose a different result after the deadline.
- Current LO funding closes immediately when sellable capacity is filled. At the deadline any positive subscription closes; an empty round cancels. LO loans do not use the direct loan's 50% round threshold.
- LO holdings activate as part of successful close. No separate manual activation or borrower receipt is required. No investor interest is earned during funding. The first contractual installment after the funding window, called the boundary installment, belongs entirely to the LO.
- Every borrower payment pays due amounts in this order: Garanta legal costs and recovery fee, penalty, interest, principal. A higher tier may be zero, but it cannot be skipped when money is due there.
- A projection is not a received payment. A reserved order is not an invested holding. A requested withdrawal is not an executed bank transfer.
- Check balances, status, portfolio, documents, notification and admin evidence after each money action. Reload both browsers. Reopening a completed action must not repeat the money movement.

### Record a result

For each story record Pass, Fail, Blocked or Not applicable, plus the release, role, loan name, date, starting and ending balances, and a screenshot or short recording. A missing setup or provider sandbox is Blocked, not Pass. Use Not applicable only when the feature really is absent from the tested release and record why.

If a story fails, keep its reference and evidence. Do not keep submitting a financial form to see whether it eventually works. First check whether the original action already completed.

## Part One Successful everyday flows

### S01 Browse while logged out

1. User 3, logged out, opens the home page and Investment Opportunities. Open a loan preview and its login action.
2. Open Help and FAQ, expand questions, use search if offered, and open public terms links.
3. Use browser Back and reload a public page directly.

Expected: public pages work without a session. The user sees preview information, not another person's balances, full private borrower data or admin screens. Protected actions lead to login or onboarding, not an error page.

### S02 Verify the seeded accounts and balances

1. Admin opens Users and finds the three assigned aliases. User 1, User 2 and User 3 each sign in through their own magic link in separate browser profiles.
2. User 1 and User 2 each check CHF 5,000,000 and EUR 5,000,000 available. User 3 checks zero. Verify the displayed account identity in every browser.
3. Check there are no current holdings, orders, listings, withdrawals or Smart Invest rules. Confirm 10 direct and 10 LO unfunded seeded opportunities. Record the displayed QA date and the resource pack start date.

Expected: the exact seed is ready before testing. No registration is required. Admin has regular-admin permissions and no investor wallet. Historical activity retained from before a reset is clearly separate from current balances. These synthetic verified flags do not count as a real KYC/SMS test.

### S04 Log in and out as an investor

1. User 1 signs out, requests a magic link and opens the newest link from its mailbox.
2. Navigate between pages, reload, close and reopen the browser, then explicitly sign out.
3. User 2 logs in separately and checks the displayed account identity.

Expected: each valid link signs in the intended investor. Normal navigation does not lose the session. Sign out removes access to protected data. User 1 and User 2 never see each other's information.

### S05 Log in as Admin

1. Admin opens /admin, enters its email and password, receives an email code and completes login.
2. Admin opens Daily dashboard, Tasks, Users, Compliance, Finance ops, Loans and Reports.

Expected: the regular Admin can perform its own role's work without elevated permissions. Login-code delivery is checked in the actual test mailbox, not inferred from a success message.

### S06 Check an empty account

1. From the clean seed, User 3 opens Dashboard, My Portfolio, Secondary Market, Balances, FX, Documents and the notification bell without depositing or investing.
2. Open each tab and any widget expansion. Resize to a phone width.
3. Save evidence, then return to the agreed User 3 starting state for later tests.

Expected: meaningful empty states, zero rather than NaN or broken charts, no fake activity or holdings. Registration documents may already exist. Relevant setup actions remain usable. Widgets with no meaningful data are hidden or explain the empty state.

### S07 Read funding instructions and record a deposit

1. User 1 selects Add Funds from the header and from Balances. Switch between CHF and EUR and copy the payment reference and collection IBAN.
2. Admin opens Finance ops, Lender deposit. Select User 1 by its reference and enter an approved synthetic transfer, matching currency, dates, collection account and checksum-valid source IBAN. Use the bank worksheet.
3. User 1 reloads Balances and Activity. Repeat a small deposit for User 2 in the other currency.

Expected: instructions say to put the reference in bank payment details and explain allocation delays if omitted. Only the matched investor and currency are credited, exactly once. The source IBAN becomes a verified payout account. The balance source retains its received/value date.

### S08 Create a borrower with public and private data

1. Admin opens Loans and creates a borrower named QA Direct Borrower. Fill business classification, registered address and contact information; choose which are public.
2. Fill ownership, bank account notes, KYB/AML observations and financial risk with clearly marked private test text. Add optional financial fields where available.
3. Save and reopen the borrower. Later compare the investor detail page after publishing S09.

Expected: saved values survive reload. Only selected public fields are visible to investors. Internal notes stay internal. Missing optional data is hidden rather than shown as misleading zero values. Offline company checks do not require an in-platform KYC journey.

### S09 Create and publish the main direct loan

1. Admin creates QA Direct Main using the starting values above and reference/direct-loans.csv. Save as a draft, reopen it and change a harmless summary sentence.
2. Choose Manage on that exact row, then Publish. Review the read-only repayment schedule, first payment date and totals before confirming.
3. User 1 opens the published opportunity. Compare name, borrower, currency, amount, deadline, repayment type, collateral and rate with Admin.

Expected: the draft is not public until publication. First payment is one month after loan start. Principal totals equal CHF 10,000; the final outstanding balance is zero. Admin shows separate Loan interest rate and Investor yield, both 12.00% p.a. for this direct loan.

### S10 Create and publish the main LO loan

1. Admin creates or selects an active test Loan Originator with its public name and approved external settlement details. No LO login or wallet is created.
2. Create QA LO Main. Use resources/valid/lo-a-01-publish.csv and ALL form values from lo-import-map.csv. Use EUR and a clearly anonymized public final-borrower name; keep legal identity private.
3. Review imported schedule, boundary date, EUR 8,000 post-boundary principal, 70% interest participation, 50% penalty participation and 10% retention. Publish.

Expected: EUR 7,200 is available to investors. Admin shows 12.00% loan interest and 8.40% investor yield. Investor detail identifies the LO, delayed interest entitlement and retained share without revealing private borrower identity or internal settlement details.

### S11 Browse loan details and projections

1. User 1 opens both main loans from Investment Opportunities, then follows the full detail link.
2. Inspect rates, minimum order, funding progress, collateral/LTV, term, repayment type, risk, borrower information and available documents. Change the proposed investment amount where allowed.
3. Open schedules and total rows wherever offered. Compare them with Admin's loan schedule.

Expected: correct loan name throughout. Investor projections follow the amount and currency selected, while a full-loan schedule remains clearly labelled as the whole loan. Running outstanding balances are not added together in a totals row. No promised automatic reinvestment or guaranteed returns.

### S12 Filter and sort investment opportunities

1. User 1 switches Focused and Detailed views. Sort through the dropdown and each supported table heading, in both directions, then restore the default sort.
2. Try yield, term, originator/source, currency, collateral, risk, purpose and other filters actually offered. Combine filters, remove individual tokens and clear all.
3. Make a no-match selection, then clear it. Open a matched loan and return.

Expected: rows and match counts agree with all active filters. Currency is shown beside amounts; detailed information remains available. Sorting does not silently clear filters. No-match is distinct from a load failure. Tooltip explanations open on hover and keyboard focus.

### S13 Set up Smart Invest

1. User 1 opens Smart Invest with no active rule. Complete collateral, currency, optional minimum yield, optional maximum term and review. Choose at least one effective condition.
2. Save, reload, and compare matches in Smart Invest and the dashboard widget.
3. From Investment Opportunities choose different filters and Save Smart Filters. Confirm they are saved and already applied on Smart Invest. Deactivate, then set a new rule.

Expected: one active rule only. Deactivation clears it instead of restoring an older preset. Search text, sort and visual mode are not saved criteria. Saving a rule never spends money. No repayment/reinvestment question appears in the wizard.

### S14 Receive a new matching loan alert

1. User 1 keeps an active EUR-only rule; User 2 sets a CHF-only rule. Both have financial access. Record which existing loans already match.
2. Admin publishes a NEW EUR test opportunity matching User 1's conditions. Check User 1's notification and controlled mailbox; check User 2 as well.
3. Admin updates a harmless field or reruns the supported notification job. User 1 changes the rule to include an already-open loan.

Expected: one alert for User 1 for the new matching opportunity, none for User 2's non-match. Ordinary edits and rule changes do not backfill or repeat first-publication alerts. Transactional match alerts do not depend on marketing consent.

### S15 Fund a direct loan with two users

1. User 1 opens QA Direct Main, enters CHF 6,000, reviews terms and risk checks, requests/receives the required code and confirms.
2. User 2 places CHF 4,000 on the same loan through the same flow.
3. Both users open My Portfolio, Orders. Admin checks progress and the order records. Reload before continuing.

Expected: CHF 10,000 is reserved in total, not paid twice or shown as received repayment. The loan is full but direct funding still resolves after its published deadline. Orders show allocated balance; they are not yet active loan holdings. Investors cannot cancel their orders themselves.

### S16 Subscribe to an LO loan with two users

1. User 1 subscribes EUR 4,000 to QA LO Main through the ordinary order review. Observe the reservation before the round is full.
2. User 2 subscribes EUR 3,200, completing its EUR 7,200 sellable amount.
3. Both users open their holdings and schedules. Admin opens the LO record and Finance ops settlement queue.

Expected: the full round closes and activates automatically. User 1 owns EUR 4,000 and User 2 EUR 3,200 of post-boundary principal. No Awaiting activation step or invented borrower payment is needed. EUR 7,200 becomes LO payable; EUR 800 remains LO-owned. Boundary-payment investor projection is zero.

### S17 Place a reviewed batch investment

1. On a separate set of open loans, User 1 activates a broad Smart Invest rule and selects at least two LO loans and one direct loan in the dashboard widget. Include CHF and EUR.
2. Review every amount and each currency subtotal. Accept the listed terms, use the one requested confirmation code and submit once.
3. Check every selected order and both currency balances after reload.

Expected: multiple current LO loans are selectable, subject to balance and capacity. The exact reviewed items reserve funds together. There is no combined CHF-plus-EUR total and no unselected investment. These current LO orders do not use the legacy five-minute quote purchase flow.

### S18 Check portfolio tables and widgets

1. User 1 opens My Portfolio, My loans, Activity and Orders. Compare rows with the actions already completed and sort supported headings.
2. Open order-status explanations and copy icons. Open each widget, including its full detail, then switch tabs.
3. Repeat on a wide desktop and a phone.

Expected: widgets keep the same data regardless of tab. Two widgets fit per row when space permits; expanded detail opens below that row. Tables do not cause a few-pixel page wobble. Order and loan copy icons copy the correct IDs. Pending direct orders are not counted as holdings.

### S19 Convert CHF and EUR

1. On a weekday with valid test-provider rates, User 1 opens FX, selects CHF to EUR and enters a small amount. Review rate, fee and resulting amount.
2. Select Convert, review the fresh quote and countdown, accept terms, enter the email code and confirm.
3. Check both balances and conversion history. Repeat EUR to CHF with User 2.

Expected: source is debited and target credited once using the reviewed quote and fee. Only CHF and EUR appear. History shows correct amounts and direction. FX does not reset the age of the money. No automatic incoming-payment conversion option appears.

### S20 Verify an additional payout account

1. User 1 opens Settings, Payout accounts, Add/update IBAN. Submit a second valid test IBAN with the email code.
2. Admin checks Tasks and the pending Finance ops table, finds the request and verifies the new IBAN through Payout instruction.
3. User 1 reloads its payout accounts and opens withdrawal options.

Expected: the additional account starts pending and creates admin work. After verification it becomes usable. The deposit-verified account stays usable; adding a second account does not replace it silently. Each IBAN belongs to the intended user and currency.

### S21 Request and execute a withdrawal

1. User 1 withdraws CHF 250 to a verified test account, reviews the details and confirms with the email code.
2. Admin opens the withdrawal task side-panel, reviews its owner, amount and destination, enters synthetic execution evidence and finalizes.
3. User 1 checks status, available balance, activity and notification. Admin checks Finance ops and the task queue.

Expected: requested money is reserved and cannot be spent again. Finalization changes Requested to Finalized without a second debit. The task leaves the pending queue. The task panel has the actual execution form, not a message saying the action will be added later.

### S22 Work the admin queues

1. Admin opens Daily dashboard and checks counters against Tasks, Finance ops and Loans.
2. Use available queue filters, search, refresh, assignment and task-detail actions. Open a known payout request and a known withdrawal.
3. Complete the underlying operation and refresh all related views.

Expected: owner, currency, amount, status and due date are consistent. Completed work disappears from pending lists without losing its history. Manually marking a task complete must not pretend that an unexecuted payment occurred. Empty queues are clearly empty.

### S23 Resolve direct funding and disburse

1. Prerequisite: ask the environment owner to prepare the direct resolution date in RUN-DATES.md, after the final subscription date. Admin then checks the resulting loan state.
2. Admin checks QA Direct Main: it is Funded and awaits disbursement. Open Manage, Borrower disbursement; review payout and fee and enter the collection account and bank evidence.
3. Finalize the synthetic disbursement. Users 1 and 2 reopen their holdings.

Expected: close creates the funded holdings once. Disbursement then makes the direct loan Active. Payout plus fee clears the full borrower payable. At a 2% configured success fee, CHF 9,800 goes to the borrower and CHF 200 to Garanta. Use the configured fee if different.

### S24 Record the LO boundary receipt

1. Advance to the LO boundary date. Admin opens QA LO Main, Record repayment, and uploads lo-a-02-boundary-paid.csv.
2. Use the map's as-of date and QA-BOUNDARY-1 reference. Enter matching bank value date, collection account, payer and evidence, then confirm.
3. Users 1 and 2 check balances and schedules. Admin checks the LO payable and receipt history.

Expected: Garanta receives EUR 2,100. All EUR 2,000 principal and EUR 100 interest belong to the LO; neither investor receives this installment. Existing investor holdings remain EUR 4,000 and EUR 3,200. The real receipt does not activate a second holding.

### S25 Record a regular direct installment

1. Advance to QA Direct Main's first due date, without passing the LO second-payment date unnecessarily. Admin opens Manage, Record borrower repayment with Repayment in advance unchecked.
2. Review the fixed next installment amount. Enter payer, collection account, booking/value dates and unique bank/payment evidence. Confirm once.
3. Users 1 and 2 check balance credits, principal reduction, paid schedule row, activity and repayment email.

Expected: the borrower receipt is distributed according to their 60% and 40% ownership, subject to cents rounding. Due interest is paid before principal. Both views agree with Admin. Past paid rows remain visible; future projections and totals update.

### S26 Record an LO installment and check the split

1. Advance to the LO second-payment date. Admin uploads lo-a-03-next-paid.csv with QA-REGULAR-2 and the exact mapped date.
2. Review investor credits and money owed to the LO, then confirm. Neither investor has sold or added to this main test holding.
3. Compare each result with reference/expected-lo-a.csv and the full admin schedule.

Expected: EUR 4,080 received. User 1 gets EUR 2,028: principal 2,000 and interest 28. User 2 gets EUR 1,622.40: principal 1,600 and interest 22.40. LO payable is EUR 429.60. Outstanding is now EUR 2,000, EUR 1,600 and EUR 400 respectively. The admin schedule retains the LO amount.

### S27 Settle money owed to the Loan Originator

1. Admin opens Finance ops, Loan Originator settlement queue. Check the grouping by originator and currency and distinguish funding proceeds from borrower-payment proceeds.
2. Review all payable items in one selected batch. Enter the approved synthetic bank execution and confirm settlement.
3. Reopen the queue and check bank records, report and audit history.

Expected: the batch is settled once and its payable clears exactly. No investor wallet is charged for this external payment. Other originators/currencies remain unchanged. Settling a batch does not create extra investor holdings or repayment credits.

### S28 List and edit a direct holding

1. Use a separate active direct-loan holding for User 1. From its portfolio detail choose List on secondary market.
2. Confirm navigation to Sell a holding. Set a 1% premium, inspect fees, principal, rate, LTV and both schedules. Confirm listing data first; then complete email verification and publish.
3. Edit the listing with fresh terms/code, then cancel it. Check the Sell a holding row, portfolio Listed label and activity filters.

Expected: opening or editing the first review step does not send a code prematurely. One open listing per holding. Edit and Cancel replace List while open. Cancellation leaves the holding owned by User 1 and removes it from buyers' view.

### S29 Buy another investor's direct holding

1. User 1 republishes the separate holding. User 2 opens it in For Sale Now without requesting a code yet; review principal, price, accrued interest, buyer fee and schedule.
2. User 2 chooses to buy, accepts terms, explicitly requests its email code and confirms.
3. Check both users' holdings, balances, documents and Secondary Market Activity. User 3 must not see either user's private activity.

Expected: the whole holding transfers once. Seller proceeds and buyer cost match the displayed price, accrued interest and fees. Accrued interest is compensated to the seller at settlement; later ownership and component rights belong to the buyer. The sold listing is not purchasable again.

### S30 Sell and buy an LO holding

1. In a separate copy of the LO scenario, User 1 lists an active LO holding at par or a 1% discount after its boundary date.
2. User 2 buys it with the ordinary secondary-market review and code.
3. Admin records the next valid LO payment for that separate loan. Compare User 2's credit with its acquired rights.

Expected: principal and the declared interest/penalty participation move together. Private original acquisition economics are not revealed. User 1 receives no new installment on the sold holding; User 2 receives the applicable future share. Main LO-A arithmetic tests remain untouched.

### S31 Read accepted documents and statements

1. User 1 opens Documents and filters registration, direct orders, LO orders, secondary activity and other available categories. Download relevant PDFs and each offered CSV/ZIP.
2. Check full terms text, name, amount/currency, human-readable loan identity, version and acceptance evidence. Open an account statement and annual tax-information document.
3. Admin opens Users, User 1's accepted documents, and generates the same agreement.

Expected: files open and are not blank receipt-only PDFs. Accepted historical terms and identities remain correct. LO documents are identifiable as LO transactions. Ordinary legal PDFs are not automatically attached to transactional emails. Admin sees the same accepted evidence, not newly invented consent.

### S32 Check notifications settings and help

1. User 1 opens the header bell and its notification list, follows a loan/payment link, marks notices read and reloads.
2. In Settings, change optional marketing consent, reload, inspect profile/verification/payout details and open Help and FAQ.
3. Check User 2 is unaffected and that a later transactional notice still reaches User 1.

Expected: read status persists only for that user. Marketing is optional; transactional notices remain enabled. No duplicate Notifications sidebar item. Support links work without pretending there is an in-app support-ticket flow. Profile name/email changes direct the user to support.

### S33 Generate admin reports and review audit evidence

1. Admin opens Reports. Generate supported CSV, PDF and ZIP outputs for a period containing the tested deposits, investments, disbursement, LO payments, FX and withdrawals.
2. Compare redacted and full modes, inspect dates, currencies, loan/product identifiers, originator payable and bank reconciliation figures. Open every produced file.
3. In the audit list find one investor action and one admin action by copied reference and time.

Expected: exported totals reconcile to the tested operations, not displayed market values. Redacted output does not disclose full private identity. Actor attribution is correct. A generated file has the advertised format and non-empty meaningful content. Unsupported type/format combinations give a clear error, not a corrupt file.

### S34 Finish a loan

1. Admin records remaining direct installments on their due dates and the LO final installment on its mapped date, in chronological order across both loans. For the LO receipt upload lo-a-04-final-paid.csv with QA-FINAL-3; do not first advance beyond it to the later direct maturity.
2. Check final investor credits and any remaining originator payable, then settle that payable separately.
3. Users open completed-loan history, full schedule, documents and activity.

Expected: the loan is Repaid with zero remaining principal, without losing history. The main LO final payment credits User 1 EUR 2,014 and User 2 EUR 1,611.20; EUR 414.80 is LO payable. A completed holding cannot remain available for a new secondary sale.

## Part Two More complex flows

Start each independent branch from the exact seed, then repeat only its prerequisites. Do not reuse a damaged or already-repaid loan. The tester acts only as regular Admin and User 1 to User 3.

### C01 Close a partially funded direct loan

1. Admin publishes a new EUR 10,000 direct loan with a 50% minimum. User 1 allocates EUR 3,000 and User 2 EUR 2,000 before its deadline.
2. Advance to the following date and let the funding resolver run. Do not manually choose a partial-close amount.
3. Admin checks the new principal and schedule; both investors check orders, holdings and notices. Disburse using the reduced amount.

Expected: the exact 50% threshold qualifies. Principal becomes EUR 5,000, with a regenerated schedule using the same rate and term. Neither investor is charged extra. The success fee and borrower payout use the actually funded amount.

Repeat with QA Direct Custom Minimum from the worksheet: 75% is the published threshold for that separate loan. EUR/CHF amounts remain in the currency shown in the worksheet. Exactly 75% closes; just below it cancels. The default 50% must not overwrite the declared 75%.

### C02 Cancel an underfunded or empty direct round

1. Repeat with only EUR 4,000 allocated against EUR 10,000 at 50%. In a second loan allocate nothing.
2. Advance beyond both deadlines, then inspect User 1's sources, Orders and Admin's loan state.
3. Try resolving the same rounds again through the supported scan.

Expected: both cancel automatically. Reserved amounts return once to their original balance sources and original deadlines. Allocated orders become Balance released; unallocated pending intents become Not invested. Nothing becomes a holding.

### C03 Resolve a partially subscribed LO round

1. Publish a separate copy of the LO-A draft. User 1 subscribes EUR 1,000; leave the rest unfilled. Publish a second empty LO round.
2. Advance beyond the mapped LO deadline and check the lifecycle job results.
3. Inspect User 1's holding and LO payable. Check the empty round separately.

Expected: the positive EUR 1,000 round activates despite being below 50%. Only EUR 1,000 becomes investor principal and LO funding payable. The empty round cancels. There is no admin activation decision or direct-loan minimum threshold on the LO round.

### C04 Repair a failed funding close

1. On an isolated subscribed direct loan or LO round, have the environment owner prepare a controlled close failure, such as a documented explicit hold. Do not damage the database manually.
2. Advance beyond the deadline. Admin checks that the opportunity is hidden, funds remain reserved, and an urgent task and operations email exist.
3. Remove the approved test cause through its supported process, then rerun the resolver or wait for its retry. Repeat for the other product.

Expected: no partial holdings or partial settlement from the failed attempt. Retry applies the original published outcome exactly once. No option lets Admin choose a lower threshold or cancel a qualified failed round instead. Missing or expired optional company KYB alone is not this failure condition.

### C05 Cancel before the deadline and release an order

1. Admin publishes a separate direct loan. User 1 allocates funds. Before its deadline, Admin uses the supported Release order balance action with a reason.
2. On another still-open round, Admin cancels funding with the required explanation and investor message. Test the LO-specific cancellation on a separate paused/open LO round before its deadline.
3. Compare account sources, orders, notices and audit evidence before and after.

Expected: no investor self-cancel action appears. Released funds preserve their original age. Cancelled opportunities disappear. After the deadline, discretionary release/cancellation cannot override a published funding outcome.

### C06 Receive a bank-funded pending order

1. If the release exposes bank-funded order entry, User 1 places an intent without allocating an existing balance and records the order/reference.
2. Admin records the approved matching incoming transfer and validates it through the supported allocation workflow.
3. Repeat with an amount exceeding remaining capacity, then with insufficient received funds.

Expected: an unpaid intent does not reserve capacity. Validated funds allocate only within capacity. Excess/refund work is visible and auditable; nothing vanishes or overfunds the loan. If entry/validation is API-only, an environment owner must prepare it and the tester verifies the resulting UI; do not invent an admin button.

### C07 Match old money to short funding windows

1. Use an approved aged-balance fixture for User 1 with less than 30 days left before its withdrawal deadline. Record that exact source deadline.
2. Try a loan whose final subscription date is before the source's deadline, then one extending beyond it. Repeat for a direct and an LO loan.
3. Try sources on both sides of the exact deadline boundary. Use the server's source dates, not only rounded days shown in a widget.

Expected: short enough windows can use the older source; longer ones cannot. The source withdrawal-deadline date must be later than the last inclusive subscription date. No blanket day-30 rejection, and no 60-day deadline extension.

### C08 Use several balance sources and preserve their age

1. Admin prepares two User 1 deposits with different valid dates. User 1 makes an investment or FX conversion that consumes both, oldest eligible source first.
2. Check the remaining source amounts. For FX, inspect the target source's deadline.
3. In a separate pre-deadline cancellation branch, release the allocated order and inspect restored sources.

Expected: no source is consumed twice. FX inherits the earliest consumed deadline; order release restores source lineage and original dates. Available money and reserved money reconcile separately in each currency.

### C09 Cancel a withdrawal and use the other verified IBAN

1. User 1 requests a withdrawal. Before bank execution, Admin cancels it with a reason from its task or Finance ops form.
2. User 1 requests another withdrawal using the additional verified IBAN from S20. Admin executes this one.
3. Check both records and the original deposit-verified IBAN.

Expected: cancelled money is released once with original ageing, and the cancellation remains visible. The second withdrawal uses the explicitly selected destination. Neither verification nor cancellation silently disables other verified accounts.

### C10 Process the day sixty return and missing IBAN case

1. In one isolated snapshot give User 1 an idle source and verified payout IBAN. Give User 2 an idle source with no usable IBAN.
2. Advance through reminder dates 25, 46, 53, 58, 59 and 60, inspecting notifications and scheduled-job results at each checkpoint.
3. At the deadline Admin processes User 1's forced-withdrawal task. User 2 adds an IBAN, Admin verifies it and resolves the overdue return.

Expected: User 1 gets a forced withdrawal request, not fictional automatic bank execution. User 2's applicable financial actions freeze while read-only information and the IBAN fix remain accessible. Configured penalties never exceed the remaining overdue balance or make it negative. Ageing reminders are notifications, not the old general dashboard warning panel.

### C11 Make a direct repayment in advance

1. After disbursement, advance partway through a direct interest period. Admin selects Repayment in advance, enters the actual test value date and an amount larger than interest due but below full payoff.
2. Inspect the allocation preview and revised future schedule; cancel once to confirm nothing was written. Reopen and confirm.
3. On the same value date preview another advance payment. Compare elapsed days and already-paid interest. Then test a later-day payment in a separate branch.

Expected: only due and elapsed interest is charged, not a whole future period. Same-date payment does not charge the same elapsed interest twice. History includes the advance receipt and earlier paid rows; future principal and interest recalculate without changing history. Full periods and stub periods follow the configured convention, not an assumed 30-day month.

### C12 Record an early timely installment

1. Admin leaves Repayment in advance unchecked and uses the normal fixed installment amount, with value date more than one day before it is due.
2. Read the warning explaining that this charges full scheduled interest and that a true prepayment belongs in the advance flow. Cancel, then repeat and explicitly confirm.
3. On another direct loan, use a value date just one day early.

Expected: the far-early timely payment requires explicit confirmation, not silent treatment as a prepayment. The ordinary one-day-early case follows the supported timely-payment rule. Do not expect this direct-loan confirmation override to apply to LO CSV imports.

### C13 Replace an LO schedule after a prepayment

1. Start from a separate LO-A copy that has recorded file 02, but NOT file 03. Advance to the alternative date in RUN-DATES.md.
2. Admin uploads lo-a-05-advance-alternative.csv and uses QA-ADVANCE-1. Compare the total and interest with dates.json before confirming.
3. Check both investors, retained principal, LO payable, full history and future projections.

Expected: one EUR 1,000 principal reduction plus the mapped accrued interest. Prior boundary receipt remains unchanged. The current full schedule includes actual payment history and the revised future schedule, not two copies of old future obligations. All owners' principal still adds up to the underlying loan.

### C14 Reprice a listing when principal is repaid

1. User 1 lists a separate direct holding at 1% premium. Record its principal and displayed price. User 2 opens the buy modal but does not confirm yet.
2. Admin records a regular principal repayment. Then repeat with an advance payment in another branch. Refresh seller and buyer views.
3. Repeat with a separate LO holding at 1% discount using valid replacement imports. Later repay the holding fully.

Expected: price follows the new outstanding principal while preserving the agreed premium/discount percentage. Fees, accrued interest and schedules refresh. Stale buyer review cannot silently purchase different economics. Full payoff removes the zero-principal listing. Repayment email mentions repricing only for an active unsold listing.

### C15 Move a direct loan through late and default

1. On an active direct loan, leave an installment unpaid. Advance to 4, 5, 15 and 16 days past its due date and run/check servicing jobs.
2. Admin checks risk tasks and publishes a public loan note without email, then an email-only update, then both on separate notes.
3. Users 1 and 2 inspect status, days past due, notices and public notes.

Expected: current thresholds are Late at 5 days and Defaulted at 16. Arrears are visible before/after the transition as appropriate. Internal notes stay private, and communication reaches affected holders only. Do not treat uncollected projected interest as a received credit.

### C16 Recover a defaulted direct loan

1. Admin uses a separate defaulted direct loan and its recovery form. Set a synthetic gross receipt, external deductions, legal costs/recovery fee and documented unpaid penalty and interest.
2. Try a receipt too small to reach principal, then a larger one in another branch. Review the split and confirm.
3. Users inspect recovery credits and loan history. Admin checks bank cash, retained costs, distributions and reports.

Expected: allocation is costs/fee, penalty, interest, principal in that order. External deductions are not counted as cash received twice. Credits plus retained costs reconcile to actual received money. A defaulted claim does not continue showing a reliable ordinary repayment projection as though it were performing.

### C17 Check the same waterfall on an LO loan

1. Create a separate loan with lo-waterfall-01-publish.csv, using the LO-A settings. Fill it with User 1 EUR 4,000 and User 2 EUR 3,200.
2. Record its boundary with lo-waterfall-02-boundary-paid.csv, then the next receipt with lo-waterfall-03-next-paid.csv on the mapped dates.
3. Compare the split with reference/expected-lo-a.csv's waterfall branch. Inspect retained ownership after repayment.

Expected: EUR 4,110 pays Garanta EUR 10 first, then EUR 20 penalty, EUR 80 interest and EUR 4,000 principal. User 1 receives EUR 2,033, User 2 EUR 1,626.40 and the LO EUR 440.60. The declared participation is applied to each investor's proportional components, not to the whole payment twice.

### C18 Approve or reject a nonstandard secondary listing

1. Use an eligible late/defaulted DIRECT holding. User 1 submits a listing request; User 2 checks that it is not yet public.
2. Admin rejects it with a reason. In a separate request, Admin approves it with public disclosure. User 2 must accept the extra risk acknowledgement before purchase.
3. Repeat an edit after approval and test Admin removal. Separately try listing a late/defaulted current LO holding.

Expected: nonstandard direct listings require approval and clear risk disclosure; an edit returns them to review when required. Removed/rejected listings cannot sell. Current nonperforming LO holdings remain blocked, rather than borrowing the direct-loan approval exception.

### C19 Reconcile external FX and bank balances

1. Users 1 and 2 make opposite eligible FX conversions. Admin queries the period's internal currency deltas.
2. Record approved synthetic external FX sold/bought amounts and evidence. Inspect actual rate, residual delta and gain/loss.
3. Enter a matching reconciliation snapshot, then a deliberately mismatching one in a separate branch.

Expected: investor conversions are not executed again by external settlement. Reports distinguish internal rates, external amounts and residual differences. A mismatch appears as operational work; a matching snapshot reconciles. Both currencies remain separate.

### C22 Restrict reactivate and close an account

1. Admin restricts User 3 with a reason; test an existing session and a fresh magic link. Repeat with Locked in another branch.
2. Admin restores the permitted active status and verifies onboarding requirements still apply.
3. On a fully clean User 3 branch request closure through support and close via account controls. If privacy pseudonymization is exposed/configured, test it only with approved synthetic data and a restorable snapshot.

Expected: Restricted and Locked currently block login and money actions. Reactivation does not bypass phone/KYC requirements. Closure succeeds only without balances, active holdings, pending orders or other obligations; retained documents/audit evidence are not deleted. Offline identity recovery is not an ordinary UI decrypt button.


### C24 Verify late LO settlement tasks

1. On a separate activated LO loan, leave a payable batch unsettled. Record the oldest payable date.
2. Advance to day 3, day 5 and the next day, checking Tasks and the settlement queue.
3. Admin settles the full selected batch and refreshes overdue work.

Expected: tasks start at day 3 and escalate after day 5 under current policy. Principal-sale proceeds and later servicing proceeds are separately traceable. Completed settlement clears pending work without erasing its history or charging the investor again.

### C25 Test all supported repayment shapes

1. Admin creates separate LO drafts using every lo-type file in resources/valid. Choose the EXACT repayment type and interest-only months in the map. LO-A already covers amortizing principal and interest.
2. For direct loans create the corresponding supported types; use the environment owner's prepared setup if the admin form lacks an interest-only-period field.
3. Compare schedule pattern, date sequence, first payment, principal/interest totals and final zero principal. For each type record one regular and one advance receipt using prepared evidence or the direct preview.

Expected: equal installments are approximately level, declining-principal installments reduce outstanding, bullets keep principal until the end, and interest-only periods do not repay principal. Read-only projections, full schedules and admin previews agree. No new refinancing loan is created through the retired workflow.


## Part Three Edge cases and failures

Use fresh copies or restore as needed. For rejected money actions always compare before/after balances, orders, holdings and bank records: none should change accidentally.

### E01 Expired used and invalid login links

1. User 1 opens an expired link, then a previously used link, then a link with an invalid token in an approved test session.
2. From each error screen request a new email and complete login using the newest valid link.
3. Check the resend button immediately, after reload and after 60 seconds. Try Login from another page after an expiry.

Expected: an understandable invalid/expired message and a recovery path. No permanent Check your inbox loop. The resend cooldown counts down and prevents repeat sends until allowed. An old link never logs in another account.

### E02 Incorrect expired and reused email codes

1. For admin login, withdrawal, IBAN change, FX, investment, batch investment and secondary listing/purchase, try a wrong code in separate branches.
2. Test an expired code, a code for another action and reuse after a successful action. Confirm the configured attempt limit, currently three, in an isolated challenge.
3. Request a fresh code and recover. Check the cooldown whenever an automatic send occurs, and close a modal without submitting.

Expected: wrong attempts do not move money or accept a transaction. Codes are scoped and single-use. Current defaults are ten-minute expiry and 60-second resend cooldown; verify deployed settings. Opening a secondary buy modal never sends a code by itself. A code consumed before a later business-rule rejection may require requesting a new one.


### E04 Existing account compliance restrictions

1. From the seed, Admin reopens User 3's KYC case for review using the supported Compliance action and records a test reason.
2. User 3 reloads its existing session and tries financial page URLs and actions during review.
3. Admin records an approval with a clearly synthetic test reason. User 3 reloads and verifies access returns. Request a seed reset before another independent case.

Expected: blocked users cannot get balances, full private loan information or money actions merely by typing a URL. Clear status and next steps replace generic errors. Completing one required step does not bypass the others. Provider-unavailable cases do not appear approved.

### E05 Invalid bank details and duplicate deposits

1. Admin tries a deposit with blank source IBAN, bad checksum, mismatched currency/collection account, missing amount or unusable bank dates.
2. Use a valid formatted IBAN with spaces/lowercase where accepted. Record a valid test deposit, then double-submit or repeat the same supported request.
3. Test a wrong/missing investor reference with the approved unmatched-payment setup.

Expected: invalid instructions are rejected or routed to review without crediting the wrong account. Valid IBANs normalize consistently. One bank movement creates one credit under the duplicate-detection rules. If changing the reference creates a genuinely new declaration, do not assume it is automatically a duplicate.

### E06 Withdrawal and IBAN limits

1. User 3, with no verified IBAN, attempts withdrawal. User 1 tries a pending IBAN and a destination belonging to User 2.
2. Try zero, negative, excessive amount and more decimal places than supported. Attempt to spend funds already reserved for a withdrawal.
3. Admin tries executing the same finalized withdrawal again and finalizing a cancelled one.

Expected: no wrong-account payout, negative balance or double execution. Unverified destinations stay blocked; valid previously verified accounts remain usable. Rejected amounts do not create an empty or hidden reservation.

### E07 Loan draft and publication limits

1. Admin tries missing name/currency, invalid rate, zero principal, invalid term and a past funding deadline on fresh drafts.
2. Test a deadline covering exactly 50 inclusive Zurich dates, then 51. For direct loans try invalid minimum-subscription percentages; for LO use mismatched boundary date/principal.
3. Preview zero collateral and long names, then publish a valid draft. Try changing protected financial terms after publication.

Expected: meaningful errors and no partially published loan. A 50-date window is allowed; 51 is not. Boundary must be the first installment after LO funding. Zero collateral hides LTV rather than dividing by zero. Published accepted economics are not silently rewritten.

### E08 Reject malformed LO imports

1. Admin uploads bad-total.csv, bad-numbering.csv, bad-opening-principal.csv and bad-future-payment.csv to separate LO drafts using the map's exact as-of dates.
2. Also try a missing CSV header, wrong column order, decimal text in a minor-unit column and a non-CSV file. Keep these local copies separate from valid files.
3. Correct the file by using the matching valid initial import and save successfully.

Expected: every invalid case is rejected with a usable explanation. No partial schedule or stray loan is published. The original draft remains recoverable. A file with a future payment is not rejected merely because the tester chose the wrong as-of date; use the stated date deliberately.

### E09 Preserve LO history and enforce the payment order

1. On a copy with boundary file 02 already recorded, upload bad-missing-history.csv. Separately test bad-duplicate-reference.csv in its mapped state.
2. On a boundary-paid copy, upload bad-principal-before-interest.csv with its stated advance-payment reference and date.
3. Retry a previously recorded valid payment with identical evidence, then with changed amounts or changed historical receipt data.

Expected: prior receipts cannot be removed or changed. Duplicate/conflicting payments are rejected or safely replayed without extra money. The principal-before-interest file must be rejected by the repayment service even though its CSV totals reconcile. Investor balances, LO payable and schedule remain unchanged on rejection.

### E10 Protect LO terms during and after funding

1. Subscribe User 1 to a still-open LO loan, then try recording an asset-changing payment or replacement schedule before funding closes.
2. Follow the permitted pre-deadline cancel/refund and replacement-opportunity procedure in a separate branch.
3. After the deadline, try a backdated funding-period payment and try changing the published entitlement boundary or participation rates.

Expected: existing subscriptions are not silently repriced or given different rights. Pre-deadline asset changes require the approved replacement flow. Post-deadline inconsistencies require repair/escalation, not discretionary cancellation or a fictional receipt.

### E11 Minimum balance and remaining capacity

1. User 1 tries just below the displayed investment minimum, the exact minimum, and above the remaining capacity on direct and LO loans.
2. Try the correct amount in the wrong currency, without eligible balance, and with only a source too old for that funding window.
3. Test a final remaining slice smaller than the ordinary minimum and follow the explicit rule/error shown, without assuming an exception.

Expected: exact valid amounts succeed once; invalid orders do not reserve funds or increase progress. LO retained principal is never sold. The UI explains whether the problem is amount, capacity, currency or source age.

### E12 Compete for the same investment

1. Give Users 1 and 2 enough eligible balance. Both open the same small remaining direct or LO capacity in separate browser profiles.
2. Prepare confirmation in both, submit close together and reload after both responses.
3. Check capacity, both balances, orders and any automatic LO close.

Expected: combined allocations never exceed sellable capacity. A rejected investor keeps its money. Automatic close and the competing request cannot create duplicate holdings or sell the LO's retained share.

### E13 Reject a changed batch as one whole operation

1. User 1 reviews a batch spanning CHF, EUR, direct and current LO loans.
2. User 2 consumes one selected loan's remaining capacity before User 1 submits, or Admin applies an approved blocking change to that item.
3. User 1 submits, reloads all selected loans and both balances, then reviews a fresh valid batch.

Expected: the entire stale batch fails without a partial set of investments. No CHF success with an EUR failure. A fresh review is required. Retained internal evidence of the attempted acceptance is not mistaken for a successful investment or balance debit.

### E14 Test every FX unavailability reason

1. On the controlled weekend date open FX. Repeat for a configured holiday using the environment owner's setup.
2. Have the owner provide a stale/unavailable provider response, disabled pair and reached daily-limit case in isolation.
3. Restore valid weekday quotes and retry a small conversion.

Expected: weekend and holiday messages identify the actual closure. Stale/unavailable rates show a temporary issue with support guidance, not a made-up holiday explanation. A disabled pair or limit has its own actionable error. Rejections never debit funds.

### E15 Expire a quote or interrupt submission

1. User 1 obtains an FX quote, waits past the displayed 60-second lock and tries to confirm. Refresh the quote and review again.
2. During a separate money action simulate a lost connection immediately after Submit; reconnect and reload before deciding to retry.
3. Check both possible outcomes: completed once, or not completed with unchanged money. Use developer assistance for an exact request replay where needed.

Expected: expired prices cannot execute. The user can recover without a second debit. A network error is not proof that the server rejected the action. The confirmed result is visible consistently after reconnecting.

### E16 Block invalid secondary sales

1. User 1 tries listing a direct holding before disbursement, an already sold/zero holding, an LO holding at a premium, and the same holding twice.
2. Try selling only part of one holding. User 1 also tries buying its own listing.
3. Keep two separate holdings in the same loan and confirm each can be managed independently when eligible.

Expected: unavailable actions are disabled with explanations or safely rejected. Full-holding-only policy is enforced. LO par/discount restriction is enforced. Separate legitimate holdings do not get combined accidentally.

### E17 Compete for a secondary listing

1. User 1 lists a fresh eligible holding. Users 2 and 3, now verified and funded, open it and prepare their confirmations.
2. Submit close together. In a separate branch let User 1 cancel or edit while User 2 has an old buy modal open.
3. Compare all three users' balances and holdings and the seller's activity.

Expected: only one buyer acquires the holding. The losing request has no debit. Cancelled or materially changed listings cannot settle under stale consent. The seller gets one sale and one corresponding proceeds credit.

### E18 Prevent repayment before disbursement and excess receipts

1. Admin tries a direct regular repayment and an advance repayment while its loan is Funded but not disbursed.
2. After a valid disbursement try missing collection account, future value date, zero receipt, negative amount and a receipt greater than the supported payoff.
3. Try another disbursement and a payout-plus-fee override that leaves a material residual payable.

Expected: direct servicing is blocked until registered disbursement. Invalid bank evidence and amounts do not change balances. The form supplies or clearly requires a collection account, instead of submitting an invisible blank field. Disbursement cannot execute twice or leave an unexplained residual payable.

### E19 Handle failed document downloads

1. User 1 opens an accepted document from a completed test investment.
2. Use browser network controls to fail the download, restore the connection and retry.
3. Try a broken/expired document link and a download after signing out.

Expected: a download failure gives a clear error and can recover. No blank success PDF or unauthorized file is served. Retrying a download does not repeat the investment.

### E20 Keep accounts and private data separate

1. While signed in as User 2, open a copied User 1 document URL or other user-owned resource reference through an approved test request. Repeat logged out.
2. Try admin routes as each investor and confirm they are denied. Regular Admin must not be able to edit an investor's Smart Invest rule.
3. Put distinct private marker text in borrower ownership, bank, KYB and risk notes; search investor views, documents and permitted public responses for it.

Expected: forbidden data stays inaccessible, including direct URLs. Admin-only document generation does not grant public access. Private marker text never appears in investor content. Admins cannot edit investor Smart Invest rules, even through a direct request.

### E21 Recover from delayed or failed email delivery

1. With the environment owner's help, temporarily fail delivery to a controlled mailbox for investor login, admin login, a transaction notice and a new Smart Invest match.
2. Admin inspects Failed emails/tasks and the visible delivery state. Restore the provider and use the supported retry/recovery path.
3. Confirm actual mailbox receipt, correct recipient and link, and unchanged financial records.

Expected: queued/accepted-by-provider is not claimed as delivered without evidence. Failures become visible operational work and retry safely. Expired authentication secrets are not resurrected; request a fresh challenge. Retrying a notice never repeats its money action. No secrets appear in visible logs.

### E22 Test loading errors empty filters and long content

1. In each investor page and admin table, test normal data, no rows, no filter matches, loading and a temporary failed request using approved browser/network controls.
2. Use long borrower/loan names and large valid amounts. Switch tabs during a slow request, close/reopen a modal and navigate back.
3. Check that Retry recovers and an old response cannot overwrite a different selected user's or loan's details.

Expected: no blank page, misleading empty success, clipped total or wrong-entity mutation. Stale content is not presented as fresh successful data. Tables, dialogs and status controls remain readable.

### E23 Check small screens keyboard access and tooltips

1. Repeat core navigation, investing review, withdrawal, loan detail, schedules and admin task panels at 320/390, 768, 1024, 1440 and 1920 pixels. Also test browser zoom at 200%.
2. Use Tab, Shift-Tab, Enter and Escape. Open tooltips through keyboard focus and touch where supported. Open every custom select and sort menu near screen edges.
3. Check sidebar labels, Add Funds, notification bell, table copy icons, status explanations and Smart Invest blocked-checkbox explanations.

Expected: no whole-page horizontal wobble, hidden confirm buttons, overlapping text or trapped menus. Wide data tables may scroll within their own container. Investment Opportunities fits its menu row. Tooltip text is actually visible and not clipped behind a table or modal.

### E24 Test monetary rounding and date boundaries

1. Use a small three-investor allocation prepared by the owner so division leaves one-cent remainders. Record repayment and compare the sum of credits with the distributable amount.
2. Repeat schedule checks for a month-end start and a leap-year February using supported QA fixtures; test Zurich midnight and daylight-saving changes.
3. Confirm amounts with apostrophes/thin spaces display correctly and amount presets still submit the intended integer value.

Expected: no missing cents, negative outstanding or summed running-balance totals. Last installments absorb allowed rounding residues. Calendar months are not assumed to have 30 days. Business decisions use Zurich dates even when the tester is in another timezone.

## Finish the regression run

1. Check that every story has a recorded result and that failed/blocked items have evidence and an owner. Do not sign off a money mismatch, unauthorized data exposure or failed authentication path.
2. Save the results, files generated by the website and screenshots outside the database. Use only synthetic data in anything shared with development.
3. Ask the environment owner to restore the staging seed snapshot, verify the seed date and starting balances, and check that no test job is still running. The regression baseline intentionally keeps QA mode enabled for the next run. Coordinate provider settings and the end of the QA campaign with the environment owner. Do not delete real records or send real transfers as cleanup.
4. Record the release actually tested, dates, browser/resolution coverage, unresolved issues and whether external email/SMS/Didit delivery was really observed or only simulated.

## Coverage and source notes

The stories cover public browsing, investor/admin authentication, account controls, offline company setup, direct and LO origination, funding, Smart Invest, batch orders, balances, IBANs, withdrawals, FX, portfolio, schedules, secondary trading, servicing, recovery, accepted documents, reporting, notifications, admin work queues and permissions. Registration and superadmin tools are excluded. Time changes and seed restores are preparation handled by the environment owner.

Some operational services are implemented without a complete admin UI. Those cases explicitly need an environment owner to prepare or execute the supported service; a manual tester should not be asked to invent a screen or edit the database. The current LO CSV penalty obligations are taken from validated contractual import evidence; they are not independently rebuilt from a separate LO penalty-rate policy. Validate the source evidence as well as the platform split.

Use plan/03_accounts_auth_access.md, plan/04_investor_portal.md, plan/06_admin_operations_portal.md, plan/07_loan_product_catalog.md, plan/09_marketplace_investments.md, plan/10_payments_ledger_custody.md, plan/11_loan_servicing_repayments.md, plan/13_documents_contracting_esign.md and docs/runbooks/server-deployment.md for detailed rules. Later dated decisions take precedence over older manual wording. This guide intentionally does not use the retired manual LO activation or new refinancing flow.
