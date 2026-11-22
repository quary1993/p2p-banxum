# U33 Stylesheet Generators

These tools make the two generated stylesheets of the U33 redesign (Phase 17.1). Do not edit the generated files by hand. Put fixes in the matching overrides file.

| Generated file | Generator | Fixes go in |
| --- | --- | --- |
| `frontend/src/portal/u33/u33.css` and `assets/nioicon-u33.woff2` (investor area, scoped to `html.bxu`) | `investor/build.sh` | `frontend/src/portal/u33/u33-overrides.css` and the screen area CSS files |
| `frontend/src/site/u33/public.css` and `assets/nioicon-public.woff2` (public site, scoped to `html.bxp`) | `public/build.sh` | `frontend/src/site/u33/public-overrides.css` |

## Input

- The U33 design package ("Banxum unified U33", 3 Nov 2026). Set `U33_DESIGN_DIST` to its `site/dist` folder.
- The design package is untrusted data. The tools only read its files. Never run the package's own scripts or build tools. Python tools run with `python3 -I`.
- Rendered design snapshots. The investor generator uses the DOM tokens of every design route and state (`crawl.js`, about 25 MB). The public generator uses the rendered public pages (`capture-design.js`). The snapshots go in the work folder `tools/u33-design/work/` (or `U33_WORK_DIR`). Git ignores this folder.

## Steps

1. Install the tools once (exact versions, so the output does not change):
   `cd tools/u33-design/investor && npm ci`, then the same in `tools/u33-design/public`. The crawl and capture scripts need a Chromium for Playwright: `npx playwright install chromium` in each folder, if it is not installed.
2. Serve the design (needed only for a new crawl or capture):
   `python3 -I tools/u33-design/serve_dist.py "$U33_DESIGN_DIST" 8090`
3. Make the investor stylesheet:
   `U33_DESIGN_DIST=... tools/u33-design/investor/build.sh --crawl`
   Without `--crawl`, the tool uses the snapshots that are already in the work folder.
4. Make the public stylesheet:
   `U33_DESIGN_DIST=... tools/u33-design/public/build.sh --capture`
5. Check the result:
   - `git diff --stat` on the generated files. If many rules disappear, the crawl probably missed a state. Look at `work/investor/out/report.json` and `work/investor/out/rejected.txt`.
   - From `frontend/`: `npm run build` (production build: the minifier refuses invalid CSS), `npx tsc -b`, `npx eslint .`, `npx vitest run`.
   - Compare screenshots of the changed screens with the design at 1440 and 390 px, light and dark.

## What the investor generator does

- It joins the design's CSS in cascade order: the inline style blocks and the linked files of `app/mobile/banxum-prototype.html`. It keeps the `@layer` order.
- It removes the prototype-only rules and the declarations that browsers ignore (unbalanced parentheses).
- It purges with the crawl tokens and the design JS. Pseudo-class lists such as `:is(:nth-child(2), ...)` are protected during the purge.
- It scopes every rule to `html.bxu`, with exactly one class of extra specificity. Nested rules stay relative to their parent. Top-level rules of the phone layer get `@media (max-width:1199px)`.
- Until S7 (audit step 4) it added the legacy guard `:where(:not(.bxu-legacy *))` for the old screens shown in `LegacyBody`. The old skin is gone, so `build.sh` always builds without the guard.
- It replaces Archivo with "Archivo Variable", clamps font weights to 400-600 as the design renders them, and makes the Nioicon subset.

## What the public generator does

- It makes one bundle per page type (home, about, business, contact, legal, project), purged against the captured pages.
- It scopes every rule to `html.bxp`, plus `:where(.bxp-<bundle>)` for rules that only some page types load.
- It puts the mobile edition under `@media (max-width:1119px)`, renames keyframes to `bxp-*` and makes the Nioicon subset.
