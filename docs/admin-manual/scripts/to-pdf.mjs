// Renders manual.html -> BANXUM-Admin-Manual.pdf via headless Chrome (CDP).
// Images are referenced by relative path (streamed by Chrome), not inlined.
// Usage: node to-pdf.mjs <browserWsUrl> [outName]
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const base = path.resolve(here, "..");
const htmlPath = path.join(base, process.argv[4] || "manual-print.html");
const outPath = path.join(base, process.argv[3] || "BANXUM-Admin-Manual.pdf");
const browserWs = process.argv[2];

const ws = new WebSocket(browserWs);
let nextId = 1; const pending = new Map(); const evW = [];
ws.addEventListener("message", (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method) for (let i = evW.length - 1; i >= 0; i--) if (evW[i].method === m.method) { evW[i].resolve(m); evW.splice(i, 1); }
});
ws.addEventListener("close", () => { for (const r of pending.values()) r({ error: { message: "ws closed" } }); });
const send = (method, params = {}, sid, timeout = 120000) => new Promise((resolve, reject) => {
  const id = nextId++; pending.set(id, resolve);
  const t = setTimeout(() => { pending.delete(id); reject(new Error("CDP timeout: " + method)); }, timeout);
  const wrap = (v) => { clearTimeout(t); resolve(v); };
  pending.set(id, wrap);
  ws.send(JSON.stringify({ id, method, params, ...(sid ? { sessionId: sid } : {}) }));
});
const waitEvent = (m, ms = 30000) => new Promise((res) => { evW.push({ method: m, resolve: res }); setTimeout(res, ms); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await new Promise((r) => ws.addEventListener("open", r));
const { result: { targetId } } = await send("Target.createTarget", { url: "about:blank" });
const { result: { sessionId: sid } } = await send("Target.attachToTarget", { targetId, flatten: true });
await send("Page.enable", {}, sid);
await send("Runtime.enable", {}, sid);
await send("Emulation.setDeviceMetricsOverride", { width: 1040, height: 1472, deviceScaleFactor: 1, mobile: false }, sid);
await send("Page.navigate", { url: "file://" + htmlPath }, sid);
await waitEvent("Page.loadEventFired");
// wait until every <img> has finished decoding
for (let i = 0; i < 40; i++) {
  const r = await send("Runtime.evaluate", { expression: "Array.from(document.images).every(im=>im.complete && im.naturalWidth>0)", returnByValue: true }, sid);
  if (r.result?.result?.value) break;
  await sleep(500);
}
await sleep(800);
const r = await send("Page.printToPDF", {
  printBackground: true,
  preferCSSPageSize: true,
  marginTop: 0, marginBottom: 0, marginLeft: 0, marginRight: 0,
}, sid, 180000);
if (!r.result?.data) { console.error("printToPDF failed:", JSON.stringify(r.error || r)); process.exit(1); }
fs.writeFileSync(outPath, Buffer.from(r.result.data, "base64"));
console.log("wrote", outPath, (fs.statSync(outPath).size / 1024 / 1024).toFixed(2) + "MB");
ws.close();
process.exit(0);
