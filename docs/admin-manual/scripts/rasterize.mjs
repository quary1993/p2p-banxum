// Flattens every inline annotated SVG in manual.html to a standalone PNG
// (figures/annotated/<figId>.png) via captureScreenshot, which is stable in
// headless Chrome (unlike printing many inline SVGs). Usage: node rasterize.mjs <ws>
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const base = path.resolve(here, "..");
const outDir = path.join(base, "figures", "annotated");
fs.mkdirSync(outDir, { recursive: true });
const htmlPath = path.join(base, "manual.html");

const ws = new WebSocket(process.argv[2]);
let id = 1; const pend = new Map(); const evW = [];
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } if (m.method) for (let i = evW.length - 1; i >= 0; i--) if (evW[i].method === m.method) { evW[i].resolve(m); evW.splice(i, 1); } });
const send = (M, p = {}, s, to = 60000) => new Promise((res, rej) => { const i = id++; const t = setTimeout(() => rej(new Error("timeout " + M)), to); pend.set(i, (v) => { clearTimeout(t); res(v); }); ws.send(JSON.stringify({ id: i, method: M, params: p, ...(s ? { sessionId: s } : {}) })); });
const waitE = (m, ms = 20000) => new Promise((r) => { evW.push({ method: m, resolve: r }); setTimeout(r, ms); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await new Promise((r) => ws.addEventListener("open", r));
const { result: { targetId } } = await send("Target.createTarget", { url: "about:blank" });
const { result: { sessionId: s } } = await send("Target.attachToTarget", { targetId, flatten: true });
await send("Page.enable", {}, s); await send("Runtime.enable", {}, s);
await send("Emulation.setDeviceMetricsOverride", { width: 1100, height: 1400, deviceScaleFactor: 2, mobile: false }, s);
await send("Page.navigate", { url: "file://" + htmlPath }, s);
await waitE("Page.loadEventFired");
for (let i = 0; i < 40; i++) { const r = await send("Runtime.evaluate", { expression: "Array.from(document.images).every(im=>im.complete&&im.naturalWidth>0)", returnByValue: true }, s); if (r.result?.result?.value) break; await sleep(400); }
await sleep(600);
const rects = (await send("Runtime.evaluate", {
  returnByValue: true,
  expression: `Array.from(document.querySelectorAll('svg[data-fig]')).map(el=>{const r=el.getBoundingClientRect();return {id:el.getAttribute('data-fig'), x:r.left+window.scrollX, y:r.top+window.scrollY, w:r.width, h:r.height};})`,
}, s)).result.result.value;
let n = 0;
for (const r of rects) {
  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: r.x, y: r.y, width: r.w, height: r.h, scale: 1.4 } }, s);
  if (shot.result?.data) { fs.writeFileSync(path.join(outDir, r.id + ".png"), Buffer.from(shot.result.data, "base64")); n++; }
}
fs.writeFileSync(path.join(outDir, "index.json"), JSON.stringify(rects.map((r) => ({ id: r.id, w: Math.round(r.w), h: Math.round(r.h) })), null, 2));
console.log("rasterized", n, "figures");
ws.close(); process.exit(0);
