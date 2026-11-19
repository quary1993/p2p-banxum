# Claude Design TODO

## 2026-11-09: U33 Fidelity Pass: Differences From The Design That Stay

- Screen or component: all U33 investor screens, the sign-in screens and the public site.
- Current behavior: the texts and states follow the design. The investor area now also has the design's Export on My investments, the "View matches" dialog of Smart Invest, the Loan originators page (`/marketplace/originators`), the country, payment line and security description on the opportunity cards, and the design's date format ("4 Oct 2026"). These differences stay:
  - Data that the platform does not have: the "Banxum co-investment" line (U33-DEC-15); the originator's "About" text on the Loan originators page (the public originators API has no story; U33-DEC-23 added the borrower's city and employees and the originator's founding year, city and sector); the bank name of a bank account; address, date of birth and nationality in Personal details; the "Updated" date and "Source of repayment" of the credit file (U33-DEC-20 added the financial years, the key ratios, the existing debt, "Checks & updates" and the document metadata); borrower names in Past opportunities and Earlier claims (the public projects API is anonymous); "Coming soon" projects and Save for later are built (U33-DEC-17, U33-DEC-18, 2026-11-10).
  - Decisions in the register: no passkeys (D-2; since 18.5, 2026-11-19, sign-in is password + SMS code or authenticator app as in the design, and operations need the email code + the PIN or the authenticator code, D-1; before that: an email link and the email code + PIN, U33-DEC-01, Phase 17.3); service emails always on (U33-DEC-30); "Contact support to change" instead of Edit (U33-DEC-26); the verification history instead of self-declaration and periodic review (U33-DEC-27); two acceptances and the document version note (U33-DEC-14); repayments credited to the Banxum account (U33-DEC-02); the resale premium and seller fee at 2% instead of the design's 1% (U33-DEC-06, U33-DEC-07); four Smart Invest steps until the Repayments step and the other criteria exist (U33-DEC-19, Phase 17.2); "your investment starts" in the reservation notice until the signed assignment exists (U33-DEC-13); no support hours or answer times until they are confirmed (U33-DEC-35); the brand line in the footer (U33-DEC-34); All projects, Statistics, Help and Guides stay on the public site (U33-DEC-39).
  - Functions that the design does not have and that stay because their removal removes a function: the amount line on the opportunity page and in Review & sign (minimum, amount still open, the balance usable for this loan; audit A-39); the funding close date on the opportunity page; the Swiss-borrower places line (MKT-DEC-028 until U33-DEC-08); the Transactions CSV; the report types, report currency and report summary; the account closure request; the frozen-account and penalty information (U33-DEC-04 open); the CHF IBAN next to the QR-IBAN; the QR code as a PNG; cookie settings and imprint on the public site.
- Suggested improvement: add each item when its data or phase is ready; ask the designer for the states that the design does not show.
- Priority: important.

## 2026-11-09: U33 Investor Shell, Skin Coexistence And Shared Components (Phase 17.1 S1)

- Screen or component: investor shell `frontend/src/portal/shell/` (sidebar INVEST / WALLET / ACCOUNT, header balances, account dropdown, notifications dropdown, phone header and off-canvas menu, footer), `frontend/src/portal/components/`, generated `frontend/src/portal/u33/u33.css` + `u33-overrides.css`, interim `/transactions` and `/reports` screens.
- Current behavior: the shell is the design's DOM and CSS (purged and scoped to `html.bxu`), wired to today's data and routes. Every old screen body is shown unchanged inside the new shell (`LegacyBody`, old skin `html.bxm`); in Dark the old bodies appear as a light panel because the old skin has no Dark. The account dropdown has Profile & Settings, Help, Language (English or Deutsch since 2026-11-10, U33-DEC-31) and Sign out; the design's Personal information / Security / Bank accounts / Preferences entries wait for the settings sub-routes (S5). Transactions and Reports have a U33 page head over today's activity list and today's statements/tax documents (S4 rebuilds them). Notification rows use the neutral style (amber only for failed deliveries) because the API has no category for the design's positive/late tones. The Account entry keeps today's alert marker (money due back, frozen account) in the design's count style. The compact sidebar state is kept per browser.
- Suggested improvement: S2-S5 replace each `LegacyBody` with the rebuilt screen; add the settings sub-routes and the remaining account-menu entries (S5); give notifications a category (positive, late, default) so rows get the design's tones; the design's attribute selectors on prototype links (`a[href^="#/projects/"]`, `[href$="/invest"]`, `a[href="#/signup"]`) never match app addresses, so the screens that need those styles add a class and an override; Appearance and Number format controls in Profile & Settings -> Preferences (S5; the hooks exist, preview mode has a floating reviewer panel).
- Priority: blocking polish (until S2-S5 replace the old bodies).

## 2026-11-09: Number Format Preference (U33-DEC-32)

- Screen or component: `frontend/src/investorPortal/format.ts` (`useNumberFormat`, `parseMoneyInputToMinorUnits`), every amount, rate and percentage of the investor area.
- Current behavior: the investor area shows European `1.234,56` by default and Swiss `1’234.56` as the alternative, independent of the language; the choice is saved in the account (updated 2026-11-10, Phase 17.8: `User.number_format`, `PATCH /api/v1/auth/preferences/display/`; the account's choice applies on sign-in on every device, and the browser keeps a copy). Typed amounts follow the selected format; a value valid only in the other format is accepted when it has one reading, and a value with two readings (e.g. `1,234` with the Swiss format) is refused with an example instead of being guessed. The admin console keeps `1'234.56`; the public site keeps its own format (S6). Emails and the notification centre show the amounts and percentages of each message in the recipient's format (messages are written in the canonical Swiss form and converted when shown; the backend's Swiss group sign is the ASCII apostrophe because PDFs are Latin-1); a new account statement of one investor uses that investor's format. Documents already issued are not rewritten.
- Suggested improvement: decide whether the admin console should follow the operator's own preference; show the Swiss group sign the same way in the interface (’) and in emails (').
- Priority: important.

## 2026-11-09: U33 Fonts And Icons (U33-DEC-37)

- Screen or component: `frontend/src/portal/u33/assets/nioicon-u33.woff2` (Nioicon subset, 228 glyphs used by the kept U33 rules), Archivo via `@fontsource-variable/archivo`.
- Current behavior: the design's embedded Archivo faces (400/500/600) are replaced by Archivo Variable (SIL OFL 1.1); weights outside 400-600 are clamped to what the design renders. Nioicon (DashLite template) is subset from the design's file; `fcicons` is not used.
- Suggested improvement: confirm the DashLite/Nioicon licence covers this use and distribution (U33-DEC-37) or pick a replacement icon set with the same glyphs.
- Priority: important.

## 2026-11-09: U33 Account, Add Funds And Withdraw (Phase 17.1 S4)

- Screen or component: `frontend/src/portal/screens/wallet/AccountScreen.tsx`, `AddFundsDialog.tsx`, `WithdrawDialog.tsx`, `parts/`, `wallet.css` (route `/balances`; the header's Add funds opens the same dialog).
- Current behavior: the design's account cards (EUR first) with the available balance, "Reserved for investments" (allocated primary orders, linked to My investments) and, when there are any, "Withdrawals in progress"; Add funds and Withdraw per currency; the automatic-return line with the date and amount of the next return from the lots (day 56 last day, return from day 57: 18.4). Balance details lists each lot (received, source, available, return date, Last day / Due back / Frozen tag), the investment reservations (funding close date when the loan is listed) and the withdrawals in progress (the design has no such list). The lot table has the design's per-lot "Reserved" column (18.3: `reserved_amount_minor` of the balances API, from the allocated orders); a lot that is fully reserved stays in the list with "Reserved for investments" in place of its return date. Today's last-day, due-back (with or without a verified bank account) and penalty states use the design's alert component (`.ov-updates .alert`) because the design has no screens for them (U33-DEC-29/-04); the frozen banner stays the shell's. Bank accounts live in Profile & Settings (design): the account rules and Withdraw's "Change" link there, and "Add a bank account" (due-back and last-day notices without a verified account, Withdraw without one) opens today's payout-IBAN dialog of the shell (S5's U33 bank-account dialog after the merge). Add funds shows the API's account holder, IBAN, QR-IBAN, BIC and personal reference with copy buttons, "Transfer from a bank account in your name" and "Deposits we cannot match to you are checked by hand" (U33-DEC-05), "Banxum is a brand of Garanta Finanzgruppe AG" (U33-DEC-34); for CHF a PNG of the Swiss QR code ("Download QR code") and the code on screen, not the design's QR-bill PDF. Withdraw: amount within the withdrawable balance, the verified account of the currency (the return account first, a choice when there are several; pending accounts listed as "Pending verification"), "Usually 1–3 business days · No Banxum fee" (U33-DEC-35), then today's email code + PIN and a result step in the dialog (the design shows a toast). The PIN field and its create/forgot dialogs are still the old skin (`investorPortal/pin.tsx`). The old skin's `.modal` box (styles.css) also matches the U33 dialogs; `wallet.css` carries the main session's temporary fix `html.bxu body > .modal {...}`.
- Suggested improvement: the 56-day rule with the 10- and 3-day notices (Phase 17.2, U33-DEC-03); remove penalty mode and design the failed-return and locked states (U33-DEC-04, U33-DEC-29); a QR-bill payment part (PDF) from the backend; PIN-only confirmation of withdrawals (Phase 17.3, U33-DEC-01) and a U33 PIN field; move the `.modal` fix into `u33-overrides.css`; pass the currency to the U33 bank-account dialog.
- Priority: important.

## 2026-11-09: U33 Transactions (Phase 17.1 S4)

- Screen or component: `frontend/src/portal/screens/wallet/TransactionsScreen.tsx`, `transactionsModel.ts` (route `/transactions`).
- Current behavior (18.3): `GET /investor/portal/transactions/` filters the whole history on the server by search (title, project, reference, type, amount), period (last 30 / 90 days, calendar years, custom from/to on Europe/Zurich dates), type and currency, and sends 15 rows per page ("Show more" loads the next page); the design's "Available balance" column (the investor's `investor_balance_liability` ledger balance in that currency right after the movement; "—" when the ledger cannot place it); a detail dialog (principal and interest of repayments and recoveries, destination of withdrawals, the available balance after, link to the loan); the server's Summary of every movement that matches (deposited, invested, repayments credited, withdrawn); `GET /investor/portal/transactions/export/` gives the CSV of the whole filtered history in the investor's number format with the design's columns (Date, Type, Description, Currency, Amount, Available balance, Principal, Interest, Status) and the reference. Repayments and recoveries read "Credited to your balance" (U33-DEC-02). Reservation, release and closing are separate movements (Q26). Resale listings appear as rows without an amount sign.
- Suggested improvement: "Available after transaction" on phones as the design's second line (today the mobile record shows the column's label and value).
- Priority: important.

## 2026-11-09: U33 Reports And Create Report (Phase 17.1 S4)

- Screen or component: `frontend/src/portal/screens/wallet/ReportsScreen.tsx` (route `/reports`).
- Current behavior (18.3): the design's year control (this year, last year, the year before, All years), the type filter (Account statement, Portfolio report, Interest and repayments, Tax report) and the Annual / All-time summary per currency (`GET /investor/portal/reports/summary/`: invested, principal repaid, interest received). One list with the reports kept as issued (`GET /investor/portal/reports/`: those the investor created and the monthly account statements the platform creates each month) and the statements and annual tax information offered on request (`GET /investor/portal/documents/`). A PDF opens in the in-app reader ("View": pages, zoom, Download PDF, error with "Try again", Escape / Close); a CSV is downloaded. Create report: the design's four types, a month range (the portfolio is "As of" today), EUR and CHF or one currency, PDF or CSV; the report is generated and kept (`POST /investor/portal/reports/`), a toast and a "Document ready" notification (opens Reports) announce it. The Tax report says it is information for the tax return, not an official tax certificate (E-09). Create report offers PDF and CSV (the design); the offered statements and tax information keep their CSV and the ZIP evidence package (PDF, CSV and checksums) on their row (D-11).
- Suggested improvement: country names instead of codes in the reports; German report texts with 18.13.
- Priority: important.

## 2026-11-09: U33 Documents (Phase 17.1 S4)

- Screen or component: `frontend/src/portal/screens/wallet/DocumentsScreen.tsx`, `documentsModel.ts` (route `/documents`).
- Current behavior: three tabs (the design has two): Investment documents (accepted investment, resale and Loan Originator agreements, with search, type and year filters), Statements (statements and tax information, also under Reports) and Platform documents (accepted registration terms and risk disclosures). Each row has "View" (the in-app PDF reader, 18.3) and "Download". Acceptances read "Accepted by you" with "Accepted on ... with your email code and PIN": an acceptance is not a signature, and there are no "Signed by Banxum" assignment declarations before the QES work (U33-DEC-13, Phase 17.6). The investment link of the design is the acceptance's context label as text: the documents API has no holding id for acceptances. On phones the tabs use 13 px labels and a 12 px gap so the three fit.
- Suggested improvement: the QES assignment declaration per investment at closing in this tab (U33-DEC-13); a holding id per acceptance to link the investment; decide whether statements stay in Documents or only in Reports.
- Priority: important.

## 2026-11-09: U33 Notifications Page (Phase 17.1 S4)

- Screen or component: `frontend/src/portal/screens/wallet/NotificationsScreen.tsx` (route `/notifications`).
- Current behavior: All / Unread views with counts, Mark all as read, rows that open the screen they are about and mark themselves read (`investorPortal/notifications.ts`), the design's empty states. Rows without a destination are buttons that only mark the notice read. Each row keeps its topic label under the text (audit A-46; the design has none). Tones (18.3) follow the API's category: positive (money credited, a sale), late (a loan turned late), attention (default) and neutral; a failed delivery is late and says "Email not delivered". The navigation targets include transactions, reports and documents ("Document ready" opens Reports). The row markup repeats the header dropdown's (`portal/shell/NotificationsMenu.tsx` does not export its row).
- Suggested improvement: one shared row component for the dropdown and the page.
- Priority: nice-to-have.

## 2026-11-09: U33 Public Site (Phase 17.1 S6): Shell, Home, About, Project Pages, For Borrowers, For Loan Originators, Contact, Legal

- Screen or component: `frontend/src/site/u33/` (PublicSkin `html.bxp`, PublicShell, pages Home, About, Project, Business, Contact, Legal; generated `public.css` + `public-overrides.css`).
- Current behavior: the U33 public design (desktop edition at 1120 px and wider, mobile edition below, one DOM) with live data. Home shows at most three open projects (closing soonest first, then coming soon), the calculator on the same projects, and the security example on the open projects that have a loan-to-value; the hero rate is the highest open rate, or the statistics' average ("Average annual interest") when nothing is open. Additions the design has no state for: the empty/loading/error box of the opportunities, the card's purpose line (the project's summary, two lines at most), the status badge of funded/repaying/late/default/repaid loans and their "Repayment record" panel, the "I have an account" link in the project gate (opens the loan after log in), the project notice for unknown ids, the cookie notice and the toasts in U33 style, a closing "Ready when you are." band on Home (the About page's conversation band), the forms' consent checkbox, error lines, alert and "sent" state with the reference, and "Other documents" on the legal pages. The asset value of the security figure is the one the published loan-to-value implies ("Value implied by the published loan-to-value"); the asset name is the anonymous public name the admin enters for the main security (18.3, `LoanSecurity.public_name`, for example "Residential building in Biel"), or the type ("Property", "Equipment") when none is entered. The footer links the kept pages (All projects, Statistics, Help, Guides, imprint, cookie settings; D-10). Legal pages show the real texts (published templates; content.ts outlines show their headings only). The public design has no dark theme, so the public site stays light. German and French are marked "Soon" in the language menu.
- Decisions applied in the texts: U33-DEC-38 (collateral or guarantees, no "protected"), U33-DEC-15 (co-investment block left out), U33-DEC-01 (step 3 "Confirm with your PIN"), U33-DEC-35 ("will reply by email", valuation statement), U33-DEC-12 (0% investment fees), U33-DEC-16 (no ratings), U33-DEC-34 (operator line in the footer), U33-DEC-36 (support@banxum.com instead of investors@banxum.ch).
- Suggested improvement: design the states listed above (empty opportunities, funded-loan record, cookie notice, form consent/sent/error, legal outline without text, "Other documents"); decide whether Home keeps the closing band; decide the footer links to the October pages (All projects, Statistics, Help, Imprint, Cookie settings) once U33-DEC-39 is decided; a public asset name per security (U33-DEC-21) would replace the generic names; the calculator and projections use today's monthly schedule until Phase 17.5 (U33-DEC-10/-11).
- Priority: important.

## 2026-11-09: October Public Pages Kept Next To U33 (U33-DEC-39)

- Screen or component: `/projects`, `/how-it-works`, `/statistics`, `/help`, `/guides`, `/guides/{id}`, `/newsletter/confirm`, `/newsletter/unsubscribe`, 404 (`frontend/src/site/pages/`, October shell and `html.bxs` skin).
- Current behavior: unchanged October look and texts, reachable from the U33 footer (All projects, Statistics, Help), from "All projects, including funded and repaid loans" under the home opportunities and from the project page breadcrumb of a funded loan. The risk ratings were removed from the project cards, the statistics list, the Help questions and the guides (U33-DEC-16). The newsletter sign-up lives on `/projects` and `/guides` only (the U33 home has none); "Subscribe again" on an expired newsletter link opens `/projects`. Texts still to align with the decisions: Help "0% fees for investors" (U33-DEC-12), magic-link login (U33-DEC-01, Phase 17.3), the 58-day return (U33-DEC-03, Phase 17.2), the "first year" article saying repayments were paid to bank accounts (U33-DEC-02; kept verbatim by the 2026-10-15 owner decision), the terms outline's "50-day return".
- Suggested improvement: the owner's decision per page (keep, integrate in U33, retire); then a U33 design for the kept ones and the text alignment above.
- Priority: important.

## 2026-11-09: U33 Investing Screens (Phase 17.1 S2): Overview, Investment Opportunities, Past Opportunities, Opportunity Page, Credit File, Review & Sign

- Screen or component: `frontend/src/portal/screens/invest/` (`OverviewScreen`, `OpportunitiesScreen`, `PastOpportunitiesScreen`, `OpportunityScreen`, `CreditFileScreen`, `InvestScreen`, area CSS `invest.css`); routes `/dashboard`, `/marketplace`, `/marketplace/archive`, `/marketplace/{loan-id}` (and `/schedule`, which opens the page with the schedule open), `/marketplace/{loan-id}/credit-file`, `/marketplace/{loan-id}/invest`.
- Current behavior: the design's DOM and classes with live data. States and lines the design has no version of: loading, empty and error panels; the line under the amount field (minimum, amount still open, the investor's balance in the loan currency usable for this loan); "Add funds" replaces "Review investment" when money is missing and opens the shell's Add funds dialog (page and amount stay; the dialog opens on the account's default currency, not the loan's); the closed opportunity page (Funding closed / Payment overdue / In default / Repaid, with a link to the investor's own investment); the clear-filters link next to the counter; a note under the two acceptances saying where the acceptance is recorded; the result page links "Your accepted terms in Documents" (the design's "Signed agreement" does not exist before the QES of U33-DEC-13); the Overview's frozen-balance line and the dismissible automatic-return line; the legacy immediate claim purchase (executable quote, cash price, principal assigned, premium or discount, quote expiry, Reprice) inside the Review & sign layout. "Help with this step" opens the general FAQ, not help for the step. Dates read "05 Jun 2026" (shared `formatDate`, two-digit day) where the design shows "5 Jun 2026". Filters are the ones today's data supports (currency, security type, minimum rate, maximum term, originator); the design's LTV, country and repayment filters are not built. The design's "Loan originators" button is left out because there is no originators page yet.
- Decisions applied in the texts: U33-DEC-16 (no ratings, no rating filter), U33-DEC-15 (no "Banxum invests alongside you"), U33-DEC-14 (two unchecked acceptances, documents open before confirmation, a new amount clears them), U33-DEC-19 (no batch approval: the Overview's Smart Invest card lists matches and each opens its own opportunity), U33-DEC-02 (repayments and recoveries "credited to your Banxum balance"), U33-DEC-38 (collateral wording, nothing called protected), U33-DEC-33 (EUR and CHF kept apart, no FX), U33-DEC-12 ("No investment fees", no universal "0 fees"), U33-DEC-35 (no promised timings), U33-DEC-24 (investor and originator interest shares in Loan terms; only the investor's share in projections), U33-DEC-08 wording rule (the amount starts empty; the minimum is never pre-filled).
- Suggested improvement: design the states listed above (loading/empty/error, closed opportunity, amount line, Add funds next to a shortfall, acceptance-recorded note, claim quote); give "Help with this step" a contextual help page; let Add funds open on the loan currency; build the repayment filter once the repayment groups exist (U33-DEC-11).
- Priority: important.

## 2026-11-09: U33 Investing Features Waiting For New Backend Data (S2)

- Screen or component: Overview, Investment opportunities, opportunity page and credit file (`frontend/src/portal/screens/invest/`).
- Current behavior (Coming soon updated 2026-11-10, U33-DEC-17): Coming soon opportunities follow the open ones, the next to open first, with the design's soon card (no funding block, "Opens {date}"), the list's "Coming soon" tag, the counter "· N coming soon" and the opportunity page's soon box ("Opens on {date}", "You can reserve an amount from that day. Funding closes on {date}.", "Tell me when it opens"). Additions: the counter adds the coming soon part only when there is one (the design always shows both parts on Smart Invest); after "Tell me when it opens" the box says "We will email you when this loan opens" and has "Cancel the opening alert" (the design shows a toast only); the alert email goes out when the loan is published, not on the planned date. Save for later (updated 2026-11-10, U33-DEC-18): the opportunity page's "Save for later" / "Saved" button (v107-save), the cards' "Saved" badge (removes it) and Overview's "Continue your investment review" panel are the design's, stored in the account (the design keeps them in the browser). Differences by decision: an opportunity can be saved without an amount (its Overview row then has no amount); saved cards keep their place in the sort (the design moves them first); a saved amount that no longer fits is explained on Overview and on the opportunity page and kept; the 7, 3 and 1 day reminders are emails listed in Notifications. Left out until the data exists: the Smart Invest repayment criterion and the security groups (U33-DEC-19, after U33-DEC-11 and U33-DEC-21); (updated 2026-11-10, U33-DEC-20: the credit file always has the seven chapters; Financials shows the recorded years in currency thousands with the details under "+", the four key ratios with their formulas and the existing debt, or the last-year figures when no year is recorded, or says that nothing is published; "Checks & updates" lists the recorded checks ("File review · Recorded by Banxum"), the monitoring text, the recovery stages and the loan notes; Documents shows category, period or date, issuer, version and status; each check has the design's chip (Received or Reviewed) and "Reporting over the loan term" shows the recorded reporting plan as "Proposed plan" with the design's note, or "Agreed plan" (added 2026-11-10; a plan step's icon follows the design's three standard steps, repeated for longer plans)); prior-ranking debt drawn in the LTV figure (several securities are listed and the credit file states prior-ranking debt with the combined share, U33-DEC-21, 2026-11-10); the originator's "About" text (U33-DEC-23 added the borrower's city and employees and the originator's founding year, city and sector; an empty value is left out); the first installment kept by the originator explained with amounts before confirmation (only a sentence today; open question of U33-DEC-24). Loan terms show the investor's and the originator's shares of interest and penalty interest, and the review step states the split before confirmation (U33-DEC-24, 2026-11-10); stage-by-stage recovery information on a defaulted opportunity page (the stages are on the investment page, U33-DEC-22). The co-investment block stays out for good (U33-DEC-15).
- Suggested improvement: add each element with its backend phase; the design's markup for them is in the prototype (`#/projects`, `#/projects/bx-1046`, `#/projects/bx-1046/credit-file`).
- Priority: important.

## 2026-11-09: U33 Investing Screens Show Today's Platform Rules Until Phase 17.2+ (S2)

- Screen or component: Review & sign confirmation dialog (`.p73-modal`), Overview balance card, opportunity cards and page, Review & sign summary and payment schedule.
- Current behavior: the confirmation dialog asks for the email code and the PIN (ACC-DEC-009; the old PIN component is restyled to the design's boxes) where the design shows the PIN only (U33-DEC-01 / U33-DEC-13, Phase 17.3). The Overview shows the automatic-return date from the API (day 57, or earlier for the bank calendar: 18.4) and, for a frozen account, "Of which ... is frozen, with a daily penalty." (the penalty goes with U33-DEC-04). Swiss-borrower loans show "at most 20 investors", the places left and the raised minimum (MKT-DEC-028) on cards, the funding card and Review & sign (U33-DEC-08 replaces it with the CHF 500,000 borrower total). Projections and schedules use today's monthly engine (annual rate / 12) and monthly repayments only (U33-DEC-10 Actual/365, U33-DEC-11 frequencies).
- Suggested improvement: switch each text and control when its backend phase lands: PIN-only confirmation (17.3), 56-day return and no penalty (17.2), CHF 500,000 borrower total without places (U33-DEC-08), Actual/365 projections and the repayment frequencies (U33-DEC-10/-11).
- Priority: blocking polish (each when its phase ships).

## 2026-11-09: Shared Dialog And Old Skin Rules Under U33 (found in S2)

- Screen or component: shared `Dialog` in `body > .modal`, old skin files `frontend/src/styles.css`, `frontend/src/banxumSkin.css`, `frontend/src/skin/pin.css`.
- Current behavior: the old skin's `.modal` rules squeeze U33 dialogs (580 px box at the top left); S2 carries the agreed reset `html.bxu body > .modal { ... }` in `portal/screens/invest/invest.css`, marked temporary. `skin/projects.css` and `skin/loans.css` lost the rules of the old primary market, loan and invest pages; `styles.css` and `banxumSkin.css` still hold many rules that no source uses any more (for example the old dashboard's `dz-*`), left alone because they are shared by every slice.
- Suggested improvement: move the `.modal` reset into `u33-overrides.css` at the merge and drop it from `invest.css`; after all slices are merged, prune the unused rules of `styles.css` and `banxumSkin.css` in one pass.
- Priority: important.

## 2026-11-13: Owner Answers That Change Investor Screens

- Screen or component: Investment opportunities, Overview, credit file, Transactions, public pages, exchange screen.
- Current first-version behavior: saved opportunities keep their place in "Closing soonest"; the loan-to-value uses the first security; released reservations are not listed; How it works, the first-year article and the October texts are still public; the exchange screen uses the old skin.
- Suggested improvement (decided 2026-11-13, `plan/22` "Final Answers Of 2026-11-13"): saved opportunities first and visually marked, then "Closing soonest" (C05); main security chosen by the admin and LTV on the sum of the distinct relevant assets, with the assets, values and dates shown (C06); "Banxum invests" label without amount (Q04); released reservations as a Transactions entry (Q26); How it works merged into Help, the first-year article removed, return and sign-in texts updated with their rules, "0% fees for investors" kept (Q24); the exchange screen removed (Q25); the seven missing states built with maximum care, coherent with U33 (Q23).
- Priority: important.

## 2026-11-10: Two Invalid Selectors From The Design CSS (audit G-05)

- Screen or component: generated `frontend/src/portal/u33/u33.css` (dialog close control `.close`, Overview widget list `.nk-iv-wg3-list`).
- Current behavior: the design's own stylesheet has `.close:not(:disabled):not(.disabled):hover-focus` (opacity .75 on hover) and `.nk-iv-wg3-list:last-child() li:nth-last-child(2)` (no bottom border on the second-last item). The selectors are not valid, so browsers ignore both rules in the design and in our screens; the production build warns about them. Our screens look like the design. The generated file is not edited by hand, and the generator `tools/u33-design/investor/build-u33-css.mjs` needs the design package to run again.
- Suggested improvement: ask the designer if the two rules are intended. If yes, add correct selectors in `u33-overrides.css` (`.close:hover`, `.close:focus`; `.nk-iv-wg3-list li:nth-last-child(2)`). If no, drop them when `u33.css` is next regenerated (S7 clean-up).
- Priority: nice-to-have.
- Decided 2026-11-13 (owner answer Q27, B): remove both rules; the visible U33 look stays (IMPLEMENTATION_PLAN 17.11).
- Done 2026-11-19 (Phase 18.2): the generator drops both selectors (`dropInvalidSelectors` in `build-u33-css.mjs`), and the two rules are removed from the generated `u33.css` with the same result. A full regeneration also changes a few legacy guards (the old skin changed since the last run), so it waits for the S7 clean-up. Done 2026-11-19 (audit step 4): `u33.css` is regenerated without the legacy guards; without comments, the new file is the old file minus the guards.

## 2026-11-19: S7 Clean-up, The Old Skin Removed (audit step 4)

- Screen or component: the investor portal (`html.bxu`, layout "portal"), `frontend/src/portal/u33/u33-overrides.css`, `frontend/src/base.css`, `frontend/src/portal/screens/invest/invest.css`.
- Current behavior: the old skin (`UserSkin`, `LegacyBody`, `banxumSkin.css`, `skin/*.css`, `investorPortal/pin.tsx`) is removed. Until now the old skin was mounted around the portal and some of its rules reached the U33 screens. What was kept on purpose: its design tokens (fonts, radii, colours, shadows; the screens' own CSS was checked with them) as `html.bxu body.has-sidebar { ... }` in `u33-overrides.css`; the borrower story styles (credit file) in `invest.css`; `.sr-only` in `base.css` (without it the collateral explanation on the loan page became visible). What changed on the portal (the design's own values now apply): small buttons are 44 px high (were 40 px from the old `.btn` height), with wrapping allowed; on Investment opportunities the cards of one row have the same height and the bottom line stays at the bottom; card footers, the balance notice and some dialog headings move by 1-2 px; table headers no longer use tabular figures (no visible change).
- Suggested improvement: none needed; check the 44 px small buttons and the equal card heights on the next design review.
- Priority: nice-to-have.

## 2026-11-10: Bundle Size, Lazy Routes And CSS Per Area (audit G-07)

- Screen or component: `frontend/src/App.tsx`, `frontend/src/main.tsx`, the public, investor and admin style systems.
- Current behavior: one JavaScript bundle (about 1.5 MB) and one CSS bundle (about 2.1 MB), about 690 KB with gzip, for every route. The public site, the investor area and the admin console all load on the first visit.
- Suggested improvement: after the S7 clean-up removes the old skin CSS (`LegacyBody`, `banxumSkin.css`, `skin/*.css`), load the public, investor and admin route groups with `React.lazy` and give each group its own CSS entry. Check the CSS order (`u33.css` before `u33-overrides.css`, the admin `styles.css` scope) and move the admin tests that render routes synchronously to `findBy` queries. Compare desktop and phone screenshots before and after.
- Priority: important (before launch).
- Done 2026-11-19 (audit step 4, with the S7 clean-up): `frontend/src/lazyAreas.ts` loads the public site (`SitePages`, CSS in `site/siteStyles.ts`) and the admin console (`AdminApp`, CSS in `adminConsole/adminStyles.ts` = `styles.css`) on demand; the investor area (sign-in, registration, portal) stays in the main bundle with `u33.css` and `u33-overrides.css`. The `:root` tokens and element rules from the top of `styles.css` are in the global `base.css`, because all three areas were built on them. A loaded area renders at once (no loading state on later visits); the tests preload both areas in `src/test/setup.ts`, so no test changed to `findBy`. Main bundle: JS 1,710 kB -> 1,106 kB, CSS 2,158 kB -> 1,465 kB. Screenshots and computed styles before and after (light, dark, 390 px; pages and dialogs): no change on the public site, the sign-in pages and the admin console; on the portal only removed old-skin side effects (see "S7 Clean-up" below).

## 2026-11-09: U33 My Investments And Investment Page (Phase 17.1 S3)

- Screen or component: My investments `/portfolio` (summary, In funding, Current investments, Payment updates, Portfolio insights, `?view=payments` schedule and calendar, `?view=history`), investment page `/portfolio/:holdingId` (also an open order id: the reserved state), `frontend/src/portal/screens/portfolio/`.
- Current behavior: the design's DOM on today's portfolio and primary-order APIs. All payments lists the investor's share of each payment already received (18.3: `received_payments` of the portfolio API, one row per paid installment, "Paid") and the remaining ones, with the design's Upcoming / Paid / All payments filters; received money without such rows stays one "Received to date" row. Projections exist for active, payment-due, funded and late investments; a loan in default shows "Projection unavailable" and no next payment. Late and default information shows the overdue rows, the days past due, the stages the team recorded and the next step only when it is known (updated 2026-11-10, U33-DEC-22: the late card's steps are the first missed payment, the recorded stages and "Next step · …"; the recovery card's "Current stage" is the latest recorded stage and "Next milestone" the known next step, without a date when none is known), the public loan notes and the recorded recoveries per type; without recorded stages the notes are shown as before; no stages, next steps or dates are invented. Recovered amounts are the recorded ones, credited to the Banxum balance (U33-DEC-02); there is no gross / deducted costs / net breakdown (U33-DEC-12). Documents are today's acceptance PDFs matched to the order or loan; there is no Banxum-signed assignment document (U33-DEC-13). Left out: the design's "Export" button (no portfolio export API), "Banxum co-investment" (U33-DEC-15), ratings (U33-DEC-16). Additions the design has no state for: two lots of one loan are counted as one investment and each lot row says "Invested on" / "Bought on" (audit SECONDARY-11); "Listed for sale" tag; Sold and Written off states; "Investment not found" page; the activity list moved to Transactions and released / never-invested orders are no longer listed anywhere on My investments.
- Suggested improvement: the QES assignment document (U33-DEC-13); a portfolio/schedule export (CSV/PDF); a design state for lots of one loan, sold, written-off and not-found investments; decide where released and closed-not-invested orders are shown (Transactions entry or a history line).
- Priority: important.

## 2026-11-09: U33 Resale Market, Sell Investment, Purchase (Phase 17.1 S3)

- Screen or component: Resale market `/secondary-market` (Available, My listings, "How resale works", offer page `?offer=<id>` with "Confirm purchase"), "Sell investment" / "Edit listing" / "Cancel listing" dialogs on the investment page, `frontend/src/portal/screens/portfolio/`.
- Current behavior: the design's layout with the U33-DEC-06/07 values (2% where the design says 1%): the whole position at 0-102% of the investment value, "Up to 2% premium", the slider from "100% discount" to "2% premium" with the par mark, "Maximum selling price: ... (2% premium).", in whole basis points (a typed amount is rounded to the nearest basis point); the selling fee is 2% of the price capped at 2% of the investment value, with "· No fees" next to accrued interest; fee, accrued interest and net come from the server quote; buyers pay no fee. A principal price of zero is allowed when accrued interest is due; a total of zero shows the server's refusal under the price. "How resale works" has the example from 100% discount to 2% premium and the 2% fee and premium sentences. Seller and buyer terms stay as acceptances with the template version (U33-DEC-14), confirmed with the email code and the PIN (ACC-DEC-009) until the PIN-only confirmation of U33-DEC-01 (Phase 17.3); the create/forgot PIN dialogs are the old-skin ones (S5). Listing is offered only on an investment marked On schedule (no approval request). The offer list has no borrower country flag and no "Ends <date>" line (the buyer list API has neither); the purchase is blocked with "Add funds" when the investable balance is lower than the total price. My listings: the design shows only the empty card; listed investments use the offers table with Edit / Cancel listing, and completed sales and purchases follow in a second table. The design's "Prototype tools" are left out.
- 18.3: the buyer list carries the borrower country and the loan's maturity ("Until …" under the remaining term); My listings has the states Listed / Sold / Cancelled (a listing removed or refused by Banxum is "Removed by Banxum" under Cancelled), with the sale's proceeds and date or the day the listing ended; completed purchases stay below.
- Suggested improvement: PIN-only confirmation (U33-DEC-01, step 4).
- Priority: important.

## 2026-11-09: U33 Smart Invest (Phase 17.1 S3)

- Screen or component: Smart Invest `/smart-invest` (not set up, active with matches, zero matches, paused, "Why these matches?", "Pause Smart Invest" / "Resume Smart Invest"), setup/edit wizard, `frontend/src/portal/screens/portfolio/SmartInvestScreen.tsx`, `SmartInvestWizard.tsx`.
- Current behavior (updated 2026-11-09, U33-DEC-19 part 1; 18.3 adds Repayments): five steps (Currency, Interest & duration, Security, Repayments, Review): currency, minimum interest, maximum term, security types (our collateral types in the design's groups; inventory, invoices, securities pledge, cash, asset-backed, mixed and other stay selectable under their own names) and the design's "Maximum loan-to-value" (an opportunity without a loan-to-value figure does not match a limit); the review step's "More preferences" has the borrower country, the originator and the optional "Preferred investment amount" (one amount for each selected currency; it never limits the matches). 18.3: the design's fifth step Repayments (No preference; Periodic repayments with Interest only / Principal and interest; Payment at maturity) maps today's repayment types (interest only: bullet with periodic interest, interest-only then bullet; principal and interest: equal installments, equal principal, interest-only then amortizing; a one-payment loan pays at maturity); the final types come with 18.6. "No preference" everywhere can be saved and matches every open opportunity (paused without any limit, it counts as not set up). Before 18.3 the in-platform/email channels waited for U33-DEC-30; new matches are emailed as today, so the page says "New matching opportunities are sent to you by email." without the design's "Notification settings" link. "Pause Smart Invest" keeps the preferences and removes matches, marks, counters and alerts (Overview shows "Smart Invest is paused."); the paused page is the design's (saved amount, rate and duration, "Resume Smart Invest", "Edit preferences"); editing a paused rule keeps it paused. (Until 18.3 the backend refused preferences without any limiting criterion.) Purposes and loan kinds were removed from saved rules by a data migration (an active rule left without a criterion is paused). Matches are cards with the borrower's city and country and "Review investment" opening the opportunity page; each investment is confirmed there on its own (no batch: the batch placement API is removed). With a usual amount, a card says when that amount is below the minimum or more than is left, and the opportunity page prepares the amount from it (never raised to the minimum). There is no Cards/List switch. Coming soon matches (U33-DEC-17) follow the open matches with the soon card and "View details"; the toolbar reads "N opportunities · N open · N coming soon" as in the design, and the open count never includes them.
- Suggested improvement: the final repayment types and frequencies of U33-DEC-11 (18.6), the security groups after U33-DEC-21.
- Priority: important.

## 2026-10-16: Swiss-Borrower Investor Limit On The Invest Page (MKT-DEC-028)

- Screen or component: investor Invest page (`/marketplace/{loan-id}/invest`, primary order and quoted Loan Originator claim), amount step. Since 2026-11-09 (U33, S2) the note lives in `frontend/src/portal/screens/invest/InvestScreen.tsx` and the places also show on the opportunity cards and the opportunity page; `SwissInvestorLimitNote.tsx` was removed. The rule itself is replaced by U33-DEC-08 (see "U33 Investing Screens Show Today's Platform Rules").
- Current behavior: for a loan to a Swiss borrower a small grey note under the amount field reads "Swiss borrower: at most 20 investors. N places left." ("1 place left" for one). The minimum in the field hint and the amount check is the API's `minimum_investment_minor`, which already includes the raised new-investor minimum. When no place is left a new investor sees a red banner "No place left for a new investor" with "This loan to a Swiss company already has the maximum of 20 investors. Choose another loan on the primary market." and the Review/Quote button stays disabled; an investor who already invests sees "No places left for new investors. You already invest in this loan, so you can add to it." A 409 `swiss_investor_limit` at confirmation shows the same message in the error banner and reloads the loan.
- Suggested improvement: decide whether the places left also belong on the loan page and the marketplace cards (the API has `max_investors`, `places_left`, `is_existing_investor` in the list and detail), and whether the note should explain why the minimum is higher than the usual CHF/EUR 1,000.

## 2026-10-16: Investor PIN (ACC-DEC-009): Registration Step, Post-Login Screen, Sensitive Actions, Settings

- Screen or component: six-box PIN input and rules checklist (`frontend/src/investorPortal/pin.tsx`, `skin/pin.css`); registration step 3 "Create your PIN" (Account, Email and phone, PIN, KYC); the post-login "Create your PIN" screen for accounts without a PIN (split sign-in layout; preview: UX state "No PIN yet"); the PIN boxes next to the email code in every sensitive action (withdrawal, payout IBAN, FX, invest, Smart-Invest batch, Loan Originator claim, listing create/edit, secondary purchase); Settings > PIN with Change PIN and Forgot PIN dialogs.
- Current behavior: six square boxes (1px #0a0a0a, no radius, 26px Archivo digits, masked with a dot, "Show" toggle), focus moves on, a pasted PIN fills all boxes, backspace goes back, digits only; labels "PIN digit 1 of 6"; error line under the boxes. The registration card puts the entry left and a paper "Your PIN" checklist right (stacked on phones). Wrong PIN: "Wrong PIN. N attempts left before your PIN is locked." under the boxes, boxes cleared and focused. Locked: red "PIN locked" banner with the Zurich time and a "Forgot PIN?" button; boxes disabled. No PIN yet: the create-PIN dialog opens and the action continues after saving. Forgot PIN: intro naming the last two phone digits, then email code, SMS code, new PIN twice. Preview mode accepts any 6-digit PIN that is not weak and simulates wrong PINs and the lock.
- Suggested improvement: final visual pass of the boxes (size at 320 px, focus ring, error colour on dark backgrounds), a success moment after saving the PIN at registration, whether the checklist should sit under the boxes on desktop too, a countdown instead of a clock time in the lock banner, a "PIN created" step in the KYC timeline, and the wording of the PIN emails (locked, changed).
- Priority: important.

## 2026-10-15: Public Site 1:1 With The Site Design (Foundation: Shell And Home)

- Screen or component: public site shell (header, phone menu, language menu, footer, phone call-to-action bar, cookie notice, toasts) and Home, `frontend/src/site/`.
- Current behavior: markup and CSS are the design's own (the design CSS is purged and scoped to `html.bxs`); a harness compares the design and the app page by page at 1440 and 390 px. Home matches the design except: the place lines read "Country · Sector" (the API has no city), the figures line has no "sample figures", the soon line lists the next project to open first. The design's regular-weight text renders in Helvetica/Arial because its first Archivo face (400, latin) follows a byte-order mark and the browser drops it; the site uses Archivo for every weight. The language menu offers German and French as "Soon" (toast only).
- Suggested improvement: confirm Archivo for body text (the design as rendered shows Helvetica/Arial); decide whether project cards should show a region instead of the city; the other pages follow in the next round.
- Priority: important.

## 2026-10-15: Newsletter Emails (Public Site, COMMS-DEC-009)

- Screen or component: "Confirm your email address" email and the "New projects are open" email of the public site newsletter.
- Current behavior: both use the shared email layout; the new-projects email lists each project as a linked title with "8.50% a year · 12 months · CHF" and a "View project" link, then a "See all projects" button; the footer says why the person gets the email and links to Website, Unsubscribe and the support address.
- Suggested improvement: design the project entry (perhaps the project card of the public site, with its status tag and funding bar) and check the confirmation email against the public site design.
- Priority: nice-to-have.

## 2026-10-15: Public Site Projects, Project Page And Statistics (1:1 With The Site Design)

- Screen or component: `/projects` (status chips, currency select, list, newsletter block, interest calculator), `/projects/{loan-id}` (facts, security, company, who lends, repayment so far, invest box with the mini calculator, other projects) and `/statistics`, `frontend/src/site/pages/`.
- Current behavior: markup, texts and both calculators are the design's, checked with the harness at 1440 and 390 px in every state (filters, calculator options, open/soon/repaying/late/default/repaid projects, unknown id). Data limits: place lines and the project lead read "Country · Sector" (no city, no governing law), Region shows the country, Employees shows "–", the originator line names the originator's country instead of its city and has no business sentence, the crumbs show the first 8 characters of the loan id. Coming soon projects come from the API (`public_status: "coming_soon"` with the planned opening date, U33-DEC-17); the preview fixtures keep the design's form (an open project published after today). While loading or after a failed load the lists show a plain box ("Loading the projects.", "The projects could not be loaded. Try again"), which the design does not have. The filter choice is kept for the browser tab.
- Suggested improvement: decide whether to publish a city or region and the governing law (or drop them from the design), and design the loading and error states of these pages.

## 2026-10-15: Public Site Forms And Info Pages (How It Works, For Companies, For Loan Originators, About, Contact)

- Screen or component: `frontend/src/site/pages/` HowItWorks (marketplace diagram), Companies, Originators, About, Contact; the three forms in `EnquiryForm.tsx` / `enquiry.ts`.
- Current behavior: 1:1 with the design at 1440 and 390 px (harness), including the invalid and done states. The forms post to the enquiry API with a hidden honeypot and the time since the form was shown; API field errors appear under their fields, a 429 or an error without a field shows a red-edged alert above the submit button (no design for it). The done boxes keep the design's "We sent a confirmation to <email>." although the API sends no email to the person (owner decision pending). The partner cells on For loan originators read "<Country> · partner since <Month Year>" and "<N> claims funded." (the API has no city or business text). The diagram's disc uses `/brand/banxum-logo-white.svg`.
- Suggested improvement: design the alert above the submit button and a sending state of the submit button; decide the done-box sentence about the confirmation email; decide what the partners column shows when there are no partners (it is left out for now) and whether partners get a city/business line.
- Priority: important.

## 2026-10-15: Public Site Help, Guides, Legal Pages, Newsletter Links And 404 (Round 2)

- Screen or component: `/help`, `/guides`, `/guides/{id}`, `/legal/{doc}`, `/newsletter/confirm`, `/newsletter/unsubscribe` and the 404, `frontend/src/site/pages/`.
- Current behavior: Help, Guides, Guide, the six design legal pages and the 404 match the design at 1440 and 390 px (harness). Terms of use and Risk information show the published "registration" and "risk_disclosure" templates once published (same layout, "Version N · Valid from <date> · Print · Download PDF", the template text as site prose, then "You will be asked to confirm" with the checkbox labels); the other three templates (`/legal/primary-market-investment`, `/legal/secondary-market-listing`, `/legal/secondary-market-purchase`) use the same layout with no active side-navigation item. The newsletter link pages are not in the design: page head plus a site box with a short status text ("Your subscription is confirmed.", "You are unsubscribed.", "This link is not valid or has expired." with "Subscribe again").
- Suggested improvement: design the newsletter link pages and the legal states the design does not have (template loading, not yet published, load error, the backend-only documents in the side navigation, tables and the acknowledgement list in a template); the design hides list markers in `.site-prose` (`li { list-style: none }`), so template bullet lists show without bullets.
- Priority: nice-to-have.

## 2026-10-09: Public Preview Fields, Listing Rule C18 And Lot Labels (QA audit round 2)

- Screen or component: public home carousel, `/projects` cards and `/projects/{loan-id}`; Secondary market "Sell a holding"; My investments loan table.
- Current behavior: the public pages read only the MKT-DEC-002 preview (borrower name, borrower country as a country name, loan type "Direct loan"/"Loan Originator claim" plus "Refinanced", amount, interest, term, status "Open for investment", currency); title and purpose are no longer public. Late or defaulted holdings show a disabled "List" with "Late or in default: cannot be listed"; there is no "Request listing" or "Approval pending". Two lots of one loan count as one loan; each lot row says "invested on <date>" or "bought on <date>", and the table footer says "N loans · M lots".
- Suggested improvement: design a proper country/flag treatment and a loan-type badge for the public cards; consider grouping lots under one loan row with an expandable lot list.
- Priority: nice-to-have.

## 2026-10-09: Public Project Routes And Page Titles

- Screen or component: public project list/detail routes and browser page titles.
- Current behavior: each public project preview uses `/projects/{loan-id}`, survives reload, and returns to `/projects`. Public, authentication, and investor routes update the browser title from the application router, including after sign-out.
- Suggested improvement: add per-project title and description metadata if server rendering or social link previews are introduced.
- Priority: nice-to-have.

## 2026-10-08: Banxum Design Re-skin (User Side)

- Screen or component: all public, sign-in, registration and investor-portal screens. Source: the Banxum prototype (DashLite layout, Archivo, black/white palette) and the Banxum public-site prototype.
- Current behavior: user-side styles live in `frontend/src/banxumSkin.css` (tokens, shell, base components, Overview) and `frontend/src/skin/*.css` (one file per area). Every rule is scoped by the `bxm` class that `UserSkin` sets on `<html>`, so the admin console keeps its own look. Sidebar uses the design names (Overview, Projects > Primary/Secondary market, My investments, Smart-Invest, Wallet > Account/FX, Profile & Settings, Documents, Notifications, Help). Header has a user menu, a notifications menu (5 latest, "View all") and an "Open now" line. The primary market has a Cards view (default) and the existing table as List. Investing and the holding detail are pages (`/marketplace/:loanId/invest`, `/portfolio/:holdingId`) instead of dialogs. The new home page is at `/`; the public loan preview moved to `/projects`.
- Suggested improvement:
  - Confirm the company facts that the home page copies from the design: VQF membership, FINOS affiliation, yearly independent audit, CHF 1,100,000 share capital, registered trademark, "not protected by the Swiss deposit insurance", and the 0.25% seller fee wording.
  - Public loan cards follow MKT-DEC-002 (borrower, amount, interest, period, type, status, currency); the design also shows funded %, days left and minimum. Decide if the public preview fields should change.
  - The "Open now" header line shows the open loan that closes last, because the public loan list has no publication date. Add a published-at field if "newest" is wanted.
  - Not built because there is no backend or data: password/2FA/passkey sign-in, language switcher (DE/FR), cookie notice, newsletter form, "Mark all as read", help contact form, loan description/investor count/"new loan vs existing claim" on cards, quick-amount buttons on the invest page, auto-invest without approval, transactions and reports pages.
  - Review the new pages with real (non-fixture) data, long names and empty states.
- Priority: important.

## 2026-10-09: Multi-Select Filters And Smart-Invest Criteria

- Screen or component: primary-market filter panel, Smart-Invest rule editor and setup wizard (steps 1 and 2), rule summary.
- Current behavior: source, collateral, currency, risk rating, purpose and loan type are multi-select (QA row 37). The filter panel keeps its pill chips as toggles; the rule editor and wizard use square `.check` checkboxes. The combined "Either", "Both", "CHF and EUR", "Anyone" and "Any" options are gone: nothing ticked means no restriction and is labelled ("Any currency", "With or without collateral"). Collateral offers "Any collateral" (every secured loan, including types added later), each collateral type, and "No collateral (unsecured)"; while "Any collateral" is ticked the types show ticked and disabled. The rule editor offers the full rating scale, purpose list and collateral catalog, not only values on today's loans.
- Suggested improvement: the collateral and purpose lists are long on phones (one column of 13 types); consider collapsing the types under "Any collateral" or a "Show types" toggle. Unused `.si-cond-pills` and `.si-wiz-option` rules can be removed from `skin/projects.css` and `styles.css` once no other screen needs them.
- Priority: nice-to-have.

## 2026-09-09: Borrower and Originator Stories

- Screen or component: opportunity calculator, borrower/originator story and separate schedule pages.
- Current behavior: structured rich text and authenticated raster images; direct loans use the borrower's story, LO loans only the originator's story. Selected-public facts remain visible. Investment entry exists on both pages; full schedules retain actual repayments, including prepayments.
- Suggested improvement: final editorial/accessibility review of long stories, empty profiles, long image captions and narrow-screen calculator tables. Preserve confidentiality and label projections as indicative, not guaranteed or received payments.
- Priority: important.

This file is the working brief for Claude Design. Claude Design owns the complete user-facing UI/UX pass for BANXUM before launch. Implementation agents should add entries here whenever they build or touch public, investor, client-portal, onboarding, marketplace, documents, payments, FX, reporting, or account-settings UI visible to platform users.

Admin console UI/UX is not owned by Claude Design. Admin console screens are implemented and designed by the Codex implementation agent and tracked in `docs/admin-console/TODO.md`.

## Ownership Boundary

### 2026-09-09: Archived QA Activity

- Current behavior: Portfolio activity, secondary-market activity and FX history retain pre-reset rows with a small "Before QA reset" label; the archived rows never contribute to current balances or holdings.
- Follow-up: review label wrapping and scanability in the v9 tables on narrow screens. Keep these historical rows distinguishable from the new QA opening balances.
- Priority: nice-to-have.

### 2026-09-07: Funding-Window Eligibility

- Current behavior: single and batch investment previews use each source's remaining holding time; shorter campaigns can use older funds. Balances and FAQ explain potential versus loan-specific eligibility. Fixed day-30 warnings are removed.
- Follow-up: polish the potentially-investable balance label and batch tooltips without implying that all balance can fund every loan; preserve mobile wrapping and keyboard access.
- Priority: nice-to-have.

Claude Design owns:

- Public and unauthenticated user-facing pages.
- Investor registration, login, phone verification, KYC handoff, and account-access states.
- Investor portal IA, navigation, layout, visual system, responsive behavior, and component polish.
- Primary marketplace, loan detail, investment intent, payment instructions, clickwrap, and order-status UX.
- Secondary marketplace browse/list/purchase UX, including risk disclosure and counterparty anonymity.
- Balance, deposit, withdrawal, payout-IBAN, balance-ageing, penalty-mode, and frozen-action UX.
- FX quote, quote-confirmation, exchange history, and limit/error UX.
- Portfolio, exposure, activity, repayment/recovery history, documents, statements, tax-information views, settings, FAQ, support, and notification/status surfaces visible to investors.
- User-facing copy hierarchy, empty states, loading states, validation states, error states, risk warnings, and accessibility.

Claude Design does not own:

- Admin console UI, admin dashboard, admin task queues, compliance review screens, borrower/loan/ledger/reconciliation/admin-reporting screens, or operational admin flows.
- Backend services, financial calculations, ledger rules, regulatory constraints, API contract changes, or database models.
- Legal/regulatory wording approval. Claude may improve UX structure and placeholder copy, but final legal text must remain configurable and advisor-approved.

## Canonical Product Context

- User-facing platform/brand name: BANXUM.
- Legal operator: Garanta Finanzgruppe AG, Switzerland.
- BANXUM must be used for product/platform naming in public pages, investor portal copy, email templates, legal-document titles, generated PDFs/statements, support/FAQ copy, and other user-facing UI where the platform brand is intended.
- Garanta Finanzgruppe AG must be used where the legal operator, contracting party, regulated entity, account holder, VQF/SRO-supervised operating entity, or required legal footer is intended.
- Product brand and legal operator are related but distinct. Do not replace legal-operator references with BANXUM, and do not use Garanta Finanzgruppe AG as the consumer-facing product name unless the context is legal/operator disclosure.
- Platform brand, legal operator, support email, domains, and footer identities must remain configuration/template variables in implementation. Do not hardcode them in reusable templates, document generators, or notification bodies.
- Borrowers are legal entities created and managed by admins. Borrowers do not have a portal and do not log in.
- Direct self-registration is for natural-person lenders only. Legal-entity lenders can exist, but they are created by admins after off-platform onboarding.
- KYC/KYB/AML is handled through Didit/provider workflows plus Garanta compliance evidence. User-facing KYC should be designed as a handoff/status journey, not as an in-platform identity-document collection flow.
- The platform exposes claim/receivable participation in loans. Avoid language that implies a bank deposit, fund unit, savings account, bond exchange, trading venue, guaranteed return, or portfolio-management service.

## Non-Negotiable Domain Rules

These rules must be visible in UX decisions and must not be simplified away:

- Investors can hold platform balances, but every incoming balance lot has regulatory ageing deadlines. Funds must be invested within the 30-day investment window or withdrawn within the 60-day withdrawal window.
- FX conversion does not reset balance ageing. Converted money inherits the source balance deadline. UI must not imply a fresh 30/60-day timer after FX.
- A balance is eligible for investment when it is pledged within its own 30-day investment window. The loan may resolve later under its separately capped funding campaign. Do not incorrectly compare the lot investment deadline with the loan funding deadline.
- If funds reach the 60-day deadline and a usable payout IBAN exists, Garanta may initiate forced withdrawal. If no usable IBAN exists, financial actions are frozen until the investor provides a usable IBAN, and penalty mode may apply according to configurable policy.
- Amounts are stored in minor units. User-facing normal balances and monetary amounts should display two decimals. FX confirmation may display the exchange rate and conversion detail with four decimals where useful; internal precision is higher.
- Supported launch currencies are CHF and EUR, but currency UI should be configurable/extendable.
- Europe/Zurich is the authoritative business timezone for platform day-counts, ageing reminders, late/default status, and user-facing date explanations.
- Primary-market pending investment orders are intents only. They do not reserve loan capacity until funds are allocated/validated in the system.
- First-come, first-served allocation applies when available capacity is limited.
- Loan publication and investment must not expose incomplete borrower optional fields. If an optional borrower field is absent, hide the label and value rather than showing empty, unknown, or not provided.
- Marketplace borrower disclosures must reuse the investor-facing borrower projection from the backend. Do not rebuild hidden/visible document or optional-field logic in frontend code.
- Secondary-market browse and purchase UX must preserve counterparty anonymity. Buyers should not see seller identity, seller net proceeds, maker fee, or internal admin fields. Sellers should not see buyer identity.
- Secondary-market listings for non-performing loans require clear status disclosure and an extra buyer risk acknowledgement.
- Written-off/defaulted/recovery status must be visible next to affected holdings. Do not represent a written-off or defaulted position as a normal live loan just because holding principal still exists.
- Investors may receive repayments, recoveries, secondary-market proceeds, FX proceeds, and withdrawals through platform balance flows. Activity/history must distinguish income/cost items from principal movements.
- Financial actions such as invest, withdraw, FX, secondary-market list, and secondary-market purchase are sensitive. The final UI must support fresh email-code confirmation when the backend integration for that action is wired.

## UX Principles

- Build the actual investor experience, not a marketing landing page. The first authenticated screen should help an investor understand balances, deadlines, investment opportunities, and portfolio state.
- Keep the UI quiet, dense, and financial. Prioritize scanability, tables, compact summaries, clear status chips, exact amounts, and predictable navigation over decorative cards or oversized hero content.
- Use plain English only for v1.
- Avoid promotional return language. Use factual labels such as target interest, scheduled repayment, risk rating, collateral type, current status, days past due, and outstanding principal.
- Separate data that is actionable from data that is historical. A user should quickly understand what they can do now, what is blocked, what needs attention, and what already happened.
- Use progressive disclosure for risk and legal content: show concise summaries near decisions, and provide expandable/detail/download access to full terms and documents.
- Make confirmations explicit for money-moving actions: amount, currency, source balance/deadline impact, fees, expected result, documents accepted, and irreversible/operational caveats.
- All risky statuses need concrete labels and timestamps: KYC pending, KYC manual review, account restricted, phone unverified, balance overdue, withdrawal requested, payment pending validation, loan late, loan defaulted, recovery, final resolution pending, and secondary-market approval required.
- Avoid jargon where it does not help. When domain terms are necessary, define them once in context using compact copy.
- Do not hide regulatory constraints behind friendly language. The 30/60-day balance rule, forced withdrawal requirement, and non-extendable regulatory basis must remain clear.

## User-Facing Information Architecture

Recommended first-pass navigation for authenticated investors:

- Dashboard: account state, balances by currency, ageing alerts, active actions, portfolio summary, recent activity.
- Marketplace: primary-market loans, loan detail, public preview state before login/KYC, investment intent flow.
- Portfolio: holdings, exposure metrics, loan status, repayment/recovery history, public risk notes, secondary-market actions.
- Secondary Market: active listings, non-standard listing warnings, sell/list flow for own holdings, purchase flow.
- Balances: balance lots/deadlines, deposits/payment instructions, withdrawals, payout IBANs, forced-withdrawal/penalty states.
- FX: quote, confirmation, daily limit, fees, history, settlement status copy.
- Documents: accepted terms, investment/secondary-market evidence, account statements, tax-information statements, downloadable packages when implemented.
- Settings: profile, phone verification, bank/payout instructions, marketing consent, support contact, account closure request guidance.

Public/unauthenticated routes should include:

- Public marketplace preview with limited loan fields and clear login/KYC prompts.
- Registration, magic-link login, phone verification, Didit KYC handoff, terms acceptance.
- FAQ/support pages with the support email and concise explanations of balances, investment orders, risks, FX, withdrawals, and secondary market.

## Critical Flow Guidelines

### Registration, Login, And KYC

- Registration accepts natural-person lenders only.
- T&C acceptance happens at registration and must be presented as server-versioned clickwrap, not a generic checkbox detached from document version.
- After registration, route to Didit KYC. If KYC is pending/manual-review/declined, show a clear account state and next step without exposing internal provider payload details.
- Magic-link login should feel simple, but failed/bounced email recovery is handled through support. Do not design self-service password reset for investors.
- Phone verification is required before financial access. Keep phone confirmation lightweight and separate from MFA language.

### Balances, Deposits, And Withdrawals

- Balance views must show per-currency totals and actionable buckets:
  - investable within the 30-day window.
  - withdraw-only because the lot's investment deadline passed.
  - overdue/60-day attention required.
  - penalty-mode/frozen funds.
  - pending withdrawal.
- Each balance lot or grouped bucket should expose enough date context for the investor to understand why an amount is usable or blocked.
- Deposit/payment instructions must make the unique payment reference prominent and explain that matching depends on amount, currency, sender name/IBAN, and reference.
- Withdrawal UX must show destination IBAN, requested amount, currency, expected operational status, and finality caveats.
- Forced withdrawal and missing-IBAN states should be serious but not alarmist. The investor should always know the single next action: provide a usable IBAN.

### Primary Marketplace And Investment

- Public preview before login/KYC should show limited loan data only.
- Full loan detail after financial access should show borrower disclosure, amount, currency, target interest, term, repayment type, collateral type/value/LTV where applicable, risk rating, country, funding progress, deadline, documents, and status.
- Investment intent must communicate that the order is not effective until funds are allocated/validated.
- If only part of an order can be allocated, show the accepted amount, unaccepted amount, and what happens to the excess.
- If deterministic deadline close funds a loan below its original target, show the final subscribed principal and the platform's investor notice in the relevant loan/order/notification surfaces. Do not imply that an admin chose the partial amount.

### Portfolio And Servicing

- Portfolio holdings should separate principal outstanding, interest/recovery received, current loan status, next due date, days past due, repayment type, and secondary-market availability.
- For repayments, show whether the payment was regular, partial, multi-installment, early repayment, or recovery related when available.
- For default/recovery/resolution, show status, public notes, recovery distributions, and any final-resolution reporting context without promising recovery.
- Use current loan status as a first-class visual signal in portfolio tables and holding detail.

### Secondary Market

- Treat secondary market as a bulletin-board claim/participation transfer, not an exchange.
- Listing flow is full-holding only. Do not design partial holding sales.
- Seller price is set as a percentage of current principal balance. UI must show discount/premium clearly.
- Buyer-facing listing detail should show current principal, sale price, discount/premium, accrued interest, taker fee, total cost, loan status, days past due if any, last payment date if available, and public notes.
- Buyer-facing views must not reveal seller identity, seller net proceeds, maker fee, or admin approval internals.
- Seller-facing views may show seller economics, maker fee, net proceeds, listing status, and removal/approval state.
- Non-standard listings need a visible warning and additional acknowledgement before purchase.

### FX

- FX is an auxiliary settlement function. Do not make it feel like trading.
- Launch pairs are CHF/EUR and EUR/CHF. Pair selection should be extendable.
- No minimum exchange amount. Default per-investor daily limit is CHF 100,000 equivalent.
- Quote confirmation should show source amount, target amount, rate, platform fee, expiry/validity, daily-limit impact, and inherited balance deadline impact.
- Background/display quotes may change; confirmed quotes are fixed for the confirmation window. UI should make quote expiry and stale quote refresh clear.
- If a sanity check or provider issue blocks quotes, show a clear unavailable state rather than a suspicious rate.

### Documents, Statements, And Tax Information

- Accepted terms must be viewable later and should show acceptance timestamp, document title/version, transaction context, and downloadable/generated evidence when available.
- Account statements and annual tax-information statements are informational only and not tax advice. This disclaimer must be visible.
- Statements should separate income/cost items from principal and balance movements.
- Do not expose admin-only report controls or full/unredacted admin reporting surfaces to investors. Investor documents must be self-scoped.

## Visual And Interaction Standards

- Use a restrained financial SaaS style: compact tables, consistent spacing, clear hierarchy, and restrained color use.
- Avoid one-note palettes and decorative gradient/orb backgrounds.
- Cards may be used for individual repeated items or compact summaries. Avoid nested cards and marketing-style decorative sections inside the app.
- Use stable table columns, filters, sort states, row actions, pagination or incremental loading where large lists are possible.
- Use icons for common actions where useful, with text labels or tooltips for clarity. Do not replace critical financial labels with icons alone.
- Amounts must align visually, use consistent currency formatting, and avoid wrapping in ways that obscure decimals.
- Date and deadline displays should be consistent and include timezone-sensitive explanations where deadlines matter.
- Every form needs loading, success, validation-error, server-error, cooldown, retry, and stale-data states.
- Every money-moving confirmation needs a review screen before final submit.
- Responsive layouts must work at mobile, tablet, and desktop widths without overlapping text or hidden critical actions.
- Accessibility baseline: keyboard navigation, visible focus states, sufficient contrast, semantic headings, clear form labels, table captions/labels where needed, and screen-reader-friendly status changes.

## API And Implementation Guidance

- Use the generated TypeScript API client from `frontend/src/api/generated/banxumApi.ts` and the shared HTTP client where possible.
- Investor APIs are self-scoped. Do not add user-id selectors or client-supplied investor IDs to investor-facing screens.
- If a backend endpoint is not implemented yet, Claude Design may build UI with MSW mocks or clearly marked local fixtures, but must record the missing endpoint/contract in this file.
- Do not change backend financial calculations or API semantics to fit a design. If a flow feels hard to design, record the UX issue and ask Codex/backend to expose a better projection.
- Keep admin APIs out of user-facing screens.
- Update this file after every design pass with:
  - screen/component touched.
  - current behavior.
  - design decision.
  - remaining backend/API dependency, if any.
  - priority.

## Required Claude Design Deliverables

Before launch, Claude Design should produce or implement:

- Final user-facing route map and navigation model.
- Design tokens for color, typography, spacing, status chips, tables, forms, buttons, alerts, modals, and data cards.
- Responsive layouts for desktop and mobile for all critical flows.
- Investor dashboard, marketplace, balances, portfolio, secondary market, FX, documents, and settings screens.
- Transaction confirmation patterns for invest, withdraw, FX, secondary-market list, and secondary-market purchase.
- Risk/disclosure component patterns for loan risk, default/recovery/resolution, secondary-market warnings, balance-ageing deadlines, and KYC/account restrictions.
- Empty/loading/error/stale/cooldown states.
- Accessibility pass and visual QA screenshots across representative viewports.

## Open Design Work Items

## 2026-06-01: Initial Portal Shell

- Screen or component: root React scaffold shell.
- Current first-version behavior: simple operational shell with top bar, module navigation preview, and status summary.
- Suggested improvement: Claude Design should define the final user-facing/investor information architecture, density, navigation states, responsive behavior, and component tokens before production user-facing portal screens are built out.
- Priority: important.

## 2026-06-02: Investor Balance Ageing And Return-IBAN States

- Screen or component: investor balance dashboard, withdrawal flow, payout-IBAN declaration, ageing reminders, penalty-mode/frozen-action banner.
- Current first-version behavior: no user-facing UI was implemented in this slice; backend APIs now produce balance-ageing reminder events, forced-withdrawal requests, and penalty-mode lot states.
- Suggested improvement: Claude Design should design the investor-facing balance breakdown for investable, withdraw-only, overdue, and penalty-mode funds; reminder messaging hierarchy; the required usable-IBAN declaration/update flow; and a blocking financial-action banner that keeps read-only account access available while clearly explaining the regulatory 60-day limit.
- Priority: important.

## 2026-06-02: Clickwrap Acceptance And Document Downloads

- Screen or component: registration terms display, primary-market investment acceptance, secondary-market purchase/listing acceptance, document evidence/download states.
- Current first-version behavior: no user-facing UI was implemented in this slice; backend APIs now expose current published templates and create immutable acceptance evidence for authenticated transaction contexts.
- Suggested improvement: Claude Design should design the checkbox/clickwrap acceptance presentation, long-form legal text layout, required checkbox hierarchy, stale-template refresh state, accepted-document confirmation state, and user-facing document package/download surfaces for investor portal transactions.
- Priority: important.

## 2026-06-04: Investor Portal API Foundation

- Screen or component: investor dashboard, balances, portfolio, activity timeline, primary-order history, secondary-market own-activity history, and FX history.
- Current first-version behavior: no user-facing UI was implemented in this slice; backend APIs now expose self-scoped data contracts for dashboard summaries, balance ageing buckets/deadlines, payout instructions, holdings, exposure metrics, public loan-note summaries, recent activity, primary orders, secondary-market listings/purchases/sales, and FX quote/exchange history.
- Suggested improvement: Claude Design should do the full investor-portal information architecture and visual pass before production UI implementation, including dashboard hierarchy, balance-ageing warnings, regulatory 60-day deadline language, portfolio/exposure charts, activity table density, empty/error/loading states, responsive behavior, and clear separation between read-only history and money-moving actions.
- Priority: important.

## 2026-06-05: Full User-Facing UX Pass

- Screen or component: all public and investor-facing surfaces.
- Current first-version behavior: Claude Design delivered a standalone high-fidelity reference prototype for the investor experience. That prototype has now been ported into the real Vite/React frontend as a typed first-version investor portal using generated API hooks with local fixture fallback. See `docs/claude-design/INTEGRATION.md`.
- Suggested improvement: Claude Design should now review and polish the integrated app itself, not the deleted standalone prototype. The pass should focus on production-quality spacing, responsive behavior, accessibility, loading/error/cooldown/stale states, and final legal/risk-copy hierarchy across public preview, onboarding/KYC, dashboard, marketplace, investment, balances, withdrawal, FX, portfolio, secondary market, documents, statements, settings, support, and all status/notification states.
- Remaining backend/API dependency: final provider delivery and final production templates/layouts. Registration/KYC redirect, sensitive email-code confirmation, primary investment, withdrawal, live deposit instructions, payout IBAN update, FX quote/execute, secondary-market list/purchase, investor document/statement/tax downloads, and notification delivery status are now wired as first-version live flows.
- Priority: important.

## 2026-06-05: Integrated Investor Portal QA Follow-Up

- Screen or component: integrated investor portal in `frontend/src/App.tsx`, `frontend/src/styles.css`, and `frontend/src/investorPortal/*`.
- Current first-version behavior: app renders public preview, magic-link login, registration/phone/KYC handoff, dashboard, marketplace, loan detail, investment modal, balances/deposit/withdraw/IBAN, FX, portfolio, secondary market, documents, settings, and FAQ. The integration uses generated API hooks and fixture fallback rather than the raw `window.BX` prototype data.
- Design decision: keep the app quiet, dense, and operational. Use BANXUM as brand, Garanta Finanzgruppe AG as legal operator. Preserve counterparty anonymity, balance-ageing deadlines, day-60 freeze copy, server-versioned clickwrap language, and email-code step-up patterns.
- Remaining backend/API dependency: final provider delivery, final legal/tax/reporting templates, and production PDF/CSV layouts. Live mutations and server-projected documents/deposit instructions/notifications are now present as first-version flows.
- Claude Design action: perform a full visual/accessibility pass directly against the integrated Vite app. Check desktop/tablet/mobile; table wrapping; focus states; modal/drawer accessibility; empty/loading/server-error/validation-error/cooldown/stale states; and whether every money-moving confirmation remains understandable without overpromising outcomes.
- Priority: important.

## 2026-06-05: Frontend User-Facing Audit Follow-Up

- Screen or component: investor frontend data adapter, local dummy-data review mode, HTTP client, money inputs/formatting, data-backed state handling, mobile public preview, and critical state tests.
- Current first-version behavior: live API calls are the default. Dummy fixture data requires explicit preview/test mode through `VITE_PREVIEW=true` or `npm run dev:dummy`, cannot be used in production builds, is aliased out of normal production bundles, uses placeholder data rather than initial cached account data, and is visibly labelled in authenticated views. Public and investor data views now show retryable error states and empty states instead of infinite loading or bare table headers.
- Design decision: any fixture-backed authenticated view must carry a clear preview-data warning. The "Open dummy portal" shortcut, UX-state switcher, and "Demo: any 6 digits" code hints are review-only affordances visible only in explicit preview mode. Do not remove or soften the preview warning while fixtures are available.
- Remaining backend/API dependency: final provider delivery, final document/report layouts, profile/settings verification summary, and recovery/default-resolution split detail. Core investor write mutations, deposit instructions, document downloads/evidence packages, and notification list/status now have first-version live API wiring.
- Claude Design action: when polishing the UI, keep the preview warning and fixture/live-data distinction intact. Audit the new retry/error/empty states, the mobile preview-banner layout, and the mobile public help/FAQ access. Do not design fixture states as if they are real account data.
- Priority: important.

## 2026-06-06: Investor Write-Flow Live Wiring

- Screen or component: magic-link login, registration/KYC handoff, withdrawal modal, FX quote/execute, primary investment modal, secondary-market listing modal, and secondary-market purchase modal.
- Current first-version behavior: live mode now uses generated API hooks for magic-link request/consume, natural-person registration, KYC session start/status, sensitive-action email-code request, investor withdrawal request, payout IBAN submission/update, FX quote/execute, primary order/create-clickwrap-allocate, secondary listing create, and secondary purchase. Preview mode keeps clearly marked dummy behavior. Transaction clickwrap uses the current server-published template version and accepts backend-provided checkbox labels rather than hardcoded legal labels.
- Design decision: every money-moving user action must show a review step, server-versioned clickwrap context, explicit email-code request, 6-digit code entry, and a server-error state. Do not make the email-code field look optional in live mode. Do not calculate final financial outcomes in the client; display backend quote/order/listing values where available.
- Remaining backend/API dependency: final legal templates and production PDF/CSV layouts; final provider-backed phone/SMS/SendGrid/Didit/Yahoo flows in deployed environments; final copy for tax and statement disclaimers.
- Claude Design action: run a full production-polish pass on these live mutation flows, including cooldown text after email-code request, stale template/expired quote handling, failed mutation retry/cancel behavior, mobile modal ergonomics, focus management, and clear post-submit states for pending manual operations such as withdrawal.
- Priority: blocking polish.

## 2026-06-06: Investor Payout IBAN Self-Service

- Screen or component: Settings payout accounts card and add/update payout IBAN modal.
- Current first-version behavior: investors can submit an additional CHF/EUR payout IBAN after requesting and entering a `bank_account_change` email code. Live mode posts through `/api/v1/ledger/payout-instructions/`; preview mode shows local success. The submitted instruction does not replace or disable an existing verified deposit-source IBAN. It is clearly labelled pending Garanta verification, is not usable for withdrawals or forced returns until admin verification, and automatically creates a linked finance task for the admin team.
- Design decision: treat payout-account changes as sensitive but operationally pending, not instant. The confirmation copy must say that the 60-day balance deadline is not extended and that Garanta verification is required before the IBAN can be used.
- Remaining backend/API dependency: richer admin review/detail UX for investor-submitted payout instructions, final IBAN verification operating procedure, and production SendGrid delivery of the email-code step.
- Claude Design action: polish the Settings payout-account card and modal, especially mobile form layout and pending-verification status language. Make the distinction explicit between verified source accounts established by deposits and additional accounts awaiting Garanta review; do not imply that requesting another IBAN removes an existing verified payout path.
- Priority: important.

## 2026-06-06: Deposit Instructions, Documents, And Notifications

- Screen or component: Balances deposit modal, Documents screen, Notifications screen, and top-bar notification entry point.
- Current first-version behavior: deposit instructions now load from the backend and display Garanta's configured collection account plus the investor/currency-specific payment reference. Documents now list self-scoped accepted clickwrap evidence plus generated-on-request account statements and annual lender tax-information statements, with PDF/CSV/ZIP download actions where the backend supports them. Notifications now show investor email delivery status and operational notice bodies, while authentication and sensitive-code email bodies are deliberately redacted.
- Design decision: keep these screens operational and evidence-oriented. Deposit copy must not imply instant crediting; it should emphasize bank reconciliation and exact reference matching. Document/tax copy must keep the informational-only/not-tax-advice disclaimer visible. Notification copy must not reveal magic-link URLs or sensitive-action codes in the portal.
- Remaining backend/API dependency: final bank account details in platform settings, final advisor-approved statement/tax templates and PDF/CSV layouts, and production provider delivery/status data.
- Claude Design action: polish the density and hierarchy of the deposit-instruction modal, download action grouping, document type filters, checksum/evidence hints, notification status chips, and mobile table/card behavior. Confirm that users can distinguish generated-on-request files from immutable accepted evidence.
- Priority: important.

## 2026-06-23: Generated Legal Evidence PDFs

- Screen or component: registration acceptance, primary-market investment modal, Documents screen, and accepted-document confirmation states.
- Current first-version behavior: registration can use the imported lender user agreement template, and primary-market investments can use the imported project investment confirmation / claim assignment agreement template. Accepted evidence is rendered on demand as a BANXUM/Garanta PDF with a cover page, table of contents, source-of-truth notice, accepted checkbox, and transaction-specific data populated by the server. Accepted legal terms and transaction-agreement PDFs are no longer emailed by default; users access historical accepted versions from the Documents screen.
- Design decision: treat these PDFs as legal evidence packages, not marketing collateral. The UI should make clear which document was accepted, which transaction it belongs to, when it was accepted, and where the generated PDF/CSV can be downloaded later.
- Remaining backend/API dependency: final counsel-approved template text, final production PDF layout decision, and any later post-close assignment artifact if legal requires a final holding ID after funding close.
- Claude Design action: polish user-facing copy and layout around "terms unavailable", stale-template refresh, accepted-document success, and Documents-screen grouping for historical accepted versions and per-order investment confirmations. Do not design an email-with-attachment expectation for legal terms.
- Priority: important.

## 2026-06-30: Public And Portal FAQ

- Screen or component: logged-out FAQ/How-it-works page and signed-in Help & FAQ screen.
- Current first-version behavior: FAQ content is now a shared React component rendered from a public-safe route (`/faq` or public navigation) and inside the authenticated investor shell. Logged-out visitors no longer hit investor portal gating or authenticated data calls when opening FAQ.
- Design decision: keep FAQ educational and compliance-aware rather than promotional. It explains the P2P model, onboarding/KYC, balance ageing, investment orders, repayments, secondary-market anonymity, FX deadline inheritance, documents, support, and risk warnings without implying guaranteed liquidity or returns.
- Suggested improvement: Claude Design should polish the public FAQ hierarchy, mobile accordion spacing, quick navigation between sections, and whether the public FAQ should include visual diagrams for money flow and 30/60-day ageing rules.
- Priority: important.

## 2026-07-04: FX Market-Closed Availability State

- Screen or component: investor Currency Exchange screen and quote error states.
- Current first-version behavior: live-mode FX now displays a proactive weekend-closed banner and disables quote entry/button on Zurich weekends. Backend quote errors distinguish weekend closure, configured FX market holiday closure, and ordinary temporary provider staleness/malformed provider responses.
- Design decision: closed-market FX should feel like a clear operational unavailability state, not a failed trade. Copy must explain that BANXUM cannot issue executable quotes when live FX market rates are not published, while keeping exchange history readable.
- Suggested improvement: Claude Design should polish the weekend/holiday banner placement, mobile spacing, disabled-form affordance, and whether the exchange form should collapse into a read-only explanatory panel during market closures.
- Priority: important.

## 2026-07-04: Borrower Disclosure On Loan Detail

- Screen or component: authenticated marketplace loan detail, Overview and Documents tabs.
- Current first-version behavior: loan detail now renders the backend-projected borrower disclosure. Legal business name is always public; business classification, registered address, and contact info appear only when Garanta marks that field public for the specific borrower. Internal ownership, bank-account details, KYB/AML observations, and financial-risk notes are not returned to the investor UI. Borrower documents shown in the Documents tab come only from investor-visible, clean-scanned borrower files in the backend disclosure projection.
- Design decision: do not duplicate disclosure visibility rules in the frontend. Hide absent optional fields completely; do not show "unknown" or empty labels. Keep borrower disclosure factual and operational, not promotional.
- Suggested improvement: Claude Design should polish the borrower disclosure section for scanability, especially long address/contact text, financial-metric alignment, document-list hierarchy, and mobile layout inside the loan detail tabs.
- Priority: important.

## 2026-07-08: Refinanced Loan Badge

- Screen or component: public loan preview header, marketplace listing rows, authenticated loan detail header, portfolio holdings rows, and holding detail drawer.
- Current first-version behavior: loans with `is_refinancing: true` show a small monospace `tag` badge - "Refinanced loan" in headers/drawers and a shorter "Refinanced" variant inline next to the loan title in marketplace and holdings table rows. The badge is purely informational and reuses the existing `.tag` styling used for currency/purpose tags.
- Design decision: refinancing is provenance information, not a risk warning. The badge must stay visually neutral (no warn/bad tone) and must not crowd out status, rating, or currency chips.
- Suggested improvement: Claude Design should decide whether the badge deserves a distinct visual treatment from generic currency/purpose tags (for example an outline accent), review truncation/wrapping of the title-plus-tag combination in narrow table cells on mobile, and consider a tooltip or one-line explainer for first-time investors who do not know what a refinanced loan is.
- Priority: nice-to-have.

## 2026-07-08: Original Loan Section On Refinanced Loan Detail

- Screen or component: authenticated marketplace loan detail, Overview tab (`OriginalLoanSection`).
- Current first-version behavior: for refinancing loans, the Overview tab renders an "Original loan" card below the purpose/borrower-disclosure card showing original principal, original interest rate (bps rendered as %), original term, original repayment type, original interest-only period where applicable, original loan start date, and a read-only "Original loan repayment schedule" table (#, due date, principal, interest, total, outstanding after, and a green "Paid" chip on installments settled before publication). The table ends with a bold, separated totals row for the additive amount columns and paid count; the running outstanding-after column is intentionally not summed. Copy states the schedule is informational, shows the loan being refinanced, and that investors fund the new loan whose terms are shown above; the financed amount can be lower than the remaining outstanding of the original schedule.
- Design decision: never present the original schedule as the payment plan investors will receive. Keep the informational disclaimer adjacent to the table, and hide the whole section (not empty labels) when the loan is not a refinancing loan or optional original fields are absent.
- Suggested improvement: Claude Design should polish long-schedule ergonomics (24+ rows): consider collapsing paid installments behind a "show paid installments" toggle or scroll container, sticky table header, a compact paid/remaining summary line above the table, mobile horizontal-scroll behavior for the seven-column table, and whether the section belongs on Overview or a dedicated tab once real refinancing volume exists.
- Priority: important.

## 2026-07-27: Portfolio Holding Detail And Repayment Schedule

- Screen or component: Portfolio Holdings table and holding-detail modal.
- Current first-version behavior: selecting a holding opens a large centered modal instead of a narrow side drawer. It retains holding-level invested, outstanding, interest-received, rate, status, and public-risk-note information. Two tabs separate the investor-specific outstanding principal/interest projection from the authoritative whole-loan schedule, which also shows amounts already paid. Both schedule tables end with a bold, separated totals row; the projection totals principal, interest, and expected payments, while the whole-loan schedule totals contractual, paid, and outstanding amounts.
- Design decision: the investor tab is projected server-side by applying the servicing module's exact largest-remainder distribution algorithm sequentially to all current active holdings. The whole-loan tab remains explicitly labelled as borrower obligations. Both can change after holding transfers, repayments in advance, recoveries, or schedule revisions; the frontend must never derive, prorate, or re-amortize either schedule itself.
- Suggested improvement: Claude Design should review long-schedule ergonomics, sticky headers, paid/upcoming filtering, mobile horizontal scrolling, and whether a later API should add an investor-specific expected-distribution projection alongside the authoritative whole-loan schedule.
- Priority: important.

## 2026-07-27: Secondary-Market Review And Step-Up Flow

- Screen or component: secondary-market buyer listing detail, seller listing modal, and Portfolio-to-secondary-market navigation.
- Current first-version behavior: seller listing is a two-step, large-modal flow. Step one reviews the holding, borrower, rate/term, LTV, pricing, fees, seller proceeds, listed-claim projection, whole-loan schedule, and current seller terms. Only after the seller confirms that data does step two send and request entry of the fresh email code before publishing or submitting for approval. Buyer detail now shows buyer-safe loan context and both schedules without seller identity or seller economics; opening it does not send a code, and the buyer explicitly requests one only when ready to purchase. The Portfolio action opens the Secondary Market directly on `Sell a holding`.
- Design decision: preserve counterparty anonymity and backend-projected schedules. Step-up authorization is deliberately late in the flow so an exploratory buyer receives no unsolicited code and a seller does not authorize data that is still being edited. Seller acceptance evidence and the listing mutation are created only at final submission.
- Suggested improvement: review long-schedule ergonomics inside transaction modals, sticky headers, mobile table scrolling, visual step progression, focus placement when moving to verification, and the hierarchy between loan risk information and transaction pricing. Do not collapse the schedule review into client-side calculations or expose seller-side fields to buyers.
- Priority: important.

## 2026-08-03: Investor Brandbook Reskin

- Screen or component: public preview, onboarding/authentication, investor shell, dashboard, marketplace, portfolio, balances, FX, secondary market, documents, notifications, settings, FAQ, forms, tables, status surfaces, and dialogs. The internal admin console remains visually isolated from this layer.
- Current first-version behavior: the existing production flows now use the `website_redesign` visual language without changing routes, API calls, mutations, data projections, or account-state behavior. The reskin applies the ivory/card/hairline palette, Instrument Sans financial figures, Newsreader editorial asides, carbon binding actions, green add-money/profit semantics, red risk/destructive semantics, pill actions and modes, lighter tables, quieter cards, and tighter responsive layouts. The marketplace retains its live-data filters and expanded detail while matching the redesign's company/rate/term/LTV/capacity/deadline hierarchy.
- Design decision: keep the existing sidebar information architecture and every established workflow. Carbon is the default command color; green is reserved for adding money, positive value, and future active investing-rule state; red is reserved for risk, lateness, penalties, and destructive action. Investor/public styles stay scoped to `.app`, `.public`, and `.auth-wrap` so they cannot restyle the operations-focused admin console.
- Suggested improvement: continue the page-by-page redesign only by adapting existing backend projections and workflows. Verify every future screen at desktop, 768px tablet, and 390px mobile; keep wide financial tables contained rather than creating page-level overflow; and preserve the focused/detailed marketplace modes as fields are added.
- Priority: important.

## 2026-07-27: Consolidated Secondary-Market Listing Management

- Screen or component: Secondary Market `Sell a holding` and `Secondary market activity` tabs, plus Portfolio Holdings status.
- Current first-version behavior: each sellable holding row now shows whether it is unlisted, actively listed, or awaiting approval. An open listing replaces the create action with `Edit` and `Cancel`; editing reprices the same listing through a fresh terms-acceptance and email-code flow, while cancellation removes the listing without changing the holding. Portfolio rows and holding detail show the same listing status. The former `My listings` tab is replaced by a unified activity table covering listing creation/edits, cancellations, purchases, and sales; sales and purchases are selected by default, with filters for listing lifecycle entries.
- Design decision: the holding is the primary management context, so investors should not have to reconcile a separate listing table with their portfolio. Listing edits are labelled as listing activity and share the `Listings and edits` filter; they are not presented as money movements. Edit/cancel controls remain unavailable in read-only impersonation and frozen account states.
- Suggested improvement: Claude Design should review action density on narrow screens, status-chip terminology, keyboard/focus behavior across edit and cancellation modals, filter discoverability, and whether activity rows need a compact detail expansion for historical pricing. Preserve the distinction between listing lifecycle entries and completed sale/purchase cash movements.
- Priority: important.

## 2026-07-27: Servicing-Ready Status And Automatic Listing Repricing

- Screen or component: Portfolio holding detail, full-loan schedules, Secondary Market listing/buy views, activity, and repayment-credit notifications.
- Current first-version behavior: `Funded` now means funding closed but borrower payout still pending; the loan becomes `Active` only after the borrower disbursement succeeds. Funded holdings remain visible, but their secondary-market action is disabled with an explicit post-disbursement availability hint. Investor full-loan schedules show immutable historical regular and advance payments followed by the latest outstanding schedule, while investor holding projections remain future-only. Every unsold open secondary listing is automatically recalculated after repayment, recovery, or servicing-status change from the latest holding/loan state while preserving the seller's premium/discount percentage. Repayment-credit notices mention this recalculation only when that investor's listing remains active. If the loan becomes late/defaulted, the listing status tooltip explains that it is hidden pending Garanta reapproval.
- Design decision: do not present a funded-but-undisbursed loan as servicing-active, do not derive historical schedule rows or listing economics in the client, and do not imply that the seller's absolute listing price is fixed after principal changes. The durable seller instruction is the premium/discount percentage (`price_bps`).
- Suggested improvement: clarify `Funded - awaiting borrower payout` versus `Active` in status tooltips; visually distinguish historical payment rows from projected rows; add an unobtrusive “Repriced after repayment” activity/detail treatment; and make the preserved premium/discount explicit in active-listing summaries without exposing internal recalculation metadata.
- Priority: important.

## 2026-08-03: Marketplace Redesign And Brand-System Adoption

- Screen or component: authenticated investor shell brand lockup and primary Marketplace route.
- Current behavior: the investor frontend self-hosts the `Instrument Sans` and `Newsreader` variable fonts and uses the BANXUM redesign palette through the production token layer. The Marketplace page uses the approved editorial heading and account-aware supporting copy, displays the configured minimum investment, labels the selected currency balance as available to invest, and exposes the authoritative Smart-Invest state. Marketplace structured filters can be saved as the investor's one active rule and route to the Smart-Invest page; search text, sorting, and focused/detailed view are not persisted. Focused rows follow the redesign's Company, Yield, Term, Collateral margin, Available to invest, and Availability order. Search, filter/sort controls, the Detailed secondary row, loan status/rating/currency/refinancing provenance, funding progress, and all existing investment flows remain intact.
- Design decision: `website_redesign/` is a visual/IA reference, not executable production code. Smart-Invest is a server-owned discovery and first-publication alert rule, never an automated investment mandate. The setup wizard has five steps only: collateral, currency, optional minimum yield, optional maximum term, and review. The design-reference repayment/reinvestment and originator-concentration questions are intentionally excluded because the product neither auto-invests nor enforces a concentration cap. Fabricated 30/60-day capacity forecasts remain excluded; financial eligibility and investment actions continue through the ordinary server-enforced flow.
- Remaining backend/API dependency: none for the one-rule Smart-Invest foundation, matching projection, transactional match alert, Marketplace save action, or dashboard widget. The marketplace preview still omits some authenticated detail fields; add them only through backend investor projections after product/compliance approval, never by copying disclosure logic or financial calculations into the frontend.
- Suggested improvement: continue the redesign route by route while retaining the current menu and data contracts. Recheck the opportunity desk with production-scale row counts, add backend pagination before the list becomes large, and conduct a final keyboard/screen-reader pass after the remaining investor screens adopt the new tokens.
- Priority: important.

## 2026-08-06: Smart-Invest Rule And Setup Wizard

- Screen or component: Smart-Invest menu route, five-step setup wizard, manual criteria editor, Marketplace `Save Smart Filters` action, dashboard match widget, and active/inactive rule state.
- Current behavior: an eligible investor can activate one server-owned rule from structured Marketplace criteria, review current matching opportunities, adjust it, or deactivate and clear it. Smart-Invest is a peer navigation item immediately after Investment Opportunities, not an indented child. The wizard asks only about collateral, CHF/EUR scope, optional minimum yield, optional maximum term, and review. It has no repayment/reinvestment preference and no originator-concentration step. A newly published match creates one transactional alert per investor/loan pair; it never reserves funds or places an order. The redesigned dashboard shows currency-separated invested principal, schedule-backed upcoming payments, received interest, idle balances, required actions, and the current Smart-Invest rule/matches without combining currencies or fabricating reinvestment. Clicking a matching loan on either surface opens the same opportunity sheet and ordinary reviewed investment flow. Superadmin read-only impersonation can view but cannot change the rule.
- Design decision: preserve the v9 editorial hierarchy and rule-state treatment while keeping every financial action explicit. Keep Smart-Invest adjacent to Investment Opportunities as a separate first-class route. Dashboard values must remain server-projected and currency-separated. Do not reintroduce the design-artifact concentration, repayment, or reinvestment questions unless a later product decision introduces an enforceable portfolio-policy model.
- Suggested improvement: perform a final production-data visual pass for long Loan Originator names, zero-match and many-match states, keyboard focus inside the wizard, and small mobile viewports. Keep risk wording visibly adjacent to matching results.
- Priority: important.

## 2026-08-03: CHF/EUR Currency Exchange Redesign

- Screen or component: investor Currency & FX route, conversion preview, executable-quote handoff, balances, availability notices, and exchange history.
- Current behavior: the page now follows the `website_redesign/fx.html` composition while retaining BANXUM's existing CHF/EUR-only launch scope and audited execution flow. A large converter shows source and target currencies, source balance, target proceeds, platform fee, and the effective rate net of fees. The effective rate is centered in the conversion action band and Convert sits in that same row; the reference design's EUR-only lending explanation and incoming-payment conversion row are intentionally omitted. A compact right rail shows CHF/EUR balances and the material FX controls. History remains a real self-scoped backend projection and now presents Date, Converted, Rate net of fees, and Received rather than fabricating provider/reference fields BANXUM does not store.
- Design decision: live amount previews are computed by a non-persistent backend endpoint using the same provider freshness/sanity validation, configured fee, exact minor-unit rounding, and daily-limit logic as executable quote issuance. The browser never fetches or calculates a provider rate. Previewing creates no legal or append-only quote evidence; Convert requests a fresh 60-second executable quote and then enters the existing terms/email-code confirmation flow. CHF/EUR are the only currencies shown. Weekend, configured holiday, and temporary-provider-unavailable states remain explicit and fail closed while balances/history stay readable.
- Remaining backend/API dependency: none for the implemented CHF/EUR conversion and history screen. Yahoo availability and approved provider terms remain operational go-live dependencies. Future currencies, richer provider provenance in history, or a persistent indicative-rate feed require explicit backend contracts and must not be inferred in the client.
- Suggested improvement: validate rate/fee legibility with production-sized history, review the converter's keyboard and screen-reader announcement order, and keep the mobile source/target relationship clear without replacing exact amounts with decorative charts.
- Priority: important.

## 2026-08-04: Portfolio Redesign And Data-Grounded Risk Widgets

- Screen or component: investor Portfolio route, My loans table, earnings calendar, portfolio-spread, collateral-spread, and borrower-default panels.
- Current behavior: the Portfolio route now follows the redesign while retaining the live self-scoped holdings, Activity, and Orders projections. All money remains integer-minor-unit data rendered with the shared currency-aware formatter. The portfolio-spread widget uses current concentration, purpose, disclosed LTV, collateral type, and current late/defaulted exposure; it does not infer a historical on-time-payment ratio from schedule-event rows. Collateral classification uses the loan's explicit collateral type, while weighted LTV includes only secured holdings with a disclosed LTV. Default-interest figures come from each loan's configured annual `default_penalty_interest_bps`; zero means not configured. Recovery copy shows the universal non-overridable order of Garanta legal costs/recovery fee, penalty/default interest, contractual interest, then principal; loan terms may change amounts due but cannot move principal ahead of another due tier. Collateral values can change and recovery timing is not guaranteed.
- Design decision: preserve the redesign's four-widget composition without presenting reference-prototype assumptions as live financial or legal terms. Do not add fixed daily penalty rates, fixed court timelines, guaranteed collateral outcomes, or client-derived payment-performance history. Where the API cannot prove a metric, use a narrower current-state metric or add an authoritative backend projection first.
- Remaining backend/API dependency: a historical payment-performance score and project-specific recovery-duration estimate require canonical servicing/reporting projections and approved disclosure semantics before they can appear. The current implementation deliberately omits both.
- Suggested improvement: review dense expanded-panel copy and chart labels with legal/compliance, test long borrower and collateral labels, and retain the no-page-overflow behavior at 390px, 768px, and desktop widths.
- Priority: important.

## 2026-08-04: Portfolio Tabs, Tables, And Empty States

- Screen or component: investor Portfolio route, `My loans`, `Activity`, and `Orders` tabs, primary-order information tooltip, portfolio insights, and no-data states.
- Current behavior: `Activity` and `Orders` now use the same unframed, strong-rule financial-table language as Marketplace and `My loans`, while preserving all existing dates, references, categories, amounts, identifiers, allocation values, and status explanations. The four portfolio-insight widgets sit below the selected tab and remain available when switching between populated or empty Activity/Orders views. They are hidden only when the selected currency has no active holdings, because calendar, concentration, collateral, and default metrics would otherwise be misleading. Empty holdings and orders provide direct Marketplace/Orders actions. The former full-width primary-order notice is now an accessible hover/focus/tap tooltip next to the Orders tab.
- Design decision: tab selection changes the transaction dataset, not the investor's underlying portfolio insight. Currency selection therefore remains available on every tab and controls the persistent holdings-derived widgets. Wide Activity and Orders tables scroll only inside their own container; the focused `My loans` table has no desktop/tablet overflow and enables contained horizontal scrolling only at narrow widths where its columns cannot fit.
- Remaining backend/API dependency: none for this behavior. Server-side pagination will be required before Activity or Orders histories become large enough that returning the complete self-scoped dataset affects response or rendering performance.
- Suggested improvement: keep this header-rule, restrained-row, tabular-number treatment as the baseline while redesigning the remaining investor tables page by page. Test unusually long loan titles, localized status labels, and high-volume histories before launch; do not solve long histories by shrinking text below the established table scale.
- Priority: important.

## 2026-08-04: Portfolio Insight Grid And Compact Order References

- Screen or component: Portfolio insight widgets and the `Orders` table identifier columns.
- Current behavior: the four holdings-derived widgets form two equal-width cards per row when the content area can support them. Opening either card places its full detail panel across the entire width immediately below that two-card row. At 860px and below, each widget expands to the available tab/content width and its detail follows the selected card directly. Orders use a numbered compact reference (`#1`, `#2`, and a shortened identifier) plus an unframed copy icon; the loan column uses the bold loan title plus an equivalent icon. Hover/focus text and accessible names preserve `Copy order ID` and `Copy loan ID`, while the complete identifiers remain out of the visual hierarchy.
- Design decision: insight cards should scan as a balanced two-column dashboard on wide screens without making their expanded analysis compete for half-width space. On narrow screens, legibility takes priority over retaining two columns. Copy controls are utilities rather than primary actions, so they have no border, pill, padding, or visible label in dense tables.
- Remaining backend/API dependency: none. Compact references are presentation-only and always copy the authoritative complete backend ID.
- Suggested improvement: validate widget heights with production-scale labels and translated copy, and consider a shared icon-only utility tooltip primitive if the same compact identifier pattern is adopted across more investor tables.
- Priority: important.

## 2026-08-04: Secondary-Market Redesign And Authoritative Buyer Economics

- Screen or component: Secondary Market `For sale now`, `Sell a holding`, and `Secondary market activity` tabs, buyer listing table, seller summary, and buyer detail modal.
- Current behavior: the route now follows the redesign's editorial hierarchy and three-tab navigation while preserving the existing anonymous browse, full-holding listing/edit/cancel, filtered activity, terms, risk acknowledgement, schedules, and sensitive-action flows. Buyer rows show server-owned outstanding principal, transfer asking price, premium/discount, remaining unpaid installments, and total buyer cost. Loading, error, empty, frozen, and read-only states remain distinct; frozen/read-only viewers can inspect buyer-safe listing detail but cannot request a code or purchase.
- Design decision: do not estimate an investor's effective annual return in the browser. Actual yield depends on purchase price, accrued interest, fees, repayment type, timing, future servicing changes, and the complete cash-flow schedule. Until an approved backend yield projection exists, the table uses authoritative buyer total cost and the premium/discount explainer remains qualitative. Seller availability copy distinguishes immediately listable, non-performing approval-required, and funded-awaiting-disbursement holdings.
- Remaining backend/API dependency: an effective annual buyer-yield or IRR column requires a canonical server-side calculation, definition, rounding policy, disclosures, and tests for every repayment type. It must not be restored as a client-side approximation.
- Suggested improvement: review long mixed-currency listing tables, compact activity filters, and buyer-detail schedule density at production scale. Preserve contained horizontal scrolling on narrow screens and keep seller identity/economics out of every buyer projection.
- Priority: important.

## 2026-08-04: Investor Data-Table System Pass

- Screen or component: public loan preview, Dashboard opportunities, Balances lots, Portfolio Activity and Orders, Secondary Market browse/sell/activity, Documents, FX history, and loan/investment schedules.
- Current behavior: investor-facing datasets now share the redesign's open financial-table grammar: a strong top rule, restrained uppercase headers, consistent row rhythm, tabular right-aligned amounts, subtle separators and hover feedback, compact utility actions, and horizontal scrolling contained within the table rather than the page. Marketplace, Portfolio My loans, FX history, and secondary buyer listings retain their domain-specific responsive compositions; legacy card frames were removed from public/dashboard loans, balance lots, seller holdings, secondary activity, and document history. Schedule tables retain their detail/modal containers and totals rows. Filtered Documents now shows a deliberate empty state instead of a header-only table.
- Design decision: visual consistency does not mean forcing every dataset into identical columns or mobile behavior. Operational schedules remain denser than browse tables; marketplace and secondary buyer rows retain their information hierarchy; admin-console tables remain intentionally separate and work-focused. Wide financial datasets scroll internally at narrow widths rather than shrinking money, statuses, or legal references below the established type scale.
- Remaining backend/API dependency: high-volume Activity, Orders, Documents, and balance-lot datasets need server-side pagination before production volume makes full self-scoped responses expensive. No client-side truncation was introduced in this pass.
- Suggested improvement: validate long translated labels, large histories, mixed currencies, and screen-reader table navigation with production-scale fixtures. Consider stacked mobile rows only for the highest-frequency user workflows after usability testing; retain native table semantics for schedules and audit-like histories.
- Priority: important.

## 2026-08-04: Navigation, Add Funds, And Select Controls

- Screen or component: investor sidebar, sticky header, Add Funds bank-transfer modal, registration, Marketplace filters, payout controls, QA state switcher, and admin select inputs.
- Current behavior: the primary navigation now uses `Investment Opportunities` and `My Portfolio`; Notifications remains available from the persistent header bell and no longer consumes a duplicate sidebar row. `Add Funds` is the single action label on Dashboard and Balances, and a persistent green header action opens the existing self-scoped bank-transfer instructions with an explicit CHF/EUR selector. On mobile, balances collapse while Add Funds stays beside the notification control. Sidebar labels remain single-line at the supported 320px minimum viewport. Native select elements retain platform/mobile accessibility while sharing one deliberate surface, chevron, hover, focus, and disabled treatment across investor, onboarding, and admin interfaces.
- Design decision: technical and regulatory nouns such as deposit reconciliation and deposit protection remain unchanged where they describe actual concepts; only the user command is normalized to `Add Funds`. The Notifications route and history screen remain intact even though its sidebar link was removed. The header action reuses the canonical deposit-instruction projection and does not introduce a second funding workflow or any client-side bank-account logic.
- Remaining backend/API dependency: none for these shell and control changes. Available funding currencies continue to come from the backend instruction projection.
- Suggested improvement: validate unusually long translated navigation labels before localization and confirm native option-menu rendering on the supported iOS, Android, Windows, and macOS browser matrix.
- Priority: important.

## 2026-09-07: Loan Originator Subscription Opportunities And Holdings

- Screen or component: Investment Opportunities common table/detail, finite
  subscription review, funding-close exception states, My Portfolio holding detail, activity, documents,
  and secondary-market buyer detail.
- Current behavior: direct BANXUM loans and Loan Originator claims share the primary
  opportunity table. The common rate column is `Yield`; an originator row carries a
  Loan Originator badge/name and opens a product-aware detail with anonymized
  borrower disclosure, underlying coupon, nominal participating yield, separate
  interest/penalty participation, minimum investment, funding deadline, maturity,
  current outstanding/sellable principal, and post-boundary cash flows. Current
  subscriptions reserve balance at par after clickwrap/email-code confirmation.
  Successful close creates holdings and immutable post-boundary entitlements in the
  same transaction. The boundary installment belongs entirely to the LO and its
  actual bank receipt is recorded separately. Portfolio and
  activity identify activated originator claims and show investor cash-flow projections.
  Performing originator holdings may be resold at par or a discount, not a premium.
- Design decision: never present the underlying coupon as a promised investor IRR,
  never imply returns are guaranteed, and never expose private final-borrower legal
  name unless explicitly published per loan by an admin, originator settlement status,
  or internal import references. Explain that no
  investor interest accrues during funding or on the boundary installment; one unit
  of cash buys one unit of principal at activation; later interest and penalty rights
  use separate declared participation. Failed close preserves the reservation and
  alerts operations; cancellation restores the original balance-lot amounts and
  ageing dates. No originator recourse/buyback exists.
- Remaining backend/API dependency: non-performing originator-claim resale is
  intentionally blocked until an approved impaired-accrual/default-entitlement
  pricing projection exists. Do not design around or bypass that v1 boundary.
- Suggested improvement: run final mobile/tablet usability and accessibility review
  with long originator names, mixed currencies, near-deadline rounds, close-failure
  and legacy upgrade exceptions, empty projections, and cancellation/refund copy. The
  review should preserve the existing marketplace table hierarchy rather than
  introducing a separate marketplace.
- Priority: important.

## 2026-08-04: Loan-Originator Retention Disclosure

- Screen or component: originator-claim marketplace detail, investment terms, and portfolio holding detail.
- Current behavior: a positive server-owned retention percentage is disclosed as the minimum share of current outstanding principal retained by the named Loan Originator. The holding view states only that the retained claim is not offered to investors; it does not infer historical cash flows, loss parity, recourse, or recovery outcomes in the browser. A zero value is intentionally omitted.
- Design decision: describe the mechanism factually as an ownership/availability floor, not as protection or a guarantee. All retained and sellable amounts are calculated by the backend with ceiling rounding in minor units. Investor screens consume only the percentage and authoritative schedules supplied by the API.
- Remaining backend/API dependency: none for the current disclosure. Any future comparison of originator and investor realized losses or recoveries requires a dedicated server projection and approved legal wording.
- Suggested improvement: validate the disclosure with legal/compliance and test 0%, fractional percentages, 99.99%, long originator names, and narrow screens without promoting the retention percentage into an implied credit rating.
- Priority: important.

## 2026-10-09: Session Expiry, Blocked Accounts, Logo Home Link

- Screen or component: investor log-in screen, expired-link screen, portal "Account access" page, site/sign-in/registration logos.
- Current behavior: sessions end 2 hours after login; the next API call returns the investor to Log in with a "Your session has expired" notice (kept until a new link is requested). A restricted, locked or closed account with an open session sees an "Account access" page with the status and support address instead of portal screens; a valid link of a restricted or locked account shows "Your account is restricted/locked" with a Contact support button. The expired-link screen keeps its email field while typing and sends only on Enter or the button. Every logo outside the portal links to the Overview when an investor is signed in and to the home page otherwise.
- Suggested improvement: decide whether to warn shortly before the 2-hour limit (the API does not expose the expiry time yet), and review the Account access page copy with compliance for each status.
- Priority: nice-to-have.

## 2026-10-09: KYC Verification Under Review

- Screen or component: investor Verification page (KYC status) and registration KYC step.
- Current behavior: a case that waits for an admin decision (decline, manual review, AML hit, provider re-check) shows "Verification under review" with "Your verification is under review. We will contact you." and no start button; the API refuses a new session with the same text (409). AML hits read as manual review in the investor API. The start button returns only after an admin requests re-verification.
- Suggested improvement: keep the copy non-revealing (never name sanctions, PEP or adverse media); consider a restart action on the "Waiting for verification result" state when the Didit session has expired, and a timeline step label for "under review".
- Priority: nice-to-have.

## 2026-10-09: Secondary Buy Modal Price Lock

- Screen or component: secondary-market Buy modal ("For sale now" > Buy).
- Current behavior: the review rows (principal, sale price, accrued interest, taker fee, total cost) come from the freshly loaded listing detail, and the purchase sends those reviewed values. If the price changed before confirm (seller edit, repayment repricing, or a new day's accrued interest), the server rejects the purchase with nothing charged; the modal shows a "Price changed" banner, reloads the new price, unticks the terms checkbox and keeps the entered email code so the buyer can review and confirm again.
- Suggested improvement: highlight which rows changed (old vs new total) and consider a short note that accrued interest grows daily, so a review left open overnight must be refreshed.
- Priority: nice-to-have.

## 2026-10-09: Notification Centre Content

- Screen or component: investor Notifications page and header bell.
- Current behavior: only real notices are listed (sign-in links and confirmation codes are left out and never counted as unread). Each row shows the notice time (when the event happened, platform clock) and a short label such as Deposit, Withdrawal, Funding, Loan status or Balance reminder. New notices cover deposits, withdrawals, forced returns, penalty mode, payout IBANs, currency exchange, primary orders, funding close/cancel, order release and Late/Defaulted loans; each opens its balance, FX, portfolio or holding page.
- Suggested improvement: filter chips by label, group same-day balance reminders of different currencies, and a calmer layout for long bodies (the full email body is shown today).
- Priority: nice-to-have.

## 2026-10-09: Login Links, Repeated Registration, Phone Correction

- Screen or component: login-link and registration emails, registration step 2 ("Verify your phone").
- Current behavior: login emails link to `/login#token=...`; the portal removes the token from the address bar before any request. A registration for an address that already has an account gets the same "Magic link sent" screen; the owner gets an email that says the account already exists (with a sign-in link for investors). Nothing stored changes. On the phone step, "Send SMS" uses the number typed at registration; until the phone is verified, this corrects a wrong stored number. The page does not show the stored number when it differs.
- Suggested improvement: show the stored number (masked) on the phone step with an explicit "Change number" control, and review the "account already exists" email copy.
- Priority: nice-to-have.

## 2026-10-09: Withdrawal Review, Forced Returns and Penalties in Activity

- Screen or component: Withdraw modal (Review step) and the My investments > Activity table.
- Current behavior: the Review step shows the destination IBAN and account name before the email code. Activity lists each day-60 penalty charge ("Penalty charged: balance past the 60-day limit", tag "penalty") and labels forced returns "Forced return to your bank account" (tag "forced return"); a cancelled one reads "Forced return cancelled". Payee names come from the verified payout IBAN.
- Suggested improvement: link a forced-return or penalty line to a short explanation of the 60-day rule and the payout IBAN used; group daily penalty lines per lot when there are many.
- Priority: important.

## 2026-10-09: Completed Holdings, Holding Page States, Borrower Document Download

- Screen or component: My investments (new "Completed" tab), holding page, loan page "Documents" card.
- Current behavior: repaid, sold and closed holdings are listed under My investments > Completed with the result (Repaid, Sold, Written off), invested amount and interest received; Open goes to the holding page. The holding page counts borrower installments (not payment rows), shows "Matures <date>" for Loan Originator claims, and a loan in default opens on the overdue payment; its future installments read "Not expected". Each borrower document on a loan page has a Download button; a refused download shows the reason under the list.
- Suggested improvement: add a final summary for completed holdings (total received, return, end date) and filters by result; decide the wording for future installments of a defaulted loan with compliance.
- Priority: important.

## 2026-10-09: Invest Results, Seller Pricing, Own Listings

- Screen or component: invest page result step, Smart-Invest batch review, loan quick-view sheet, listing form, "For sale now".
- Current behavior: the invest result shows what the server did: "Order placed" (reserved), "Order partly placed" (only part of the amount was left) or "Order not placed" (less than the minimum was left; red banner, nothing moved). A new amount or Back to the amount step needs the terms ticked again. The batch review needs the same risk acknowledgement as a single investment. The listing form shows the server's transfer price, accrued interest, maker fee and net proceeds for a sale today. Your own listing shows a grey "Your listing" pill instead of Buy and opens a view without terms or code. Amount fields keep the decimal comma and accept ' ’ and spaces.
- Suggested improvement: design the partly placed / not placed states (icon, next step such as "Find another loan"), show the accrued-interest growth per day on the listing form, and style "Your listing" rows (badge, muted row) at phone width.
- Priority: nice-to-have.

## 2026-10-09: Frozen Account Banner, Account Page, Phone Tables, Dialogs

- Screen or component: investor shell banner (day-60 penalty mode), Account page (payout IBANs, pending withdrawals), phone tables (Account lots, Activity, Orders, Documents, Smart-Invest matches), all dialogs, FX confirmation.
- Current behavior: the frozen state comes from the balances API; one red banner on every page says what is frozen, the daily penalty, and to add a payout IBAN (button opens the IBAN dialog); Invest, FX, secondary trades and Add Funds are blocked with the reason. IBANs show Verified / Pending verification; pending withdrawals list forced returns with a "Forced return" chip. Below 640 px tables become stacked label/value rows. Dialogs take focus, keep Tab inside, give focus back, and ignore Escape while a money action runs. The FX confirmation counts the quote down and offers "Refresh quote". Unknown addresses show a "Page not found" page.
- Suggested improvement: design the stacked phone rows (spacing, which fields lead), a compact variant of the frozen banner after the first visit, the empty-IBAN state of the Withdraw dialog, and the 404 page artwork. Portfolio widget cards are still whole-card buttons (long accessible names) and some pages jump heading levels (Banner titles are h4).
- Priority: important.

## 2026-10-12: Transactional Email Layout (Re-skin)

- Screen or component: every transactional email (login link, confirmation code, investor notices, Smart-Invest matches, document emails), shared layout in `communications/services.py`.
- Current behavior: the layout follows the site: white card with hairlines on a light grey page, the black Banxum wordmark (hosted PNG, `/brand/banxum-email-logo.png`) in the header, a square status tag (green confirmation, red important, black action needed, grey information), Archivo with Helvetica/Arial fallback, pill buttons, key/value rows and a black footer with the white wordmark. Confirmation codes show large in their own box; expiry times read as Zurich wall time.
- Suggested improvement: test in Outlook desktop, Gmail (web and app, dark mode) and Apple Mail; decide whether to embed the logo as an inline image instead of loading it from the app domain; consider a dark-mode logo variant and per-topic illustrations for key events (deposit credited, loan defaulted).
- Priority: important.

## 2026-10-13: Investor Loan Notes

- Screen or component: My investments > investment page, "Loan notes" section.
- Current behavior: the section lists all public notes in newest-first order. Each item shows the full title, full message, and publish date. A public-and-email note opens this section from the notification bell. Email-only notes do not appear.
- Suggested improvement: review the typography for very long messages and decide whether note types need visible labels when more note categories are in regular use.
- Priority: nice-to-have.

## 2026-10-16: Money Goes Back to the Bank After 58 Days

- Screen or component: Account page (currency cards, lots table, alerts, "Rules for your money"), nav badge, Help FAQ "Balances and deadlines", pending withdrawals, ageing emails (day 25/46/53/56/57 reminders, day-58 last day, day-59 and day-60 notices without IBAN), deposit-credited and forced-return notices.
- Current behavior: owner decision "Goes back to your bank automatically after 58 days." Each lot shows "Nd holding time left" / "Day 58: last day" / "Due back to your bank" with "Goes back to your bank on <date>" or "Return due since <date>"; the age bar fills over 58 days. The cards show Withdraw-only ("Day 58: last day, can only be withdrawn today"), "Due back to your bank" ("Not invested within 58 days") and "Goes back to your bank on <date> if not invested". Money due back without a verified IBAN in its currency gets a warning banner "Add a verified bank account so we can return your money" with an "Add payout IBAN" button. The 60-day legal limit and penalty mode after day 60 are unchanged and still named where they apply. The day count comes from the API (`auto_return_after_days`); static texts (FAQ, deposit note) use 58.
- Suggested improvement: design a compact countdown for the last days (56-58) on the cards and lots, decide whether the return banner should also appear in the shell (like the frozen banner) on days 59-60, and give the day-58 and day-59 emails their own visual treatment (the IBAN the money goes to, or the add-IBAN action).

## 2026-10-16: Secondary Market Fees, Par-Or-Discount Prices, FX Switched Off

- Screen or component: secondary market "For sale now" (explainer band), Sell a holding (listing form), Buy dialog, investor navigation and `/fx`.
- Current behavior: the seller fee is 2% of the price and there is no buyer fee (owner decisions 2026-10-16, rows 2 and 3); the listing form and the Buy dialog show the fee lines from the API, and the Buy dialog leaves out the "Taker fee" line when it is zero. A sale price is par or a discount (row 4): the price field takes at most 10000 bps (100%), shows "The sale price can be at most 100% (par)." above that, and blocks Confirm; the explainer band is "Why do loans sell at a discount?" with two cells (discount, par), and the premium texts are gone. Currency exchange is switched off (row 6, platform setting `fx.enabled`): the FX menu item is hidden and `/fx` shows the dashboard at `/dashboard`; past conversions still show in activity and statements. In the fixture preview FX is off too; set localStorage `banxum.preview.fx` to `on` to review the FX screens.
- Suggested improvement: replace the technical "Sale price bps" field with a percent field or a slider capped at 100% with a few presets (100%, 99%, 98%, 95%); show the seller fee rate next to the fee line; decide whether `/fx` should show a short "Currency exchange is not available at the moment" page instead of the dashboard, and whether FX notifications (past exchanges) should open the Account page while FX is off. Texts that still mention FX as an option (KYC pending note "Deposits, investing, withdrawals and FX unlock...", the 60-day explainer "FX conversion does not reset this limit", Help answers about FX, and the ledger reminder emails "invest or exchange") should be reviewed while FX is off.
- Priority: important.

## 2026-11-09: U33 Profile & Settings (Phase 17.1 S5)

- Screen or component: `/settings/personal`, `/settings/security`, `/settings/bank-accounts`, `/settings/notifications`, `/settings/preferences` (`/settings/verification` and `/settings/agreements` open Personal details with that section expanded), the Add a bank account dialog (also opened from the account menu's shell dialog and the frozen-account banner), the account menu entries (`frontend/src/portal/screens/account/`).
- Current behavior: the design's ps-page with one address per tab. Personal details shows only what today's API has (email, verified phone as "ending in NN", full name, investor type, investor ID); verified data is read-only with "Contact support to change" (an email to support with the investor reference; U33-DEC-26) instead of the design's Edit buttons. Verification details lists account, phone, identity check (Didit) and financial access with today's status; the API gives no decision date, so none is shown. Accepted agreements lists the acceptance-evidence documents with version and date and links to Documents. Security states today's sign-in (single-use link by email, 15 minutes) and the PIN card (change, forgot, create) in p73 dialogs. Bank accounts shows each payout IBAN with "Verified · date" or "Pending verification" (the API's `verification_status`), the line "Money that goes back to your bank in {currency} is sent to this account." on the default return account, "Use for returns" on the other verified accounts (email code + PIN, a change notice, no waiting period) and the design's "Change" (it adds a new account in that currency), an "Add {currency} account" card for a currency without one and "Add a bank account"; no 48-hour pause text and no remove (U33-DEC-05, 2026-11-09). Notifications lists the service emails that are always sent and the one switch, "News from Banxum" (today's marketing consent; U33-DEC-30). Preferences has Appearance, Number format, Language (English or Deutsch, saved in the account since 2026-11-10), the time zone as text (Europe/Zurich, no selector; U33-DEC-32) and "Close account", which explains the request and prepares an email to support (U33-DEC-28).
- Suggested improvement: when the backend steps land, add password + second factor and recovery to Security (U33-DEC-01, Phase 17.3), the verified address/date of birth/nationality if the platform stores them, the KYC decision date, self-declarations and the next periodic review (U33-DEC-27, Phase 17.7), Smart Invest in-app/email channels (U33-DEC-30, Phase 17.2), the closure-request endpoint with its receipt confirmation (U33-DEC-28, Phase 17.2), and save Appearance in the account if wanted (Number format and Language are saved since 2026-11-10). Design a bank card without a bank name (the API has none; the card shows the account holder) and the empty "Add {currency} account" card.
- Priority: important.

## 2026-11-09: U33 Help And "Help With This Step" (Phase 17.1 S5)

- Screen or component: `/portal/help` (`HelpScreen.tsx`, answers in `help/helpContent.ts`), Contact support and How investing works dialogs, `parts/HelpWithThisStep.tsx`.
- Current behavior: the design's Help page (search, topics, common questions, support box). Every answer is rewritten for today's platform: sign-in link + PIN and email code, repayments credited to the Banxum balance (U33-DEC-02), the holding time from the balances API (day 56 last day since 18.4) with the 60-day limit, the minimum shown per opportunity (Swiss-borrower places explained without numbers), resale of the whole position at most 100% with the seller fee shown before confirming, late/default as the investment page shows them (no day thresholds), interest on the outstanding principal (no day-count formula), no ratings, no universal "0 fees". Contact support prepares an email to support in the investor's email app (topic, message, investor reference) and says so; nothing is "sent" by the page. The support box shows the email and the operator, no hours. "Help with this step" (button + explanation dialog) is ready but not yet used by a flow.
- Suggested improvement: the Help message endpoint with receipt confirmation, error/retry and page context (U33-DEC-35, Phase 17.2), confirmed support hours (U33-DEC-35), and the answer texts of U33-DEC-03 (56 days, notices 10 and 3 days before), U33-DEC-04 (no penalty), U33-DEC-06/07 (0-102%, capped 2% fee, no fee on accrued interest), U33-DEC-09 (Due/Late 15/Default 60), U33-DEC-10 (Actual/365) and U33-DEC-13 (QES assignment declaration) when those steps land. The flow slices add "Help with this step" to the amount, review, withdraw and sell steps with the step's live values.
- Priority: important.

## 2026-11-09: U33 Sign-In, Registration, PIN Gate And Verification Screens (Phase 17.1 S5)

- Screen or component: `/login`, `/register`, the post-login "Create your security PIN" screen, `/kyc/callback`, `/verification` and the account-access screen (`portal/screens/account/auth/`, `KycStatusScreen.tsx`, `AccountBlockedScreen.tsx`).
- Current behavior: the create-account module's layout (U33Skin layout="auth") with Light/Dark switch and EN only (DE disabled). Sign-in is the design's "Welcome back / Send sign-in link" on today's magic link, with "Check your email" ("If an account exists for this address..."), expired-link and blocked ("We need to review your account", no status named before sign-in) states. Registration follows the four design steps on today's flow: details and the server-published agreements (documents open in a new tab), the email link opened in this browser, the SMS code (number can be corrected inline), the PIN (no email code at registration), then Didit with "in review", "ready" and "continue verification" states; a declined check continues in the account's Verification page. Verification and Account access are portal pages in the Profile & Settings style; provider flags (sanctions, PEP, adverse media) always read "In review". In preview mode the Didit hand-off and result are simulated on the registration screen.
- Suggested improvement: password + second factor sign-in and recovery screens, and the migration screen for existing accounts (password + factor + PIN, U33-DEC-01/-29, Phase 17.3); design the "Your session has expired" notice and the inline phone editor (no design state); a company-investor path (U33-DEC-29) beyond the "Investing as a company?" note; re-verification states once U33-DEC-27 defines them.
- Priority: important.

## 2026-11-10: Late, Default and Contract Termination Days (U33-DEC-09)

- Screen or component: investment page payment update and recovery panels (`frontend/src/portal/screens/portfolio/parts/LoanUpdates.tsx`), public FAQ, the late-payments guide and the Statistics "How we count" text.
- Current behavior: the server sets the status: Due for the first 14 days (with the real days), Late from day 15, Default from day 60, or the loan contract's own days. When Banxum records the contract termination, the late panel lists "Contract terminated" with its date after the missed payments, and the recovery panel says "The loan contract was terminated on <date>." The public texts say day 15 / day 60, that a contract can set other days, and that default does not end the contract by itself.
- Suggested improvement: the stage-by-stage recovery presentation of U33-DEC-22 (Phase 17.4) should take the termination as one of its stages; show the loan's own days on the investment page when they differ from the platform days.
- Priority: important.

## 2026-11-10: Contact Support and Account Closure Request (U33-DEC-35, U33-DEC-28)

- Screen or component: Help "Contact support" dialog (`frontend/src/portal/screens/account/parts/ContactSupportDialog.tsx`) and Preferences "Close account" dialog (`settings/PreferencesTab.tsx`).
- Current behavior: "Send message" posts the topic and the message to the team by email (`POST /api/v1/investor/portal/support-requests/`); the result shows "Message sent", the reference (SUP-YYYY-NNNN) and "We sent a confirmation to <email>. Our team answers by email." A failed send keeps the message, shows the reason and "Try again" with the same request key. "Send closure request" shows "Request received", the reference (CLS-YYYY-NNNN) and that the account is not closed yet. The design's "We answer within one business day" and support hours are left out until confirmed. The preview mode sends nothing and says "Demo: nothing was sent." The design's project context block ("About your investment") is supported by the API (`context_type: holding`) but no investment page opens the dialog yet.
- Suggested improvement: open Contact support from the investment page with the project context block; show support hours and the answer time once confirmed (U33-DEC-35).
- Priority: important.

## 2026-11-10: Smart Invest Notification Channels (U33-DEC-30)

- Screen or component: Smart Invest page ("Notification settings" under the matches), Profile & Settings -> Notifications (Smart Invest row, "Manage"), `parts/SmartInvestChannelsDialog.tsx`.
- Current behavior: the dialog with the refined design texts ("Notify me about matching investment opportunities", "In the app", "By email") and "Save preferences"; the line under the matches says where new matches go ("New matches appear in your notifications.", "New matches are sent to you by email." when only email is on, or "Match notifications are off."). The settings row shows "In-app notifications on/off · Email notifications on/off" and "Available after setup" or "Smart Invest paused". The row is shown only when Smart Invest is available to the investor (identity check approved).
- Suggested improvement: none required; review the wording of the summary line.
- Priority: nice-to-have.

## 2026-11-10: Signed-in Devices and Sign-in History (U33-DEC-25)

- Screen or component: Profile & Settings -> Security (`frontend/src/portal/screens/account/settings/SecurityDevices.tsx`).
- Current behavior: the design's "Signed-in devices" rows (laptop or phone icon, device and browser, place and last activity, "This device" or "Sign out") plus a "Sign out on all other devices" row that the design does not have (U33-DEC-25 asks for it), and the "Sign-in history" disclosure with the design's table (Date, Device and place, Method, Result) and the retention period. The place is the country name from the edge proxy header, or "Place not known"; the design shows a city. The methods are today's ("Email link", "Password and email code" for admins) until U33-DEC-01. A new-device sign-in sends a security email.
- Suggested improvement: show the city when a geolocation source is chosen; add the U33-DEC-01 methods (password, authenticator, passkey) to the history labels when they exist.
- Priority: important.

## 2026-11-10: Interface Language de-CH (U33-DEC-31)

- Screen or component: the whole investor area (`frontend/src/i18n/language.ts`, `frontend/src/i18n/locales/de-CH*.json`); Preferences -> Language, the account menu's Language entry, the sign-in/registration header select.
- Current behavior: English and Deutsch (Swiss Standard German). The account menu entry opens the design's two options with a check mark; Preferences and the sign-in header use selects (English/Deutsch, EN/DE). The design's German dictionary covers about 830 texts; about 1,280 texts the design does not contain are drafted in the same tone and need a native-speaker review. German dates follow the design ("4. Okt. 2026"). Where one English text has two German meanings the code uses a context key ("Security" of a loan = "Sicherheiten", the account's "Security" tab = "Kontosicherheit"; "To" of a date range = "Bis"; the "View" button = "Ansehen"). Emails, the notification centre texts and messages from the server are still English, as are the public site and the admin console. The Forgot PIN dialog no longer shows the last phone digits in bold (one translatable sentence).
- Suggested improvement: review the drafted German texts in place (long words in buttons, tabs and table headers, mobile layout); check the German screens against the design's German state; decide the German notification and email texts with the backend step.
- Priority: important.

## 2026-11-19: Audit Step 1 Additions Without An HTML Reference

- Screen or component: My listings, My investments and the investment page (C03 "Pending" listing); credit file and opportunity security block (F16 list of the assets in the loan-to-value, "In the loan-to-value", valuation in another currency); opportunity and investment pages ("Banxum invests", Q04); public page `/alerts/stop` (Q14); Help ("How it works" part, Q24); admin securities (main, counts in LTV, valuation currency) and recovery stages (standard names, result).
- Current behavior: built with existing U33 components and texts. "Banxum invests" uses the design's `u102-co-label` with the platform's `InfoTip` dialog instead of the design's popover. The Stop page reuses the newsletter link page layout. The How it works part reuses the retired page's sections under the Help questions.
- Suggested improvement: designer review of these states and of the label explanation.
- Priority: nice-to-have.


## 2026-11-19: Audit Step 2 (18.3) Data Fields And Contextual Help

- Screen or component: "Help with this step" (amount and review: the design's explanation dialog; withdraw and sell: opened in place inside the dialog), Loan originators (About text), credit file (Updated date, Source of repayment), Profile & Settings (bank name on bank cards; date of birth, nationality and address from Didit, read-only).
- Current behavior: the help answers use the live values (minimum, balance, capacity, amount, withdrawable amount, price range, proceeds). The originator About text and the loan's Source of repayment are entered by the admin and left out when empty. The credit file's "Updated" date is the latest change of the loan, its checks or the borrower record. CH and LI bank names come from the SIX bank master (`import_six_bank_master <file>`; the platform team imports the official file); other IBANs show the name the investor typed, or no name. The verified address, birth date and nationality are shown only when Didit provided them (the nationality as a name for common codes, else the code).
- Suggested improvement: import the SIX file on each SIX release (a scheduled reminder); the full country list for nationalities with 18.13.
- Priority: nice-to-have.

## 2026-11-19: Audit Step 3 (18.4) Return Dates And Failed Returns

- Screen or component: Account (lot table, account notices, account rules), Add funds note, Help answer "What happens to money I do not invest?", Transactions, the balance emails (notices 14/10/3 days before the return, forced return, return failed), admin Finance (Failed returns, Record a returned transfer, Verify a return account from a deposit, Settlement calendars).
- Current behavior: day 56 is the last day and the return starts on day 57, or earlier when the bank is closed (each lot shows its own return date from the API). The design has no state for a failed return (Q23): Account shows it with the design's danger alert ("Your bank sent CHF ... back." with the bank's reason, "you can withdraw it, but not invest it. There is no penalty.", and "Add a bank account" unless the cause is on the bank's side) and the lot tag "Return failed"; the plain "due back" notice leaves that money out. Transactions show "Return sent back by the bank". The opportunity page and Review & sign count only money that can reach a direct loan's borrower by day 56 (F01). Admin tools use the admin console style.
- Suggested improvement: a designed state for "Return failed" (Account card and lot), the 14/10/3-day notices as a compact countdown on the cards, and an explanation near the usable balance when F01 leaves money out ("too close to its return date for this loan").

