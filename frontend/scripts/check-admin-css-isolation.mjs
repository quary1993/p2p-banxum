// IP of Webby-Soft SRL.
// Audit S4-9: a real-browser check that the admin stylesheet styles nothing outside the admin console.
//
// Use (after "npm run build"; needs Chrome):
//   node scripts/check-admin-css-isolation.mjs
//   CHROME=/path/to/chrome node scripts/check-admin-css-isolation.mjs
//
// The script opens one page two times in headless Chrome, with the built stylesheets of the investor
// area and the public site: one time with the built admin stylesheet and one time without it. This is
// the state of a tab after a visit to the admin console (a browser keeps the stylesheet of a lazy area).
// For the investor area (html.bxu) and the public site (html.bxs) the computed styles of the sample
// elements must be the same in the two pages. For the admin console (html.bxa) the admin rules must apply.
/* global Buffer, console, process */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const assets = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "dist", "assets");
const chrome = process.env.CHROME || "google-chrome";

function built(prefix) {
  const name = fs.existsSync(assets) ? fs.readdirSync(assets).find((file) => file.startsWith(prefix) && file.endsWith(".css")) : undefined;
  if (!name) throw new Error(`No built ${prefix}*.css in dist/assets. Run "npm run build" first.`);
  return pathToFileURL(path.join(assets, name)).href;
}

const SAMPLE = `
<div class="row" id="row"><div class="col" id="col">x</div></div>
<nav class="nav" id="nav"><a class="nav-link" id="navlink">a</a></nav>
<div class="modal" id="modal">m</div><button class="btn" id="btn">b</button>
<span class="badge" id="badge">s</span><input class="input" id="input">
<table class="tbl" id="tbl"><tbody><tr><td class="num" id="td">1</td></tr></tbody></table>`;

function page(withAdmin) {
  const links = [built("index-"), built("SitePages-"), ...(withAdmin ? [built("AdminApp-")] : [])];
  return `<!doctype html><html><head><meta charset="utf-8">${links.map((href) => `<link rel="stylesheet" href="${href}">`).join("")}</head>
<body>${SAMPLE}<pre id="out"></pre><script>
const out = {};
for (const skin of ["bxu", "bxs", "bxa"]) {
  document.documentElement.className = skin;
  out[skin] = {};
  for (const element of document.querySelectorAll("body [id]:not(#out)")) {
    const style = getComputedStyle(element);
    // Sorted: Chrome does not keep one order for the custom properties.
    out[skin][element.id] = Array.from(style).sort().map((name) => name + ":" + style.getPropertyValue(name)).join(";");
  }
}
document.getElementById("out").textContent = btoa(JSON.stringify(out));
</script></body></html>`;
}

function computed(withAdmin) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "bx-css-"));
  const file = path.join(dir, "page.html");
  fs.writeFileSync(file, page(withAdmin));
  const dom = execFileSync(
    chrome,
    ["--headless=new", "--no-sandbox", "--disable-gpu", "--allow-file-access-from-files", "--virtual-time-budget=4000", "--dump-dom", pathToFileURL(file).href],
    { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"], maxBuffer: 64 * 1024 * 1024 }
  );
  const match = dom.match(/<pre id="out">([^<]+)<\/pre>/);
  if (!match) throw new Error("Chrome did not return the computed styles.");
  return JSON.parse(Buffer.from(match[1], "base64").toString("utf8"));
}

const withAdmin = computed(true);
const withoutAdmin = computed(false);
const problems = [];
for (const skin of ["bxu", "bxs"]) {
  for (const [id, style] of Object.entries(withoutAdmin[skin])) {
    if (withAdmin[skin][id] !== style) problems.push(`html.${skin}: the admin stylesheet changes #${id}`);
  }
}
if (!withAdmin.bxa.row.includes("align-items:center")) problems.push("html.bxa: the admin rule .row does not apply");
if (withAdmin.bxa.row === withoutAdmin.bxa.row) problems.push("html.bxa: the admin stylesheet has no effect");

if (problems.length > 0) {
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log("Admin stylesheet isolation: OK (investor area and public site are not changed; the admin rules apply below html.bxa).");
