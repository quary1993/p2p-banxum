// Capture harness: drives the BANXUM admin console (preview mode) through every
// screen, saves a per-card screenshot at 2x, and records the exact CSS-pixel
// rect + text of every annotatable element so the manual can draw arrows that
// land precisely on real UI. Output: figures/<id>.png + figures/manifest.json
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(here, "../figures");
fs.mkdirSync(outDir, { recursive: true });

const APP = "http://localhost:5173/admin";
const VIEWPORT_W = 1340;
const VIEWPORT_H = 1200;
const SCALE = 2;

const browserWs = process.argv[2];
const ws = new WebSocket(browserWs);
let nextId = 1;
const pending = new Map();
const evWaiters = [];
ws.addEventListener("message", (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method) for (let i = evWaiters.length - 1; i >= 0; i--) {
    if (evWaiters[i].method === m.method) { evWaiters[i].resolve(m); evWaiters.splice(i, 1); }
  }
});
const send = (method, params = {}, sid) => new Promise((res) => {
  const id = nextId++; pending.set(id, res);
  ws.send(JSON.stringify({ id, method, params, ...(sid ? { sessionId: sid } : {}) }));
});
const waitEvent = (m, ms = 10000) => new Promise((res, rej) => {
  evWaiters.push({ method: m, resolve: res });
  setTimeout(() => rej(new Error("timeout " + m)), ms);
});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await new Promise((r) => ws.addEventListener("open", r));
const { result: { targetId } } = await send("Target.createTarget", { url: "about:blank" });
const { result: { sessionId: sid } } = await send("Target.attachToTarget", { targetId, flatten: true });
await send("Page.enable", {}, sid);
await send("Runtime.enable", {}, sid);
await send("Emulation.setDeviceMetricsOverride", { width: VIEWPORT_W, height: VIEWPORT_H, deviceScaleFactor: 1, mobile: false }, sid);
await send("Page.navigate", { url: APP }, sid);
await waitEvent("Page.loadEventFired").catch(() => {});
await sleep(1500);

const evaluate = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, sid);
  if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};

// Extractor that runs in-page: returns the list of "figure" containers for the
// current screen and, for each, the annotatable child elements with rects
// relative to the figure's top-left (CSS px).
const EXTRACT = `(() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 4 && r.height > 4 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const txt = (el) => (el.getAttribute('aria-label') || el.textContent || el.placeholder || '').replace(/\\s+/g,' ').trim().slice(0,90);
  const content = document.querySelector('.admin-content') || document.querySelector('.admin-main') || document.body;
  const allCards = [...content.querySelectorAll('.card')].filter(c => !c.parentElement.closest('.card'));
  const figures = [];
  const pushFig = (el, kind, title) => {
    if (!el || !vis(el)) return;
    const r = el.getBoundingClientRect();
    const base = { x: r.left, y: r.top };
    const items = [];
    const seen = new Set();
    const add = (node, role) => {
      if (!node || seen.has(node) || !vis(node)) return;
      seen.add(node);
      const nr = node.getBoundingClientRect();
      const t = txt(node);
      if (!t && role !== 'input') return;
      items.push({ role, text: t, x: Math.round(nr.left - base.x), y: Math.round(nr.top - base.y), w: Math.round(nr.width), h: Math.round(nr.height) });
    };
    el.querySelectorAll('.eyebrow').forEach(n => add(n, 'eyebrow'));
    el.querySelectorAll('h1,h2,h3').forEach(n => add(n, 'heading'));
    el.querySelectorAll('thead th').forEach(n => add(n, 'column'));
    el.querySelectorAll('.field > label, label.field-label, .field-label').forEach(n => add(n, 'field'));
    el.querySelectorAll('select').forEach(n => add(n, 'input'));
    el.querySelectorAll('button').forEach(n => add(n, 'button'));
    el.querySelectorAll('.chip, .pill, .tag, .badge').forEach(n => add(n, 'status'));
    el.querySelectorAll('.banner .banner-title, .banner h4, .banner strong').forEach(n => add(n, 'banner'));
    figures.push({ kind, title: title || '', x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), items });
  };
  const kpi = content.querySelector('.admin-kpi-grid');
  if (kpi) pushFig(kpi, 'kpi', 'Key metrics');
  const queue = content.querySelector('.admin-queue-layout');
  if (queue) pushFig(queue, 'queue', 'Daily dashboard queues');
  allCards.forEach((c) => { const h = c.querySelector('h1,h2,h3'); pushFig(c, 'card', h ? h.textContent.trim() : ''); });
  return figures;
})()`;

const clickNavByLabel = async (label) => {
  await evaluate(`(() => { const b = [...document.querySelectorAll('.admin-nav button, button')].find(x => x.textContent.trim() === ${JSON.stringify(label)}); if (b) b.click(); return !!b; })()`);
};
const clickButtonByText = async (text) => evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === ${JSON.stringify(text)}); if (b) { b.click(); return true; } return false; })()`);

const manifest = [];
const captureScreen = async (navLabel, key, opts = {}) => {
  await evaluate(`window.scrollTo(0,0)`);
  if (navLabel) await clickNavByLabel(navLabel);
  await sleep(opts.wait ?? 1400);
  if (opts.pre) { await evaluate(opts.pre); await sleep(900); }
  const figures = await evaluate(EXTRACT);
  const screenFigures = [];
  for (let i = 0; i < figures.length; i++) {
    const f = figures[i];
    if (f.w < 40 || f.h < 24) continue;
    const id = `${key}-${i}-${(f.title || f.kind).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40)}`;
    const shot = await send("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
      clip: { x: f.x, y: f.y, width: f.w, height: f.h, scale: SCALE }
    }, sid);
    if (!shot.result?.data) continue;
    fs.writeFileSync(path.join(outDir, id + ".png"), Buffer.from(shot.result.data, "base64"));
    screenFigures.push({ id, kind: f.kind, title: f.title, cssWidth: f.w, cssHeight: f.h, scale: SCALE, items: f.items });
  }
  manifest.push({ key, nav: navLabel, label: opts.label || navLabel, figures: screenFigures });
  console.log(`captured ${key}: ${screenFigures.length} figures`);
};

await captureScreen(null, "dashboard", { label: "Daily dashboard", wait: 1800 });
await captureScreen("Tasks", "tasks", {});
await captureScreen("Compliance", "compliance", {});
await captureScreen("Finance ops", "finance", {});
await captureScreen("Loans", "loans", {});
await captureScreen("Reports", "reports", {});
await captureScreen("Superadmin settings", "settings", {});

fs.writeFileSync(path.join(outDir, "manifest.json"), JSON.stringify(manifest, null, 2));
console.log("manifest written:", manifest.reduce((n, s) => n + s.figures.length, 0), "figures total");
ws.close();
process.exit(0);
