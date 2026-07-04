#!/usr/bin/env node
// usage: node e2e.mjs <sessionid> <who> <width>x<height> <investor|admin>
import { execFile } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";

const [sessionid, who, size, mode] = process.argv.slice(2);
const [W, H] = size.split("x").map(Number);
const BASE = "https://staging.nxnarena.com";
const PORT = 9330 + Math.floor(Math.random() * 400);
const OUT = `/tmp/banxum_regression/shots`;
mkdirSync(OUT, { recursive: true });

const NAVS = {
  investor: ["Dashboard", "Marketplace", "Portfolio", "Secondary Market", "Balances", "FX",
    "Documents", "Notifications", "Settings", "Help & FAQ"],
  admin: ["Daily dashboard", "Tasks", "Users", "Compliance", "Finance ops", "Loans",
    "Reports", "QA mode", "Superadmin settings"],
};
const START = mode === "admin" ? "/admin" : "/";

const chrome = execFile("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [
  "--headless=new", `--remote-debugging-port=${PORT}`,
  `--user-data-dir=/tmp/banxum-e2e-${PORT}`, "--no-first-run", `--window-size=${W},${H}`,
]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let wsUrl;
for (let i = 0; i < 30; i++) {
  await sleep(1000);
  try {
    const v = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();
    if (v?.webSocketDebuggerUrl) { wsUrl = v.webSocketDebuggerUrl; break; }
  } catch { /* chrome not ready yet */ }
}
const ws = new WebSocket(wsUrl);
await new Promise((r) => (ws.onopen = r));
let mid = 0;
const pending = new Map();
const consoleErrors = [];
const apiFailures = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) {
    const txt = m.params.args.map((a) => a.value ?? a.description ?? "").join(" ");
    if (m.params.type === "error") consoleErrors.push(txt.slice(0, 300));
  }
  if (m.method === "Runtime.exceptionThrown") {
    consoleErrors.push(("EXC " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text)).slice(0, 300));
  }
  if (m.method === "Network.responseReceived") {
    const r = m.params.response;
    if (r.status >= 400 && r.url.includes("/api/")) apiFailures.push(`${r.status} ${r.url.slice(0, 140)}`);
  }
};
ws.onclose = (e) => console.error("WS CLOSED", e.code, e.reason?.slice?.(0, 200));
ws.onerror = (e) => console.error("WS ERROR", e.message || String(e));
let SESSION = null;
const send = (method, params = {}, ms = 30000) =>
  new Promise((res, rej) => {
    const id = ++mid;
    const t = setTimeout(() => { pending.delete(id); rej(new Error("CDP timeout: " + method)); }, ms);
    pending.set(id, (m) => { clearTimeout(t); if (m.error) console.error("CDP error", method, JSON.stringify(m.error)); res(m); });
    ws.send(JSON.stringify({ id, method, params, ...(SESSION ? { sessionId: SESSION } : {}) }));
  });

const { result: { targetId } } = await send("Target.createTarget", { url: "about:blank" });
const att = await send("Target.attachToTarget", { targetId, flatten: true });
SESSION = att.result.sessionId;
await send("Network.enable");
await send("Runtime.enable");
await send("Page.enable");
await send("Network.setCookie", { name: "sessionid", value: sessionid, url: BASE, secure: true });
await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: W < 700 });
if (mode === "investor") {
  // The SPA restores its view from localStorage; seed the stored route so a
  // session-cookie-only browser boots into the app instead of the landing.
  await send("Page.addScriptToEvaluateOnNewDocument", {
    source: `localStorage.setItem('banxum:app-route:v1', JSON.stringify({name:'dashboard'}))`,
  });
}
await send("Page.navigate", { url: BASE + START });
await sleep(6000);

async function clickNav(label) {
  const clickJs = (l) => `(() => {
    const els = [...document.querySelectorAll('button, a, [role="tab"], .nav-item')];
    const t = els.find(e => e.textContent.trim() === ${JSON.stringify(l)} || e.textContent.trim().startsWith(${JSON.stringify(l)}));
    if (t) { t.scrollIntoView({block:'center'}); t.click(); return 'clicked'; }
    return 'missing';
  })()`;
  let r = await send("Runtime.evaluate", { expression: clickJs(label), returnByValue: true });
  if (r.result?.result?.value === "missing") {
    await send("Runtime.evaluate", { expression: `document.querySelector('.menu-btn, [aria-label="Menu"]')?.click()` });
    await sleep(600);
    r = await send("Runtime.evaluate", { expression: clickJs(label), returnByValue: true });
  }
  return r.result?.result?.value;
}

async function shoot(name) {
  console.error("shoot", name);
  const metrics = await send("Page.getLayoutMetrics");
  const h = Math.min(Math.ceil(metrics.result?.cssContentSize?.height || H), 3200);
  const shot = await send("Page.captureScreenshot", {
    format: "jpeg", quality: 80, captureBeyondViewport: true,
    clip: { x: 0, y: 0, width: W, height: h, scale: 1 },
  }, 60000);
  if (shot.result?.data) writeFileSync(`${OUT}/${name}.jpg`, Buffer.from(shot.result.data, "base64"));
  else console.error("shoot failed", name);
}

const results = [];
await shoot(`${who}-${size}-00-initial`);
for (let i = 0; i < NAVS[mode].length; i++) {
  const label = NAVS[mode][i];
  const status = await clickNav(label);
  await sleep(2600);
  const slug = label.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  await shoot(`${who}-${size}-${String(i + 1).padStart(2, "0")}-${slug}`);
  results.push({ label, status });
}

console.log(JSON.stringify({ who, size, mode, results, consoleErrors: [...new Set(consoleErrors)].slice(0, 20), apiFailures: [...new Set(apiFailures)].slice(0, 30) }, null, 1));
ws.close();
chrome.kill();
process.exit(0);
