# BANXUM Admin Console — Operations Manual

A visual, beginner-oriented training manual for new operations staff. It teaches
the BANXUM peer-to-peer lending model from zero and walks through every screen of
the internal admin console (`/admin`) with **annotated screenshots** (numbered
badges + arrows pointing at real UI elements), **end-to-end workflows**, and a
**glossary**.

- **Deliverable:** [`BANXUM-Admin-Manual.pdf`](BANXUM-Admin-Manual.pdf) (51 pages)
- **On-screen version:** `manual.html` (same content; annotations are live SVG)

## What's inside the manual

1. Part 1 — The BANXUM model in plain language (the P2P primer)
2. Part 2 — Getting into the console (login, layout, preview vs. live, legend)
3. Sections 3–10 — One per admin screen: Daily Dashboard, Tasks, Users,
   Compliance, Finance Operations, Loans & Marketplace, Reports & Audit,
   Superadmin Settings
4. End-to-end workflows (11 click-by-click recipes)
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
