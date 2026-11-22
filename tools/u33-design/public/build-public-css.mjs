// Builds frontend/src/site/u33/public.css from the U33 public design (site/dist, EN pages).
//
// Usage: node build-public-css.mjs <dist> <domDir> <outCss> [--report <file>]
//   <dist>   the design's site/dist folder (read only; nothing of it is executed)
//   <domDir> rendered DOM snapshots of the design pages (harness/capture-design.js output, dom/)
//   <outCss> the stylesheet to write
//
// What it does, in order:
// 1. Page bundles. Each design page loads its own list of stylesheets, in its own order; pages
//    of one type share a list (bundle). The desktop edition list must be a subsequence of the
//    mobile edition list of the same page: the files only in the mobile list are the "mobile
//    layer" (the design shows the mobile edition below 1120 px).
// 2. One merged order of (file, layer) entries that keeps every bundle's order; an entry is used
//    by the bundles listed on it (a file is emitted twice only where two bundles load it in a
//    different order).
// 3. PurgeCSS of every file against the rendered DOMs and the design JS (dynamic classes).
// 4. Scoping: every selector gets the root `html.bxp`, plus `:where(.bxp-<bundle>,...)` when not
//    every bundle uses the entry (`:where` adds no specificity, so every rule gains exactly the
//    (0,1,1) of `html.bxp` and the design's cascade is kept). `:root`/`html` selectors get the
//    scope on the html element itself.
// 5. Mobile layer: rules wrapped in @media (max-width:1119px); nested media queries combined.
// 6. Fonts: Archivo -> "Archivo Variable" (@fontsource-variable/archivo, loaded by the app);
//    Nioicon -> family "Bxp Nioicon" with the subset ./assets/nioicon-public.woff2 (see
//    subset-nioicon.py); the design's base64 Archivo faces (assets/fonts.css) are dropped.
// 7. Keyframes renamed bxp-<name> (the app loads other stylesheets globally).
import fs from "node:fs";
import path from "node:path";
import postcss from "postcss";
import selectorParser from "postcss-selector-parser";
import { PurgeCSS } from "purgecss";

const [dist, domDir, outCss, ...rest] = process.argv.slice(2);
if (!dist || !domDir || !outCss) {
  console.error("usage: node build-public-css.mjs <dist> <domDir> <outCss> [--report <file>]");
  process.exit(2);
}
const reportIndex = rest.indexOf("--report");
const reportFile = reportIndex >= 0 ? rest[reportIndex + 1] : null;

const MOBILE_MAX = 1119;
const BUNDLES = {
  home: ["index"],
  about: ["about"],
  business: ["companies", "originators"],
  contact: ["contact"],
  legal: ["terms", "privacy", "risks"],
  project: ["residential", "manufacturing", "winery"]
};
const ALL_BUNDLES = Object.keys(BUNDLES);
const SKIP = new Set(["assets/fonts.css"]);
const NIOICON_FAMILY = '"Bxp Nioicon"';
const NIOICON_SRC = 'url("./assets/nioicon-public.woff2") format("woff2")';

function cssLinks(htmlFile) {
  const html = fs.readFileSync(htmlFile, "utf8");
  return [...html.matchAll(/<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"/g)]
    .map((m) => m[1])
    .filter((href) => !SKIP.has(href));
}

function isSubsequence(small, big) {
  let i = 0;
  for (const item of big) if (item === small[i]) i += 1;
  return i === small.length;
}

// 1. Bundles -> sequences of { href, layer }
const sequences = {};
for (const [bundle, pages] of Object.entries(BUNDLES)) {
  let reference = null;
  for (const page of pages) {
    const desktop = cssLinks(path.join(dist, `${page}.html`));
    const mobile = cssLinks(path.join(dist, "mobile", `${page}.html`));
    if (!isSubsequence(desktop, mobile)) throw new Error(`${page}: desktop stylesheets are not a subsequence of mobile`);
    const desktopSet = new Set(desktop);
    const seq = mobile.map((href) => ({ href, layer: desktopSet.has(href) ? "base" : "mobile" }));
    const key = JSON.stringify(seq);
    if (reference === null) reference = key;
    else if (reference !== key) throw new Error(`bundle ${bundle}: ${page} has another stylesheet list`);
    sequences[bundle] = seq;
  }
}

// 2. Merge: repeatedly emit a head that is not waiting behind another head in some sequence.
const entryKey = (item) => `${item.layer}:${item.href}`;
const remaining = Object.fromEntries(Object.entries(sequences).map(([b, seq]) => [b, seq.map(entryKey)]));
const merged = [];
while (Object.values(remaining).some((seq) => seq.length)) {
  const heads = [...new Set(Object.values(remaining).filter((seq) => seq.length).map((seq) => seq[0]))];
  let pick = heads.find((head) => Object.values(remaining).every((seq) => seq.indexOf(head) <= 0));
  if (!pick) pick = heads[0]; // order conflict: emit for the bundles at this head only (a duplicate)
  const bundles = Object.keys(remaining).filter((b) => remaining[b][0] === pick);
  bundles.forEach((b) => remaining[b].shift());
  const [layer, ...hrefParts] = pick.split(":");
  merged.push({ href: hrefParts.join(":"), layer, bundles });
}

function sourceFile(href, layer) {
  if (href.startsWith("/")) return path.join(dist, href.slice(1));
  return layer === "mobile" ? path.join(dist, "mobile", href) : path.join(dist, href);
}

// 3. Purge content: rendered DOMs (all states) + design JS of both editions.
const content = [
  ...fs.readdirSync(domDir).filter((f) => f.endsWith(".html")).map((f) => path.join(domDir, f)),
  ...fs.readdirSync(dist).filter((f) => f.endsWith(".js")).map((f) => path.join(dist, f)),
  ...fs.readdirSync(path.join(dist, "mobile")).filter((f) => f.endsWith(".js")).map((f) => path.join(dist, "mobile", f))
];

async function purge(raw, name) {
  const [result] = await new PurgeCSS().purge({
    content,
    css: [{ raw, name }],
    keyframes: true,
    fontFace: false,
    variables: false,
    rejected: true,
    safelist: { standard: [/^ni$/], greedy: [] }
  });
  return result;
}

// 4. Scoping
function scopeSelector(selector, scope) {
  return selectorParser((root) => {
    root.each((sel) => {
      // first compound: nodes before the first combinator
      const first = [];
      for (const node of sel.nodes) {
        if (node.type === "combinator") break;
        first.push(node);
      }
      const rootPseudo = first.find((n) => n.type === "pseudo" && n.value === ":root");
      const htmlTag = first.find((n) => n.type === "tag" && n.value.toLowerCase() === "html");
      const scopeNodes = () => {
        const nodes = [selectorParser.className({ value: "bxp" })];
        if (scope) nodes.push(selectorParser.pseudo({ value: ":where", nodes: scope.map((b) => selectorParser.selector({ nodes: [selectorParser.className({ value: `bxp-${b}` })] })) }));
        return nodes;
      };
      if (rootPseudo || htmlTag) {
        let anchor = htmlTag;
        if (rootPseudo) {
          if (!htmlTag) {
            anchor = selectorParser.tag({ value: "html" });
            rootPseudo.replaceWith(anchor);
          } else rootPseudo.remove();
        }
        let after = anchor;
        for (const node of scopeNodes()) {
          sel.insertAfter(after, node);
          after = node;
        }
      } else {
        const prefix = [selectorParser.tag({ value: "html" }), ...scopeNodes(), selectorParser.combinator({ value: " " })];
        for (let i = prefix.length - 1; i >= 0; i -= 1) sel.prepend(prefix[i]);
      }
    });
  }).processSync(selector);
}

function replaceFonts(value) {
  return value
    .replace(/(^|[\s,])(["']?)Archivo\2(?=\s*(,|$|!))/g, '$1"Archivo Variable", Archivo')
    .replace(/(^|[\s,])(["']?)Nioicon\2(?=\s*(,|$|!))/g, `$1${NIOICON_FAMILY}`);
}

const keyframeNames = new Map();
function renameAnimation(value) {
  return value
    .split(",")
    .map((part) =>
      part.replace(/[A-Za-z_][\w-]*/g, (word) => (keyframeNames.has(word) ? keyframeNames.get(word) : word))
    )
    .join(",");
}

const report = { entries: [], rejected: {}, keyframes: [], sizes: {} };
let nioiconFace = null;
const outputs = [];

for (const entry of merged) {
  const file = sourceFile(entry.href, entry.layer);
  const raw = fs.readFileSync(file, "utf8");
  const purged = await purge(raw, entry.href);
  const scope = entry.bundles.length === ALL_BUNDLES.length ? null : entry.bundles;
  const ast = postcss.parse(purged.css, { from: file });

  ast.walkAtRules("keyframes", (at) => {
    const name = at.params.trim();
    keyframeNames.set(name, `bxp-${name}`);
  });
  ast.walkAtRules("font-face", (at) => {
    let family = "";
    at.walkDecls("font-family", (d) => (family = d.value.replace(/["']/g, "").trim()));
    if (family === "Nioicon" && !nioiconFace) {
      nioiconFace = at.clone();
      nioiconFace.walkDecls("font-family", (d) => (d.value = NIOICON_FAMILY));
      nioiconFace.walkDecls("src", (d) => (d.value = NIOICON_SRC));
    }
    at.remove();
  });
  ast.walkRules((rule) => {
    if (rule.parent?.type === "atrule" && /keyframes$/.test(rule.parent.name)) return;
    rule.selector = scopeSelector(rule.selector, scope);
  });
  ast.walkDecls((decl) => {
    if (decl.prop === "font-family" || decl.prop === "font") decl.value = replaceFonts(decl.value);
  });

  if (entry.layer === "mobile") {
    const wrapper = postcss.atRule({ name: "media", params: `(max-width:${MOBILE_MAX}px)` });
    const out = postcss.root();
    ast.each((node) => {
      if (node.type === "atrule" && node.name === "media") {
        node.params = `(max-width:${MOBILE_MAX}px) and ${node.params.trim()}`;
        out.append(node.clone());
      } else if (node.type === "atrule" && /keyframes$/.test(node.name)) {
        out.append(node.clone());
      } else if (node.type === "comment") {
        // dropped
      } else {
        wrapper.append(node.clone());
      }
    });
    if (wrapper.nodes?.length) out.prepend(wrapper);
    outputs.push({ entry, root: out });
  } else {
    ast.walkComments((c) => c.remove());
    outputs.push({ entry, root: ast });
  }
  report.entries.push({ href: entry.href, layer: entry.layer, bundles: scope ?? "all", purgedBytes: purged.css.length, sourceBytes: raw.length });
  report.rejected[`${entry.layer}:${entry.href}`] = purged.rejected?.length ?? 0;
}

// 7. keyframes rename (after all names are known)
for (const { root } of outputs) {
  root.walkAtRules(/keyframes$/, (at) => (at.params = keyframeNames.get(at.params.trim()) ?? at.params));
  root.walkDecls(/^(-webkit-)?animation(-name)?$/, (decl) => (decl.value = renameAnimation(decl.value)));
}
report.keyframes = [...keyframeNames.values()];

const header = `/* IP of Webby-Soft SRL. */
/* GENERATED FILE: do not edit by hand. Put fixes in public-overrides.css.
 * Generated from the U33 public site design ("Banxum unified U33", site/dist, EN desktop pages
 * and the mobile edition dist/mobile) by tools/u33-design/public/build.sh (build-public-css.mjs):
 * per page bundle (${ALL_BUNDLES.join(", ")}) the design's stylesheets in the design's order,
 * PurgeCSS on the rendered design pages (capture-design.js) and the design JS, every
 * selector scoped to html.bxp (plus :where(.bxp-<bundle>) for files that only some page types
 * load), the mobile edition's extra layer under @media (max-width:${MOBILE_MAX}px), Archivo replaced by
 * "Archivo Variable" (@fontsource-variable/archivo), Nioicon as "Bxp Nioicon" subset
 * (assets/nioicon-public.woff2), keyframes prefixed bxp-.
 */
`;
const parts = [header];
if (nioiconFace) parts.push(nioiconFace.toString() + "\n");
for (const { entry, root } of outputs) {
  const css = root.toString().trim();
  if (!css) continue;
  const scopeText = entry.bundles.length === ALL_BUNDLES.length ? "all pages" : entry.bundles.join(", ");
  parts.push(`/* ${entry.href}${entry.layer === "mobile" ? " (mobile layer)" : ""} · ${scopeText} */\n${css}\n`);
}
const output = parts.join("\n").replace(/\n{3,}/g, "\n\n");
fs.mkdirSync(path.dirname(outCss), { recursive: true });
fs.writeFileSync(outCss, output);
report.sizes = { output: output.length, entries: merged.length };
if (reportFile) fs.writeFileSync(reportFile, JSON.stringify(report, null, 2));
console.log(`wrote ${outCss}: ${output.length} bytes, ${merged.length} entries`);
for (const e of report.entries) console.log(`  ${e.layer.padEnd(6)} ${e.href.padEnd(26)} ${String(e.sourceBytes).padStart(6)} -> ${String(e.purgedBytes).padStart(6)}  ${Array.isArray(e.bundles) ? e.bundles.join(",") : e.bundles}`);
