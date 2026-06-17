// Splits manual-print.html into chunks of <= MAX_IMGS images each, so that
// each chunk prints reliably (headless Chrome crashes printing too many images
// at once). Cover+TOC go in part 1. Writes manual-part<N>.html and prints the
// chunk list to stdout. Usage: node split-print.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const base = path.resolve(here, "..");
const MAX_IMGS = 10;

const html = fs.readFileSync(path.join(base, "manual-print.html"), "utf8");
const head = html.match(/<head>[\s\S]*?<\/head>/)[0];
const coverToc = html.slice(html.indexOf('<div class="cover">'), html.indexOf('<div class="wrap">'));
const wrapInner = html.slice(html.indexOf('<div class="wrap">') + '<div class="wrap">'.length, html.lastIndexOf("</div>"));

const pieces = wrapInner.split(/(?=<section class="screen")/).filter((s) => s.trim());
const imgsIn = (s) => (s.match(/<img/g) || []).length;

const chunks = [];
let cur = [], curImgs = 0;
for (const p of pieces) {
  const c = imgsIn(p);
  if (cur.length && curImgs + c > MAX_IMGS) { chunks.push(cur); cur = []; curImgs = 0; }
  cur.push(p); curImgs += c;
}
if (cur.length) chunks.push(cur);

const firstChildAuto = "<style>.wrap > .screen:first-child{break-before:auto !important}</style>";
const files = [];
chunks.forEach((sections, i) => {
  const part = i + 1;
  const body = `<body>${i === 0 ? coverToc : ""}<div class="wrap">${sections.join("")}</div></body>`;
  const doc = `<!DOCTYPE html><html lang="en">${head}${i === 0 ? "" : firstChildAuto}${body}</html>`;
  const name = `manual-part${part}.html`;
  fs.writeFileSync(path.join(base, name), doc);
  files.push(name);
  console.error(`part${part}: ${sections.length} sections, ${sections.reduce((n, s) => n + imgsIn(s), 0)} imgs`);
});
process.stdout.write(files.join(" "));
