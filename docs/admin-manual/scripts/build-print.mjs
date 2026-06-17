// Produces manual-print.html: manual.html with every inline annotated <svg>
// replaced by a flat <img> pointing at figures/annotated/<id>.png. Plain <img>
// prints reliably in headless Chrome. Usage: node build-print.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const base = path.resolve(here, "..");
let html = fs.readFileSync(path.join(base, "manual.html"), "utf8");

let count = 0;
html = html.replace(/<svg class="figsvg" data-fig="([^"]+)"[^>]*width="([^"]+)"[^>]*height="([^"]+)"[\s\S]*?<\/svg>/g, (m, id, w, h) => {
  count++;
  return `<img class="figsvg" src="figures/annotated/${id}.png" width="${w}" height="${h}" style="max-width:100%;height:auto;"/>`;
});
fs.writeFileSync(path.join(base, "manual-print.html"), html);
console.log("build-print: replaced", count, "svgs ->", (html.length / 1024).toFixed(0) + "KB");
