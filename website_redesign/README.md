# Banxum — static site export (from Platform v6.3)

Same folder shape as the original static export: one HTML file per page, one shared `styles.css`, one shared `app.js`. No build step, no framework — open `index.html` (public) or `dashboard.html` (logged-in) in a browser.

## Page map (old name → content)
- `index.html` — public landing: open-loan preview + register CTA
- `login.html`, `register.html`, `verification.html` — auth flow (recreated in the new design; no old-design equivalent existed in v6.3, so these follow the new language)
- `dashboard.html` — balance story, rule desk (8 matched opportunities), closing-soon list, expected income by month, invested-vs-earned comparison
- `marketplace.html` — Investment opportunities (32 loans, Focused/Detailed views, commit-capacity band)
- `loan.html` — loan detail (Aurelia Panificație): 3 outcomes, collateral, schedule, exit
- `public-loan.html` — public preview of one open loan (Solaria)
- `portfolio.html` — My investments: 16 loans, earnings calendar (rendered from data by `app.js`), spread hexagon, collateral ring/bar, protection
- `balances.html` — My money: three-state statement (Today / Expected / With reinvestment), transaction history, past months, fees
- `secondary-market.html` — 5 listings, discount/par/premium explainer, selling rules
- `fx.html` — converter, balances, rates, past conversions
- `add-money.html`, `withdraw.html` — money in/out (new pages; they exist as screens in the v6.3 design and the header links to them)
- `how-loans-work.html` — originators / purchased-loans page (new; several pages link to it)
- `documents.html`, `notifications.html`, `settings.html`, `help.html`, `faq.html` — as named

## Notes for the developer
- Design tokens live at the top of `styles.css` (`:root`). Type: Instrument Sans (UI) + Newsreader italic (asides). Red = risk/lateness only; green = profit only.
- `app.js` holds: account menu, generic expand/collapse (`data-toggle`), segmented controls (`data-seg`), FAQ accordion, show-all rows (`data-more`), and the earnings-calendar renderer — the calendar computes all 12 months from the loan schedule data at the top of the file, exactly as the platform prototype does.
- Everything else is a static snapshot of the live prototype's computed state (demo persona Andrea Keller, funded account, 29 July 2026). Figures reconcile: August income € 13,489.60 across 14 payments; 12-month contracted income € 160,021.40; balance € 488,000.00 = € 388,000.00 lent + € 100,000.00 idle.
- Not carried over from the prototype (interactive-only): the invest/commit sheet, auto-invest rule editor, filter panel with live counts, sorting, export dialog, and info modals. The live prototype (`Banxum Platform v6.3` standalone HTML in the design handoff) remains the reference for those flows.
