# BANXUM Admin Console — Operations Manual

A visual, beginner-oriented training manual for new operations staff. It teaches
the BANXUM peer-to-peer lending model from zero and walks through every screen of
the internal admin console (`/admin`) with **annotated screenshots** (numbered
badges + arrows pointing at real UI elements), **end-to-end workflows**, and a
**glossary**.

- **Deliverable:** [`BANXUM-Admin-Manual.pdf`](BANXUM-Admin-Manual.pdf) (60 pages)
- **On-screen version:** `manual.html` (same content; annotations are live SVG)

## Status (2026-11-20)

The content files in `content/` were updated for Phase 18.4 and the audit of 20 November 2026: the 56-day return
rule, no penalty and no penalty mode, failed returns, settlement calendars, and the verification of a return
account from a deposit (a deposit does not verify its source IBAN). They were also updated for Phase 18.5: admins
sign in with email, password and an authenticator app (no email code), the password rules for a new admin, the
authenticator reset by a superadmin, and investor sign-in with a password and a second factor (no magic links).
Audit step 5 added the flow "Service a direct loan on the 18.6 interest engine" (payments, expenses, Default
declaration and cancellation); the earlier repayment flow is marked as the flow for loans before the engine.
Audit step 6 replaced the boundary-installment description of Loan Originator offers with the 18.7 price
(principal plus accrued interest, F04 failure, underlying financing ID).
Audit step 7 added the 18.10 compliance tools (declaration reviews, the investor compliance file, staff roles) and
three flows: handle a declaration review, open a manual review or re-verification date, and verify the securities of
a loan. These have no figures yet.
`manual.html` was rendered again from this content (`node scripts/render.mjs`). `manual-print.html` and the PDF
were built before these changes and still show the old sign-in: rebuild them with `bash scripts/build.sh` on a
Mac with Google Chrome (a build on Linux uses other fonts and changes the layout). The figures are older captures: Finance Operations has
new cards (failed returns, returned transfer, verification from a deposit, settlement calendars) without figures
yet, so a new capture is needed for them.

## What's inside the manual

1. Part 1 — The BANXUM model in plain language (the P2P primer)
2. Part 2 — Getting into the console (login, layout, preview vs. live, legend)
3. Sections 3–10 — One per admin screen: Daily Dashboard, Tasks, Users,
   Compliance, Finance Operations, Loans & Marketplace, Reports & Audit,
   Superadmin Settings
4. End-to-end workflows (13 click-by-click recipes)
5. Glossary & quick reference (terms, statuses, dashboard queues)

## How it was built

The content is **grounded in the real codebase** (it was authored by reading the
actual backend services/models and frontend panels) and the screenshots are
**real captures of the running admin console in preview mode**, so arrows land on
the exact pixels of each element.

```
figures/                 captured screenshots + manifest.json (element coordinates)
figures/annotated/       flattened annotated figures (screenshot + arrows baked in)
content/                 authored content slices (JSON): primer, glossary,
                         screen-<key>, flows, plus accuracy verification notes
scripts/                 the build pipeline (see below)
manual.html              annotated HTML (live SVG overlays) — view in a browser
manual-print.html        print-safe HTML (SVGs replaced by flat PNGs) [regenerated]
BANXUM-Admin-Manual.pdf  the final manual
```

### Pipeline (`scripts/`)

| step | script | what it does |
|------|--------|--------------|
| capture | `capture.mjs` | drives the running admin console via Chrome DevTools, saves a screenshot per card **and** the exact CSS-pixel rect + text of every element (`figures/manifest.json`) |
| author | `author.workflow.js`, `author-fill.workflow.js` | multi-agent authoring of the content slices, grounded in the code, with an adversarial accuracy-verification pass |
| render | `render.mjs` | assembles `manual.html`: each figure gets an SVG overlay drawing a highlight box + numbered badge + arrow for every annotated element (positions come from the manifest) |
| rasterize | `rasterize.mjs` | screenshots each annotated figure to a flat PNG (`figures/annotated/`) — headless Chrome crashes when *printing* many inline SVGs |
| print-safe | `build-print.mjs` | rebuilds the HTML with `<img>` flats instead of SVG |
| split | `split-print.mjs` | splits into image-bounded chunks (Chrome also crashes printing too many images at once) |
| to-pdf | `to-pdf.mjs` | prints one chunk to PDF (Chrome `printToPDF`, custom page size) |
| merge | `merge.py` | concatenates the chunk PDFs and drops blank pages |

### Rebuild

Requires Google Chrome and [`uv`](https://docs.astral.sh/uv/). From this folder:

```bash
bash scripts/build.sh
```

This rebuilds `BANXUM-Admin-Manual.pdf` from the existing `figures/` and
`content/` (no running app needed). To re-capture screenshots or re-author
content, run `capture.mjs` against a running preview build
(`VITE_PREVIEW=true npm run dev` in `frontend/`) and the authoring workflows
first.

## Notes

- Screenshots are from **preview mode**, so every name, amount, IBAN and ID shown
  is invented demo data — safe to share for training.
- The content was fact-checked against the code; the verifier's findings were
  applied (see `content/verify-*.json` for the audit trail).
