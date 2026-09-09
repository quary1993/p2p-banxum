# Banxum Platform — developer handoff (v6.3)

Working prototype of a Swiss P2P-lending platform for first-time investors.
Everything is HTML/CSS/JS in one file; no build step, no server.

## Files

- **Banxum Platform v6.3 (standalone).html** — open in any browser, fully offline. Send this around to *see* the website.
- **Banxum Platform v6.3.dc.html** — the readable source. Markup sits inside `<x-dc>…</x-dc>`; all state, data and calculations live in the single `class Component` script at the bottom. This is the file to read when implementing.
- **README.md** — this file.
- v6 files are the previous milestone, kept for reference.

## Demo controls (not part of the product)

Account menu ("AK", top right) → *Demo · view the platform as*:

- **Invested** — the main persona: € 388,000 lent across 16 loans + € 100,000 free.
- **Fresh € 100k** — € 100,000 in the wallet, nothing invested, no rule. Start-from-zero flows: create the rule, commit to campaigns, watch Still funding fill.
- **New account** — no money, nothing invested.
- **↺ Reset the scenario** — returns rule, confirmations and commitments to the start.

All interactive state is session-only; reloading resets it.

## Product rules (non-negotiable in implementation)

1. **Red** is reserved for risk, lateness, penalties, refusals. Never for actions or neutral info.
2. **Green** is the profit colour (and the add-money action). Never a neutral state.
3. **No recommendations, no rankings, no matching.** The platform shows arithmetic and lets the investor decide. Copy states facts; urgency is expressed by data (deadlines, dots), not adjectives.
4. **Every figure must be derivable from the platform's data.** The prototype hand-carries some aggregate literals in markup (see "Dataset" below); the real build must compute them.
5. Nothing is ever committed without an explicit user confirmation. Every binding click is preceded by the full arithmetic of what it binds.

## Screens

- **Dashboard** — headline figures; "Waiting on your decision" panel: rule-matched allocation desk (tick/untick, equal split, review & confirm), closing-within-7-days dropdown (runway dots, rows open the loan sheet), rule status row, commitments receipt row. Income and invested/earned sections are collapsible (closed by default).
- **My investments** — "Still funding" runway cards (committed campaigns racing to their minimum; reserved amount, points-to-go / past-minimum, deadline; click → campaign sheet), then the loans table (sort, focused/detailed).
- **Investment opportunities** — commit-capacity bar (today / 30 / 60 days), two-ways fork (self-serve vs rule; card is state-aware), "Matched by your rule" desk (same live values as the dashboard desk), filterable list. Loan sheet: full loan detail + invest step with typed amount, quick chips, pledgeable repayments due before close, per-loan capacity notes, functional Confirm.
- **Rule (auto-invest)** — fork hero (guided ticket: 6 questions ≈ 2 min, or hand-set switches), conditions with live match counts, approval modal: allocation list with per-loan inspect (i), all/none, typed "Allocating" amount, capacity notes, denial gate, pinned confirm bar. Loans opened from the modal get a ← n of N → pager and a "bundle" footer instead of the invest bar.
- **My money** — statement card with a three-state selector (Today / Expected / With reinvestment: capital + interest accumulation, growth chart, "Put the money to work" CTA), then four stacked subsections (Earnings calendar, Spread details, Collateral, Protection) whose full-width detail panels open directly below each row; movements (running balances); **Secondary market** — listings + buy/sell rules; **Currency & FX**, **Documents**, **Notifications**, **Settings**, **Help**.

## Commitment model

- Binding capacity = free cash + repayments scheduled before each window closes, applied **in closing order** (`capAt(days) = idleFree + cumBy[days]`, `maxCap = capAt(60)`).
- Equal split: `perEach = max(100, min(floor(allocTotal / picked), ruleCeilings))`. € 100 is the platform minimum per loan.
- Typing above the maximum shows the ceiling warning + green "Solution · Add money" — the effective allocation clamps; Confirm greys and `confirmAuto` refuses when the final per-slice amounts exceed capacity.
- When arrivals fund part of an allocation, the modal says so explicitly (nothing binds beyond what has actually arrived).
- Confirmed commitments: reserved from balance (or "funds as repayments arrive"), listed in Still funding, excluded from further matching, shown on the not-lent card and the receipt row. A committed campaign's sheet shows "Already yours / Invest more", or a committed-only footer when nothing further is investable.

## Data model (all in the logic script)

- `raw` → `sched`/`payments`: per-loan payment tables (whole/cents display split, interest, principal, balance; collateral valuation + borrowed are borrower-side).
- Loan positions (`{ id: "i-…" }` rows): `lent, rate, term, made, out, next, amt, int, pri, sector, late, pen`.
- `payDays`: day-of-month → your August receipts. Sums to € 13,489.60 exactly.
- `oppRaw` (32 campaigns): `rate, term, purpose, security, col, val, bor, pen, pct, min, left, win, days`, optional `uw` originator.
- `listRaw`: secondary-market positions; `moveRaw`: account movements with running balances (re-chained to end at € 100,000).
- Compare-scenario constants: `PAID 32,683.00 · SCHED 35,786.40 · REINV 99,904.00 · FULL 138,494.00` on capital 488,000. Chart midpoint blend is 0.405 — derived by decomposing the old model's uplift (recycled payments 33.7% accrued by mid, wallet compounding 30.8%) and reweighting for the € 100,000 wallet. Replace with the real reinvestment simulation.

## The € 100,000 dataset

Investor-side figures were rescaled ×20 from the audited v6 model (linear in principal, so every amortisation row still reconciles); the wallet is exactly € 100,000; figures mixing wallet and book (the invested-vs-earned story) were **recomputed**, not scaled. Borrower-side facts (collateral valuations, originator registries) unchanged; campaign sizes were refreshed with varied factors. A residue audit script verified: payment rows sum to their month days, movements chain to the cent, interest+principal = payment on all 16 loans, compare figures recompute exactly.

Aggregate literals still hardcoded in markup (compute these in the real build): dashboard cards, € 388,000/€ 488,000 heroes, income "next 12 months", compare table, composition rings, money-page tiers, withdraw copy.

## Known demo limitations

- Add money page is instructional; deposits don't credit the balance.
- Pledged-repayment ticks in the invest step aren't persisted after confirm.
- Secondary-market purchases aren't wired to the wallet.
- Notifications/docs counts and a few state chips are static per account state.
- Desktop only (1040px content grid); no mobile layout.
- Escape-to-close is not wired in this version.

## Design tokens

- Ivory page `#F5F3ED`, card `#FBFAF7`, warm fill `#F1EFE8`, hairlines `#DDE3E1`/`#E4E1D8`, muted `#626B70`, faint `#8B939A`/`#C2BFB5`.
- Carbon (text & actions) `#151719` (hover `#000`); risk red `#C4312C`; profit green `#1E6A4B` (hover `#17573E`).
- Type: Instrument Sans (UI; tabular numerals for all figures), Newsreader italic for editorial asides and the "i" glyphs. Kickers: 11px/.16em uppercase. Pills: 999px radius; solid carbon = binds, outline = navigates, tinted chip = state.
