// Assembles the annotated HTML manual from the capture manifest + authored
// content slices. Arrows/badges are positioned from real captured element
// coordinates so they land precisely on the UI. Output: ../manual.html
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const base = path.resolve(here, "..");
const figDir = path.join(base, "figures");
const contentDir = path.join(base, "content");

const manifest = JSON.parse(fs.readFileSync(path.join(figDir, "manifest.json"), "utf8"));
const figIndex = {};
for (const screen of manifest) {
  for (const f of screen.figures) {
    const p = path.join(figDir, f.id + ".png");
    f.png = fs.existsSync(p) ? "figures/" + f.id + ".png" : null; // relative to manual.html
    figIndex[f.id] = f;
  }
}
const load = (name) => {
  const p = path.join(contentDir, name);
  if (!fs.existsSync(p)) return null;
  try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch (e) { console.error("BAD JSON", name, e.message); return null; }
};

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const paras = (arr) => (arr || []).map((p) => `<p>${esc(p)}</p>`).join("");
const bullets = (arr) => (arr && arr.length ? `<ul>${arr.map((b) => `<li>${esc(b)}</li>`).join("")}</ul>` : "");

const MAXW = 980; // max display width for a figure (px)
const MAX_FIG_H = 1230; // keep oversized annotated screenshots on one page

// De-overlap badge y positions along a rail.
function spread(list, H, getY, minGap = 36, pad = 16) {
  const sorted = [...list].sort((a, b) => getY(a) - getY(b));
  let prev = -Infinity;
  for (const a of sorted) { a._by = Math.max(getY(a), prev + minGap); prev = a._by; }
  const overflow = (sorted.length ? sorted[sorted.length - 1]._by : 0) - (H - pad);
  if (overflow > 0) for (const a of sorted) a._by = Math.max(pad, a._by - overflow);
  return sorted;
}

function annotatedFigure(fig, annotations, num) {
  const W = fig.cssWidth, H = fig.cssHeight, RAIL = 66;
  const total = W + RAIL * 2;
  const anns = (annotations || [])
    .map((a, i) => ({ ...a, n: i + 1, it: fig.items[a.item] }))
    .filter((a) => a.it);
  const left = anns.filter((a) => a.it.x + a.it.w / 2 < W / 2);
  const right = anns.filter((a) => a.it.x + a.it.w / 2 >= W / 2);
  spread(left, H, (a) => a.it.y + a.it.h / 2);
  spread(right, H, (a) => a.it.y + a.it.h / 2);
  const svgParts = [];
  const drawn = [...left.map((a) => ({ a, side: "left" })), ...right.map((a) => ({ a, side: "right" }))];
  for (const { a, side } of drawn) {
    const ex = RAIL + a.it.x, ey = a.it.y, ew = a.it.w, eh = a.it.h;
    const bx = side === "left" ? RAIL * 0.5 : total - RAIL * 0.5;
    const by = a._by;
    const tx = side === "left" ? ex - 1 : ex + ew + 1;
    const ty = ey + eh / 2;
    svgParts.push(`<rect class="hl" x="${ex - 3}" y="${ey - 3}" width="${ew + 6}" height="${eh + 6}" rx="6"/>`);
    svgParts.push(`<path class="lead" d="M ${bx} ${by} L ${tx} ${ty}" marker-end="url(#ah${fig.id})"/>`);
    svgParts.push(`<circle class="badge" cx="${bx}" cy="${by}" r="15"/>`);
    svgParts.push(`<text class="bnum" x="${bx}" y="${by + 0.5}">${a.n}</text>`);
  }
  const display = Math.min(total, MAXW, (MAX_FIG_H * total) / H);
  const dispH = (H * display) / total;
  const svg = `<svg class="figsvg" data-fig="${fig.id}" viewBox="0 0 ${total} ${H}" width="${display}" height="${dispH}" xmlns="http://www.w3.org/2000/svg">
    <defs><marker id="ah${fig.id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#9c3127"/></marker></defs>
    <image href="${fig.png}" x="${RAIL}" y="0" width="${W}" height="${H}"/>
    ${svgParts.join("\n")}
  </svg>`;
  const legend = anns.length
    ? `<ol class="legend">${anns.map((a) => `<li><span class="lnum">${a.n}</span><div><strong>${esc(a.label)}</strong> ${esc(a.text)}</div></li>`).join("")}</ol>`
    : "";
  return { svg, legend, num };
}

function kpiFigure(fig, tiles) {
  const W = fig.cssWidth, H = fig.cssHeight, TOP = 56;
  const total = H + TOP, n = tiles.length || 1;
  const parts = [];
  tiles.forEach((t, i) => {
    const cx = (W * (i + 0.5)) / n, colX = (W * i) / n;
    parts.push(`<rect class="hl" x="${colX + 4}" y="${TOP + 4}" width="${W / n - 8}" height="${H - 8}" rx="6"/>`);
    parts.push(`<path class="lead" d="M ${cx} ${TOP * 0.5} L ${cx} ${TOP - 2}" marker-end="url(#ahk${fig.id})"/>`);
    parts.push(`<circle class="badge" cx="${cx}" cy="${TOP * 0.5}" r="15"/>`);
    parts.push(`<text class="bnum" x="${cx}" y="${TOP * 0.5 + 0.5}">${i + 1}</text>`);
  });
  const display = Math.min(W, MAXW);
  const dispH = (total * display) / W;
  const svg = `<svg class="figsvg" data-fig="${fig.id}" viewBox="0 0 ${W} ${total}" width="${display}" height="${dispH}" xmlns="http://www.w3.org/2000/svg">
    <defs><marker id="ahk${fig.id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#9c3127"/></marker></defs>
    <image href="${fig.png}" x="0" y="${TOP}" width="${W}" height="${H}"/>
    ${parts.join("\n")}
  </svg>`;
  const legend = `<ol class="legend">${tiles.map((t, i) => `<li><span class="lnum">${i + 1}</span><div><strong>${esc(t.label)}</strong> ${esc(t.text)}</div></li>`).join("")}</ol>`;
  return { svg, legend };
}

function figureBlock(f, secNum, figNum) {
  const fig = figIndex[f.id];
  if (!fig || !fig.png) return `<div class="missing">Figure ${esc(f.id)} unavailable.</div>`;
  const label = `Figure ${secNum}.${figNum}`;
  let body;
  if (f.kpiTiles && f.kpiTiles.length) body = kpiFigure(fig, f.kpiTiles);
  else body = annotatedFigure(fig, f.annotations, figNum);
  return `<figure class="fig">
    <div class="figtop">
      <figcaption><span class="figlabel">${label}</span> ${esc(f.caption || fig.title)}</figcaption>
      ${f.summary ? `<p class="figsummary">${esc(f.summary)}</p>` : ""}
      <div class="figcanvas">${body.svg}</div>
    </div>
    ${body.legend}
    ${f.notes && f.notes.length ? `<div class="notes"><div class="notes-h">Notes &amp; rules</div>${bullets(f.notes)}</div>` : ""}
  </figure>`;
}

function screenSection(content, secNum) {
  if (!content) return "";
  let figNum = 0;
  const figs = (content.figures || []).map((f) => figureBlock(f, secNum, ++figNum)).join("");
  return `<section class="screen" id="screen-${esc(content.key)}">
    <div class="sec-head"><span class="eyebrow">Section ${secNum}</span><h2>${esc(content.title)}</h2></div>
    <div class="lead-copy">${paras(content.intro)}</div>
    ${content.whatYouDoHere && content.whatYouDoHere.length ? `<div class="callout"><div class="callout-h">What you do on this screen</div>${bullets(content.whatYouDoHere)}</div>` : ""}
    ${figs}
  </section>`;
}

function primerSection(primer) {
  if (!primer) return "";
  const secs = (primer.sections || []).map((s) => `
    <div class="primer-block">
      <h3>${esc(s.heading)}</h3>
      ${paras(s.body)}
      ${bullets(s.bullets)}
    </div>`).join("");
  return `<section class="screen" id="primer">
    <div class="sec-head"><span class="eyebrow">Part 1</span><h2>${esc(primer.title || "The BANXUM model in plain language")}</h2></div>
    ${secs}
  </section>`;
}

function flowsSection(flows, secNum) {
  if (!flows || !flows.flows) return "";
  const items = flows.flows.map((fl, i) => `
    <div class="flow">
      <div class="flow-head"><span class="flow-n">${i + 1}</span><h3>${esc(fl.title)}</h3></div>
      <p class="flow-goal"><strong>Goal:</strong> ${esc(fl.goal)}${fl.actor ? ` &nbsp;·&nbsp; <strong>Who:</strong> ${esc(fl.actor)}` : ""}</p>
      ${fl.preconditions && fl.preconditions.length ? `<div class="flow-pre"><strong>Before you start:</strong>${bullets(fl.preconditions)}</div>` : ""}
      <ol class="flow-steps">${(fl.steps || []).map((st) => `<li><span class="step-screen">${esc(st.screen)}</span><div><span class="step-action">${esc(st.action)}</span>${st.detail ? `<div class="step-detail">${esc(st.detail)}</div>` : ""}</div></li>`).join("")}</ol>
      ${fl.outcome ? `<p class="flow-out"><strong>Result:</strong> ${esc(fl.outcome)}</p>` : ""}
      ${fl.pitfalls && fl.pitfalls.length ? `<div class="flow-pit"><strong>Watch out for</strong>${bullets(fl.pitfalls)}</div>` : ""}
    </div>`).join("");
  return `<section class="screen" id="flows">
    <div class="sec-head"><span class="eyebrow">Section ${secNum}</span><h2>End-to-end workflows</h2></div>
    <p class="lead-copy">Step-by-step recipes that connect the screens for the jobs you will actually do. Each step names the screen and the control to use.</p>
    ${items}
  </section>`;
}

function glossarySection(gloss, secNum) {
  if (!gloss) return "";
  const dl = (arr, kf, vf) => `<dl class="gloss">${(arr || []).map((x) => `<dt>${esc(x[kf])}</dt><dd>${esc(x[vf])}</dd>`).join("")}</dl>`;
  return `<section class="screen" id="glossary">
    <div class="sec-head"><span class="eyebrow">Section ${secNum}</span><h2>Glossary &amp; quick reference</h2></div>
    <h3>Key terms</h3>${dl(gloss.terms, "term", "definition")}
    <h3>Statuses you will see</h3>${dl(gloss.statuses, "name", "meaning")}
    <h3>Dashboard queues</h3>${dl(gloss.queues, "name", "meaning")}
  </section>`;
}

// ---- assemble ----
const primer = load("primer.json");
const glossary = load("glossary.json");
const flows = load("flows.json");
const screenOrder = ["dashboard", "tasks", "compliance", "finance", "loans", "reports", "settings"];
const screens = screenOrder.map((k) => load(`screen-${k}.json`)).filter(Boolean);

const today = process.env.MANUAL_DATE || "";

let secNum = 0;
const partNav = primerSection(primer);
const gettingStarted = `<section class="screen" id="getting-started">
  <div class="sec-head"><span class="eyebrow">Part 2</span><h2>Getting into the console</h2></div>
  <div class="lead-copy">
    <p>The admin console lives at the <code>/admin</code> address of the BANXUM web app. It is completely separate from the investor app that lenders use. Only staff accounts of type <em>admin</em> or <em>superadmin</em>, with an active status, can sign in.</p>
    <p><strong>Signing in is two steps.</strong> First you enter your work email and password. Then BANXUM emails you a one-time numeric code, which you type on the next screen. This second step (an emailed code) is a security measure — even if someone learns your password they cannot get in without your mailbox. If you mistype the code too many times you must start again.</p>
    <p><strong>The layout.</strong> A dark navigation rail runs down the left with the seven areas of the console (described in the sections that follow). The main area on the right shows the selected area. A top bar shows where you are and who the operator is.</p>
    <p><strong>Preview vs. live data.</strong> When the console shows a small "Preview data" tag near the top right, you are looking at fixture (demo) data — safe for training and screenshots, not real customers. A live deployment has no such tag and every action affects real money and real people. <em>The screenshots in this manual were taken in preview mode, so the names and numbers are invented.</em></p>
    <p><strong>Signing out.</strong> Use the "Sign out" button at the bottom of the left rail when you finish. Never leave an authenticated admin session unattended.</p>
  </div>
  <div class="callout"><div class="callout-h">How to read the figures in this manual</div>
    <ul>
      <li>Each screenshot has small numbered green circles in the margins. A red arrow runs from each circle to the exact button, field, or column it describes, which is outlined in red.</li>
      <li>Below every screenshot, a numbered list explains each marked element in plain language — the number matches the circle.</li>
      <li>"Notes &amp; rules" boxes call out the safety rules the system enforces and the mistakes to avoid.</li>
    </ul>
  </div>
</section>`;

const body = [
  partNav,
  gettingStarted,
  ...(() => {
    secNum = 2; // Parts 1 & 2 above; sections start numbering at 3
    const out = [];
    for (const s of screens) { secNum++; out.push(screenSection(s, secNum)); }
    secNum++; out.push(flowsSection(flows, secNum));
    secNum++; out.push(glossarySection(glossary, secNum));
    return out;
  })(),
].join("\n");

const outline = [
  "Part 1 — The BANXUM model in plain language",
  "Part 2 — Getting into the console",
  ...screens.map((s, i) => `Section ${i + 3} — ${s.title}`),
  `Section ${screens.length + 3} — End-to-end workflows`,
  `Section ${screens.length + 4} — Glossary & quick reference`,
];

const html = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<title>BANXUM Admin Console — Operations Manual</title>
<style>
@page { size: 275mm 389mm; margin: 0; }
* { box-sizing: border-box; }
html,body { margin:0; padding:0; }
body { font-family: 'Public Sans','Segoe UI',Helvetica,Arial,sans-serif; color:#1b211d; background:#fffefb; font-size:14.4px; line-height:1.52; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
code,.mono { font-family:'IBM Plex Mono',ui-monospace,Menlo,Consolas,monospace; font-size:0.86em; background:#f3f1e9; padding:1px 5px; border-radius:4px; }
.wrap { padding:54px 60px; }
.page-break { break-before: page; }
h2 { font-size:28px; line-height:1.12; margin:0; letter-spacing:-0.35px; }
h3 { font-size:18px; margin:20px 0 5px; color:#1b211d; }
p { margin:0 0 9px; }
ul,ol { margin:0 0 9px; padding-left:20px; }
li { margin:3px 0; }
.eyebrow { color:#2f6b4f; font-size:12px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; }
.sec-head { border-bottom:3px solid #2f6b4f; padding-bottom:11px; margin-bottom:16px; }
.sec-head h2 { margin-top:4px; }
.screen { break-before: page; padding-top:0; }
.lead-copy p { font-size:14.8px; color:#363d37; }
.callout { background:#f0f4ef; border:1px solid #c9dccd; border-left:4px solid #2f6b4f; border-radius:8px; padding:11px 14px; margin:13px 0; break-inside:avoid; }
.callout-h, .notes-h { font-weight:700; color:#235; color:#2f6b4f; margin-bottom:6px; font-size:13px; letter-spacing:0.04em; text-transform:uppercase; }
.callout ul { margin-bottom:0; }
.primer-block { margin-bottom:13px; break-inside:avoid; }
.primer-block h3 { border-left:3px solid #d9b44a; padding-left:10px; }

/* Figures */
.fig { margin:18px 0 22px; break-inside:auto; }
.figtop { break-inside:avoid; break-after:auto; }
figcaption { font-size:15.4px; font-weight:600; margin-bottom:3px; break-after:avoid; }
.figlabel { display:inline-block; background:#2f6b4f; color:#fff; font-size:11px; font-weight:700; letter-spacing:0.06em; padding:2px 8px; border-radius:5px; margin-right:8px; vertical-align:middle; }
.figsummary { color:#5b635c; font-size:13.3px; margin:2px 0 8px; break-after:avoid; }
.figcanvas { background:#f6f5ef; border:1px solid #e3e0d4; border-radius:10px; padding:11px; text-align:center; break-inside:avoid; }
.figsvg { max-width:100%; height:auto; }
.figsvg .hl { fill:none; stroke:#9c3127; stroke-width:2; opacity:0.9; }
.figsvg .lead { stroke:#9c3127; stroke-width:2; fill:none; }
.figsvg .badge { fill:#2f6b4f; stroke:#fff; stroke-width:2; }
.figsvg .bnum { fill:#fff; font-size:17px; font-weight:700; text-anchor:middle; dominant-baseline:central; font-family:'Public Sans',sans-serif; }
.legend { list-style:none; padding:0; margin:10px 0 0; column-count:2; column-gap:22px; }
.legend li { display:flex; gap:8px; break-inside:avoid; margin:4px 0; align-items:flex-start; font-size:12.8px; line-height:1.42; }
.legend .lnum { flex:0 0 auto; width:19px; height:19px; border-radius:50%; background:#2f6b4f; color:#fff; font-size:11px; font-weight:700; display:flex; align-items:center; justify-content:center; margin-top:1px; }
.notes { background:#fbf7ec; border:1px solid #e7d9b0; border-radius:8px; padding:9px 12px; margin-top:10px; font-size:13px; }
.notes ul { margin-bottom:0; }

/* Flows */
.flow { break-inside:auto; border:1px solid #e3e0d4; border-radius:10px; padding:12px 14px; margin:11px 0; background:#fffdf8; }
.flow-head { display:flex; align-items:center; gap:10px; break-after:avoid; }
.flow-n { flex:0 0 auto; width:26px; height:26px; border-radius:7px; background:#2f6b4f; color:#fff; font-weight:700; display:flex; align-items:center; justify-content:center; }
.flow-head h3 { margin:0; font-size:16.6px; }
.flow-goal { font-size:13.4px; color:#363d37; margin:7px 0; }
.flow-pre, .flow-pit { font-size:12.8px; margin:6px 0; }
.flow-steps { list-style:none; counter-reset:s; padding:0; margin:8px 0; }
.flow-steps li { counter-increment:s; display:flex; gap:10px; margin:5px 0; align-items:flex-start; break-inside:avoid; }
.flow-steps li::before { content:counter(s); flex:0 0 auto; width:20px; height:20px; border-radius:50%; background:#e6efe7; color:#2f6b4f; font-size:11px; font-weight:700; display:flex; align-items:center; justify-content:center; margin-top:1px; }
.step-screen { display:inline-block; background:#eef0e9; color:#3a4a3d; font-size:10.5px; font-weight:700; padding:1px 7px; border-radius:5px; margin-right:7px; white-space:nowrap; }
.step-action { font-weight:600; }
.step-detail { color:#5b635c; font-size:12.8px; margin-top:1px; }
.flow-out { background:#f0f4ef; border-radius:7px; padding:7px 10px; font-size:13px; }
.flow-pit ul { margin-bottom:0; }

/* Glossary */
.gloss { display:grid; grid-template-columns:190px 1fr; gap:3px 16px; margin:6px 0 14px; font-size:13.5px; }
.gloss dt { font-weight:700; color:#2f6b4f; }
.gloss dd { margin:0; }
.missing { color:#9c3127; font-style:italic; }

/* Cover */
.cover { min-height:386mm; background:linear-gradient(160deg,#1b3a2b 0%,#2f6b4f 60%,#3c855f 100%); color:#fff; padding:96px 84px; display:flex; flex-direction:column; }
.cover .mark { width:64px; height:64px; border-radius:14px; background:#fff; color:#2f6b4f; font-size:38px; font-weight:700; display:flex; align-items:center; justify-content:center; }
.cover h1 { font-size:64px; line-height:1.04; margin:120px 0 0; letter-spacing:-1.5px; font-weight:700; }
.cover .sub { font-size:24px; opacity:0.92; margin-top:18px; font-weight:500; }
.cover .meta { margin-top:auto; font-size:14px; opacity:0.85; line-height:1.7; }
.cover .brandline { display:flex; align-items:center; gap:16px; }
.cover .brandline div b { font-size:22px; letter-spacing:2px; }
.cover .conf { display:inline-block; margin-top:14px; border:1px solid rgba(255,255,255,0.5); border-radius:999px; padding:4px 14px; font-size:12px; letter-spacing:0.08em; text-transform:uppercase; }
.toc { break-before:page; padding:58px 64px; }
.toc h2 { border-bottom:3px solid #2f6b4f; padding-bottom:12px; margin-bottom:18px; }
.toc-grid { display:grid; grid-template-columns:1.15fr .85fr; gap:22px; align-items:start; }
.toc ol { font-size:15.5px; line-height:1.72; margin:0; padding-left:24px; }
.toc-card { background:#f0f4ef; border:1px solid #c9dccd; border-left:4px solid #2f6b4f; border-radius:10px; padding:16px 18px; font-size:14px; color:#363d37; }
.toc-card h3 { margin:0 0 8px; font-size:17px; }
.toc-card ul { margin-bottom:0; }
</style></head>
<body>
  <div class="cover">
    <div class="brandline"><span class="mark">B</span><div><b>BANXUM</b><div style="opacity:.85;font-size:13px">by Garanta Finanzgruppe AG</div></div></div>
    <h1>Admin Console<br/>Operations Manual</h1>
    <div class="sub">A visual, step-by-step guide for new operations staff</div>
    <div class="meta">
      <span class="conf">Internal &amp; confidential</span><br/><br/>
      This manual teaches the BANXUM peer-to-peer lending model from zero and walks through every screen of the internal admin console, with annotated screenshots and end-to-end workflows.<br/>
      ${today ? "Version dated " + esc(today) + ". " : ""}Screenshots captured in preview mode; all names and figures shown are demo data.
    </div>
  </div>
  <div class="toc">
    <h2>Contents</h2>
    <div class="toc-grid">
      <ol>${outline.map((o) => `<li>${esc(o)}</li>`).join("")}</ol>
      <div class="toc-card">
        <h3>How to use this manual</h3>
        <ul>
          <li>Start with Part 1 if you are new to BANXUM or P2P lending.</li>
          <li>Use Sections 3-9 as screen-by-screen training references.</li>
          <li>Use Section 10 when you need a click-by-click workflow.</li>
          <li>Use the glossary when a status, queue, or finance term is unfamiliar.</li>
        </ul>
      </div>
    </div>
  </div>
  <div class="wrap">
    ${body}
  </div>
</body></html>`;

fs.writeFileSync(path.join(base, "manual.html"), html.replace(/[ \t]+$/gm, ""));
console.log("wrote manual.html", (html.length / 1024 / 1024).toFixed(1) + "MB", "| screens:", screens.length, "| flows:", flows?.flows?.length ?? 0);
