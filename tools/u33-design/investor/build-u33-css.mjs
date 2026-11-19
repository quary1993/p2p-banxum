// Builds frontend/src/portal/u33/u33.css from the U33 design's investor app CSS.
//
// Input (made by the other tools in this folder, never by running the design package), in the work
// folder $U33_WORK_DIR (default tools/u33-design/work/investor, ignored by git):
//   out/raw/NN-*.css + order.json  extract.py: the CSS of site/dist/app/mobile/banxum-prototype.html in
//                                  cascade order (inline <style> blocks and linked /app/*.css)
//   out/js/*.js                    extract_js.py: the design's JS sources (class names in templates)
//   snap/tokens-*.json             crawl.js: tokens of the rendered design DOM (routes x states x widths x themes)
// Output: <frontend>/src/portal/u33/u33.css and out/report.json (sizes, removed/renamed items, icon codepoints).
//
// Usage: node build-u33-css.mjs [frontend dir] [--no-legacy-guard]   (normally through build.sh)
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import postcss from 'postcss';
import selectorParser from 'postcss-selector-parser';
import { PurgeCSS } from 'purgecss';

const here = path.dirname(new URL(import.meta.url).pathname);
const frontendArg = process.argv.slice(2).find(arg => !arg.startsWith('--'));
const frontend = path.resolve(frontendArg || path.join(here, '../../../frontend'));
const work = path.resolve(process.env.U33_WORK_DIR || path.join(here, '../work/investor'));
const legacyGuard = !process.argv.includes('--no-legacy-guard');
const rawDir = path.join(work, 'out/raw');
const jsDir = path.join(work, 'out/js');
const snapDir = path.join(work, 'snap');
const outFile = path.join(frontend, 'src/portal/u33/u33.css');
const report = { removedPrototype: [], renamedKeyframes: {}, droppedFontFaces: [], weightClamped: 0 };

// ---------------------------------------------------------------------------------------------
// 1. Concatenate the design CSS in cascade order (keeps @layer statements where they were).
const order = JSON.parse(fs.readFileSync(path.join(rawDir, 'order.json'), 'utf8'));
const source = order.map(o => `/* ${o.kind}${o.kind === 'style' ? ' #' + o.file.replace(/^\d+-|\.css$/g, '') : ''} */\n` + fs.readFileSync(path.join(rawDir, o.file), 'utf8')).join('\n');
report.rawSourceBytes = Buffer.byteLength(source);

// ---------------------------------------------------------------------------------------------
// 2. Content for the purge: rendered DOM tokens + design JS + prefix expansions.
const htmlText = fs.readFileSync(path.join(work, 'out/design-body.html'), 'utf8');
const jsText = fs.readdirSync(jsDir).filter(f => f.endsWith('.js')).sort().map(f => fs.readFileSync(path.join(jsDir, f), 'utf8')).join('\n');
const tokenFiles = fs.existsSync(snapDir) ? fs.readdirSync(snapDir).filter(f => /^tokens-.*\.json$/.test(f)) : [];
const domTokens = new Set();
for (const f of tokenFiles) JSON.parse(fs.readFileSync(path.join(snapDir, f), 'utf8')).forEach(t => domTokens.add(t));
report.tokenFiles = tokenFiles;
report.domTokens = domTokens.size;

// Class names the JS builds from a prefix and a data value (`ni-${icon}`, 'tag-' + status):
// keep prefix+word for every word of the JS/DOM that completes a class existing in the CSS.
const prefixes = new Set();
for (const m of jsText.matchAll(/([a-z][a-z0-9_]*(?:-[a-z0-9_]+)*-)\$\{/g)) prefixes.add(m[1]);
for (const m of jsText.matchAll(/['"]([a-z][a-z0-9_]*(?:-[a-z0-9_]+)*-)['"]\s*\+/g)) prefixes.add(m[1]);
// Attributes the JS sets through element.dataset.camelCase are data-kebab-case in the DOM; the root
// attributes (theme, edition...) are set by script only.
const datasetAttrs = new Set(['data-theme', 'data-edition', 'data-responsive', 'data-visual-study', 'data-language', 'dark', 'light', 'refined', 'ars', 'true', 'de', 'en']);
for (const m of jsText.matchAll(/dataset\.([a-zA-Z][a-zA-Z0-9]*)/g)) datasetAttrs.add('data-' + m[1].replace(/[A-Z]/g, c => '-' + c.toLowerCase()));
for (const m of jsText.matchAll(/dataset\[['"]([a-zA-Z][a-zA-Z0-9]*)['"]\]/g)) datasetAttrs.add('data-' + m[1].replace(/[A-Z]/g, c => '-' + c.toLowerCase()));
report.datasetAttributes = datasetAttrs.size;
const words = new Set([...jsText.matchAll(/[A-Za-z0-9_-]+/g)].map(m => m[0]));
domTokens.forEach(t => words.add(t));
const cssClasses = new Set([...source.matchAll(/\.(-?[_a-zA-Z][_a-zA-Z0-9-]*)/g)].map(m => m[1]));
const expanded = new Set();
for (const cls of cssClasses) {
  for (const p of prefixes) {
    if (cls.startsWith(p) && words.has(cls.slice(p.length))) expanded.add(cls);
  }
}
report.dynamicPrefixes = [...prefixes].sort();
report.prefixExpansions = expanded.size;

// ---------------------------------------------------------------------------------------------
// 3. Prototype-only rules (preview wrapper, demo tools, sample-data notes): removed before the purge.
const prototypeOnly = [
  /\.si-preview/, /#si-preview/, /\.bxm-proto-note/, /\.p73-demo/, /\.s106-demo/, /\.pd-sample/, /\.ca-prototype/,
  /\.ca-preview-bar/, /\.u04-account\s+\.prototype/, /\.prototype\b/, /\[data-action=["']?reset/, /simulate-deposit/,
  /\[data-ca-action=["']?demo/, /\.p99-demo/, /\.bxm-demo/, /\.view-switch/, /\.preview-(?:bar|frame|device|wrap)/,
];

function dropPrototypeRules(root) {
  root.walkRules(rule => {
    if (rule.parent && rule.parent.type === 'atrule' && /keyframes$/i.test(rule.parent.name)) return;
    const kept = rule.selectors.filter(sel => !prototypeOnly.some(re => re.test(sel)));
    if (kept.length === rule.selectors.length) return;
    report.removedPrototype.push(...rule.selectors.filter(sel => !kept.includes(sel)));
    if (kept.length) rule.selectors = kept; else rule.remove();
  });
}

// ---------------------------------------------------------------------------------------------
// 4. Fonts: Archivo -> "Archivo Variable" (@fontsource-variable/archivo, loaded in main.tsx),
//    Nioicon -> the local subset file, fcicons dropped when no kept rule uses it.
function familyValue(value) {
  return value.replace(/(["']?)Archivo\1(?!\s*Variable)/g, '"Archivo Variable", "Archivo"');
}
// The design embeds Archivo only at 400, 500 and 600, so browsers render 100-300 as 400 and 700-900
// (bold, bolder) as 600 (measured in the design: equal widths, no synthesis). A variable font renders
// the real weights, so the values are clamped to what the design shows.
function clampWeight(value) {
  const v = value.trim();
  if (/^(100|200|300)$/.test(v)) return '400';
  if (/^(700|800|900|bold|bolder)$/.test(v)) return '600';
  return value;
}
function fixFonts(root) {
  root.walkAtRules('font-face', at => {
    let family = '';
    at.walkDecls('font-family', d => { family = d.value.replace(/["']/g, '').trim(); });
    if (family === 'Archivo') { report.droppedFontFaces.push('Archivo ' + (at.nodes.find(n => n.prop === 'font-weight')?.value || '')); at.remove(); }
    else if (family === 'Nioicon') at.remove(); // replaced by one local @font-face below
    else if (family === 'fcicons') at.remove(); // re-added below only if a kept rule uses it
  });
  root.walkDecls(decl => {
    if (decl.prop === 'font-family' || decl.prop === 'font' || (decl.prop.startsWith('--') && /font/i.test(decl.prop))) {
      const next = familyValue(decl.value);
      if (next !== decl.value) decl.value = next;
    }
    if (decl.prop === 'font-weight' || decl.prop === '--bs-body-font-weight' || decl.prop === '--bs-nav-link-font-weight' || decl.prop === '--bs-btn-font-weight' || decl.prop === '--bs-badge-font-weight') {
      const next = clampWeight(decl.value);
      if (next !== decl.value) { decl.value = next; report.weightClamped++; }
    }
    if (decl.prop === 'font' && /\b(700|800|900|bold)\b/.test(decl.value) && /Archivo/.test(decl.value)) {
      decl.value = decl.value.replace(/\b(700|800|900|bold)\b/, '600');
      report.weightClamped++;
    }
  });
}

// ---------------------------------------------------------------------------------------------
// 5. Scope every rule to html.bxu (the U33 investor skin class, set by portal/U33Skin.tsx).
//    Every selector gains exactly the specificity of one class (0,1,0), so the design's own cascade
//    (which rule wins over which) is unchanged:
//    - a root compound with html keeps it: html[...] -> html.bxu[...]; :root -> :root.bxu;
//      :where(html[...]) -> :where(html[...]).bxu;
//    - a selector starting with a root attribute ([data-theme=dark] ...) -> :where(html).bxu[data-theme=dark] ...;
//    - everything else, body included -> ":where(html).bxu " + selector (= html.bxu, html at zero specificity).
//    The design's root switches stay as written ([data-edition="refined"], [data-responsive],
//    [data-visual-study="ars"], [data-language]): U33Skin sets them on <html>.
//    Legacy guard (migration, see u33-overrides.css): the subject of every rule below html/body gets
//    :where(:not(.bxu-legacy *)) (zero specificity), so old screen bodies wrapped in .bxu-legacy
//    keep the old skin.
const rootAttrs = new Set(['data-edition', 'data-responsive', 'data-visual-study', 'data-theme', 'data-language']);
const pseudoElementNames = new Set(['::before', '::after', ':before', ':after', '::first-letter', ':first-letter', '::first-line', ':first-line', '::placeholder', '::selection', '::marker', '::backdrop', '::file-selector-button', '::cue', '::part', '::slotted', '::grammar-error', '::spelling-error', '::target-text', '::details-content']);
const isPseudoElement = n => n.type === 'pseudo' && (pseudoElementNames.has(n.value) || n.value.startsWith('::'));
const isHtmlTag = n => n.type === 'tag' && n.value.toLowerCase() === 'html';
const isWhereHtml = n => n.type === 'pseudo' && (n.value === ':where' || n.value === ':is') && n.nodes.length > 0 &&
  n.nodes.every(inner => inner.nodes.length > 0 && isHtmlTag(inner.nodes[0]) && !inner.nodes.some(x => x.type === 'combinator'));
const zeroHtml = () => {
  const where = selectorParser.pseudo({ value: ':where' });
  const inner = selectorParser.selector();
  inner.append(selectorParser.tag({ value: 'html' }));
  where.append(inner);
  return where;
};

// Words the old investor screens can carry as class names: every class of the old skins' CSS and every
// word of the old screen sources (a superset). A rule whose subject needs a class outside this set
// cannot match an old element, so it needs no legacy guard.
function legacyWordSet() {
  const set = new Set();
  const src = path.join(frontend, 'src');
  const cssFiles = ['styles.css', 'banxumSkin.css', ...fs.readdirSync(path.join(src, 'skin')).map(f => 'skin/' + f)];
  for (const f of cssFiles) for (const m of fs.readFileSync(path.join(src, f), 'utf8').matchAll(/\.(-?[_a-zA-Z][_a-zA-Z0-9-]*)/g)) set.add(m[1]);
  const codeFiles = ['App.tsx', ...fs.readdirSync(path.join(src, 'investorPortal')).filter(f => /\.tsx?$/.test(f) && !/\.test\./.test(f)).map(f => 'investorPortal/' + f)];
  for (const f of codeFiles) for (const m of fs.readFileSync(path.join(src, f), 'utf8').matchAll(/[A-Za-z0-9_-]+/g)) set.add(m[0]);
  return set;
}
const legacyWords = legacyGuard ? legacyWordSet() : new Set();
report.guardedSelectors = 0;
report.unguardedSelectors = 0;

function scopeSelector(selector) {
  return selectorParser(selectors => {
    selectors.each(sel => {
      const nodes = sel.nodes;
      let firstCombinator = nodes.findIndex(n => n.type === 'combinator');
      if (firstCombinator === -1) firstCombinator = nodes.length;
      const first = nodes.slice(0, firstCombinator);
      const htmlTag = first.find(isHtmlTag);
      const rootPseudo = first.find(n => n.type === 'pseudo' && n.value === ':root');
      const whereHtml = first.length === 1 && isWhereHtml(first[0]) ? first[0] : null;
      const startsWithRootAttr = first.length > 0 && first[0].type === 'attribute' && rootAttrs.has(first[0].attribute);
      const bxu = () => selectorParser.className({ value: 'bxu' });
      if (htmlTag) sel.insertAfter(htmlTag, bxu());
      else if (rootPseudo) sel.insertAfter(rootPseudo, bxu());
      else if (whereHtml) sel.insertAfter(whereHtml, bxu());
      else if (startsWithRootAttr) { sel.prepend(bxu()); sel.prepend(zeroHtml()); }
      else { sel.prepend(selectorParser.combinator({ value: ' ' })); sel.prepend(bxu()); sel.prepend(zeroHtml()); }
      if (!legacyGuard) return;
      const all = sel.nodes;
      let lastComb = -1;
      all.forEach((n, i) => { if (n.type === 'combinator') lastComb = i; });
      if (lastComb === -1) return; // the root compound itself
      const subject = all.slice(lastComb + 1);
      if (subject.some(n => n.type === 'tag' && n.value.toLowerCase() === 'body')) return;
      const subjectClasses = subject.filter(n => n.type === 'class').map(n => n.value);
      if (subjectClasses.length && !subjectClasses.every(c => legacyWords.has(c))) { report.unguardedSelectors++; return; }
      report.guardedSelectors++;
      const guard = selectorParser.pseudo({ value: ':where' });
      const inner = selectorParser.selector();
      const not = selectorParser.pseudo({ value: ':not' });
      const notSel = selectorParser.selector();
      notSel.append(selectorParser.className({ value: 'bxu-legacy' }));
      notSel.append(selectorParser.combinator({ value: ' ' }));
      notSel.append(selectorParser.universal());
      not.append(notSel);
      inner.append(not);
      guard.append(inner);
      const pe = subject.find(isPseudoElement);
      if (pe) sel.insertBefore(pe, guard); else sel.append(guard);
    });
  }).processSync(selector, { lossless: false });
}

// A rule nested in another style rule (native CSS nesting, possibly inside @media/@supports) is
// relative to its parent, which is already scoped: prefixing it again would make it read
// "<parent> :where(html).bxu X", which never matches. Such rules are left as they are.
function isNestedInStyleRule(rule) {
  for (let p = rule.parent; p; p = p.parent) {
    if (p.type === 'rule') return true;
    if (p.type === 'root') return false;
  }
  return false;
}
report.nestedRulesKept = 0;

// Q27 (owner answer 2026-11-13): two selectors of the design CSS are not valid CSS, so browsers
// ignore them (`.close:not(:disabled):not(.disabled):hover-focus` and
// `.nk-iv-wg3-list:last-child() li:nth-last-child(2)`). They are dropped; the visible look stays.
const INVALID_SELECTOR = /:hover-focus\b|:last-child\(\)/;
report.invalidSelectorsDropped = [];

function dropInvalidSelectors(root) {
  root.walkRules(rule => {
    const kept = rule.selectors.filter(sel => !INVALID_SELECTOR.test(sel));
    if (kept.length === rule.selectors.length) return;
    report.invalidSelectorsDropped.push(...rule.selectors.filter(sel => INVALID_SELECTOR.test(sel)));
    if (kept.length) rule.selectors = kept; else rule.remove();
  });
}

function scope(root) {
  dropInvalidSelectors(root);
  root.walkRules(rule => {
    const parent = rule.parent;
    if (parent && parent.type === 'atrule' && /keyframes$/i.test(parent.name)) return;
    if (isNestedInStyleRule(rule)) { report.nestedRulesKept++; return; }
    const scoped = [];
    for (const sel of rule.selectors) {
      scoped.push(scopeSelector(sel));
    }
    if (scoped.length) rule.selectors = scoped; else rule.remove();
  });
}

// ---------------------------------------------------------------------------------------------
// 6. Keyframes that clash with the app's own CSS get a "u33-" prefix (with their uses).
function appKeyframes() {
  const names = new Set();
  const walk = dir => {
    for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, f.name);
      if (f.isDirectory()) { if (!p.includes('/portal/u33')) walk(p); }
      else if (f.name.endsWith('.css')) for (const m of fs.readFileSync(p, 'utf8').matchAll(/@(?:-webkit-)?keyframes\s+([A-Za-z0-9_-]+)/g)) names.add(m[1]);
    }
  };
  walk(path.join(frontend, 'src'));
  return names;
}
// The design's phone layer selects html[data-responsive], which only its mobile edition sets; the app
// sets it at every width (one DOM). Almost every such rule sits in @media (max-width:1199px); the few
// that do not (top-level blocks) would change the desktop layout, so they get the same media query.
report.responsiveRulesLimited = 0;
function limitResponsiveLayer(root) {
  const targets = [];
  root.walkRules(rule => {
    if (!rule.selectors.length || !rule.selectors.every(sel => /\[data-responsive/.test(sel))) return;
    for (let p = rule.parent; p && p.type !== 'root'; p = p.parent) {
      if (p.type === 'rule') return;
      if (p.type === 'atrule' && (p.name === 'media' || /keyframes$/i.test(p.name))) return;
    }
    targets.push(rule);
  });
  for (const rule of targets) {
    const media = postcss.atRule({ name: 'media', params: '(max-width:1199px)' });
    rule.replaceWith(media);
    media.append(rule);
    report.responsiveRulesLimited++;
  }
}

function renameKeyframes(root) {
  const clash = appKeyframes();
  const renamed = {};
  root.walkAtRules(/keyframes$/i, at => {
    if (clash.has(at.params)) { renamed[at.params] = 'u33-' + at.params; at.params = renamed[at.params]; }
  });
  if (!Object.keys(renamed).length) return;
  root.walkDecls(/^(-webkit-)?animation(-name)?$/, decl => {
    decl.value = decl.value.replace(/[A-Za-z0-9_-]+/g, w => renamed[w] || w);
  });
  report.renamedKeyframes = renamed;
}

// ---------------------------------------------------------------------------------------------
// 7. Icon font codepoints used by the kept rules (for the subset).
function iconCodepoints(root) {
  const nio = new Set();
  const fc = new Set();
  let usesFc = false;
  root.walkRules(rule => {
    let family = '';
    rule.walkDecls(/^font(-family)?$/, d => { family += d.value; });
    rule.walkDecls('content', d => {
      for (const m of d.value.matchAll(/\\([0-9a-fA-F]{2,6})/g)) {
        const cp = parseInt(m[1], 16);
        if (cp >= 0xe000 && cp <= 0xf8ff) (/fcicons/.test(family) ? fc : nio).add(cp);
      }
      for (const ch of d.value.matchAll(/[\ue000-\uf8ff]/g)) (/fcicons/.test(family) ? fc : nio).add(ch[0].codePointAt(0));
    });
    if (/fcicons/.test(family)) usesFc = true;
  });
  return { nio: [...nio].sort((a, b) => a - b), fc: [...fc], usesFc };
}

// ---------------------------------------------------------------------------------------------
// purgecss rejects the arguments of :is()/:where()/:not() that are only pseudo-classes
// (:is(:nth-child(2),:nth-child(3)), :not(:focus-visible)...) and then drops the whole rule, although
// nothing in them depends on the page's classes. Such lists are replaced by a placeholder attribute
// during the purge and restored afterwards.
const pseudoLists = [];
const isPseudoOnlyList = node => node.type === 'pseudo' && [':is', ':where', ':not', ':matches'].includes(node.value) &&
  node.nodes.length > 0 && node.nodes.every(inner => inner.nodes.length > 0 && inner.nodes.every(n => n.type === 'pseudo'));
function protectPseudoLists(root) {
  root.walkRules(rule => {
    if (rule.parent && rule.parent.type === 'atrule' && /keyframes$/i.test(rule.parent.name)) return;
    if (!/:(is|where|not|matches)\(/.test(rule.selector)) return;
    rule.selector = selectorParser(selectors => {
      selectors.walkPseudos(node => {
        if (!isPseudoOnlyList(node)) return;
        const id = pseudoLists.push(String(node)) - 1;
        node.replaceWith(selectorParser.attribute({ attribute: 'data-bxu-keep', operator: '=', value: `"bxukeep${id}"`, raws: {} }));
      });
    }).processSync(rule.selector, { lossless: false });
  });
}
function restorePseudoLists(css) {
  return css.replace(/\[data-bxu-keep="?bxukeep(\d+)"?\]/g, (_, id) => pseudoLists[Number(id)]);
}
// The design's CSS has a few declarations with an unbalanced ")" (e.g. "color:#f3f5f4)!important").
// Browsers drop such declarations, so they never applied in the design; the production minifier
// (Lightning CSS) refuses them. They are removed, which keeps the design's rendering.
report.droppedInvalidDeclarations = [];
function dropInvalidDeclarations(root) {
  root.walkDecls(decl => {
    const value = `${decl.value}${decl.important ? '' : ''}`;
    const open = (value.match(/\(/g) || []).length;
    const close = (value.match(/\)/g) || []).length;
    if (open === close) return;
    const selector = decl.parent && decl.parent.selector ? decl.parent.selector.slice(0, 120) : '';
    report.droppedInvalidDeclarations.push(`${selector} { ${decl.prop}: ${decl.value} }`);
    decl.remove();
  });
}
const stage1 = postcss.parse(source);
dropPrototypeRules(stage1);
dropInvalidDeclarations(stage1);
fixFonts(stage1);
protectPseudoLists(stage1);
report.protectedPseudoLists = pseudoLists.length;
const purgeContent = [...domTokens].join(' ') + '\n' + [...datasetAttrs].join(' ') + '\n' + [...expanded].join(' ') + '\n' + htmlText + '\n' + jsText +
  '\ndata-bxu-keep ' + pseudoLists.map((_, id) => `bxukeep${id}`).join(' ');

const purged = await new PurgeCSS().purge({
  content: [{ raw: purgeContent, extension: 'html' }],
  css: [{ raw: stage1.toString() }],
  defaultExtractor: content => content.match(/[A-Za-z0-9_-]+/g) || [],
  fontFace: false,
  keyframes: true,
  variables: false,
  rejected: true,
  safelist: {
    standard: [
      /^show$/, /^showing$/, /^hiding$/, /^active$/, /^open$/, /^collapsed$/, /^collapse$/, /^collapsing$/, /^fade$/,
      /^in$/, /^disabled$/, /^selected$/, /^current/, /^expanded$/, /^was-validated$/, /^is-/, /^has-/, /^modal/,
      /^dropdown/, /^offcanvas/, /^bxm-theme-switching$/, /^mobile-menu-open$/, /^nav-shown$/, /^nk-sidebar-active$/,
      /^nk-sidebar-mobile$/, /^nk-sidebar-compact$/, /^is-compact$/, /^compact/, /^as-mobile$/, /^has-touch$/, /^no-touch$/,
      /^tooltip/, /^bs-tooltip/, /^popover/, /^bs-popover/, /^toast/, /^visually-hidden/, /^sr-only/,
      /^bxu/, /^bxm-app$/, /^nk-body$/, /^dark$/, /^light$/,
    ],
  },
});
const purgedCss = restorePseudoLists(purged[0].css);
report.rejectedSelectors = (purged[0].rejected || []).length;
fs.writeFileSync(path.join(work, 'out/rejected.txt'), (purged[0].rejected || []).join('\n'));

const root = postcss.parse(purgedCss);
scope(root);
limitResponsiveLayer(root);
renameKeyframes(root);
// Drop empty at-rules left by the purge.
let changed = true;
while (changed) {
  changed = false;
  root.walkAtRules(at => { if (at.nodes && at.nodes.length === 0 && !['layer'].includes(at.name)) { at.remove(); changed = true; } });
}
root.walkComments(c => { if (!/^!/.test(c.text)) c.remove(); });
const icons = iconCodepoints(root);
report.iconCodepoints = icons.nio.length;
report.fcicons = icons.usesFc;
fs.writeFileSync(path.join(work, 'out/nioicon-codepoints.txt'), icons.nio.map(cp => 'U+' + cp.toString(16).toUpperCase()).join(','));

const fontFaces = [
  '@font-face{font-family:"Nioicon";src:url("./assets/nioicon-u33.woff2") format("woff2");font-weight:normal;font-style:normal;font-display:block}',
];
if (icons.usesFc) fontFaces.push('@font-face{font-family:"fcicons";src:url("./assets/fcicons-u33.woff2") format("woff2");font-weight:normal;font-style:normal}');

const header = `/* IP of Webby-Soft SRL. */
/* GENERATED FILE: do not edit by hand. Put fixes in u33-overrides.css.
 * Source: U33 design package website_redesign_nov3 (edition "Banxum unified U33", 3 Nov 2026),
 * site/dist/app/mobile/banxum-prototype.html = every desktop layer + bxm-responsive-mobile: its 23
 * inline <style> blocks and 25 linked /app/*.css files, concatenated in document (cascade) order,
 * @layer order kept (bxm-dark, bxm-dark-base).
 * Generated by tools/u33-design/investor/build.sh (build-u33-css.mjs; see tools/u33-design/README.md):
 * - PurgeCSS 7 with content = rendered DOM tokens of the design app (crawl.js: every route of
 *   inventories/routes.csv, dialogs, menus, wizard steps and states, 1440 and 390 px, light and dark)
 *   + the design JS sources + class names its templates build from a prefix; safelist for state classes.
 * - Prototype-only rules removed (preview wrapper, si-preview, "Reset prototype", sample-data notes,
 *   demo tools).
 * - Archivo faces replaced by "Archivo Variable" (@fontsource-variable/archivo, main.tsx); font weights
 *   clamped to the 400-600 faces the design embeds (it renders 300 as 400 and 700/bold as 600).
 * - Nioicon subset to the ${icons.nio.length} glyphs the kept rules use (assets/nioicon-u33.woff2)${icons.usesFc ? ', fcicons subset (assets/fcicons-u33.woff2)' : '; fcicons dropped (unused)'}.
 * - Every selector scoped to html.bxu (portal/U33Skin.tsx) with exactly one class of extra
 *   specificity, so the design's cascade is unchanged: html[..] -> html.bxu[..], :root -> :root.bxu,
 *   :where(html[..]) -> :where(html[..]).bxu, a leading [data-theme] -> :where(html).bxu[data-theme],
 *   body and everything else -> ":where(html).bxu <selector>". The design's root attributes
 *   (data-edition, data-responsive, data-visual-study, data-language) are kept; U33Skin sets them.${legacyGuard ? `
 * - Migration guard: :where(:not(.bxu-legacy *)) (zero specificity) on the subject of every rule
 *   that could match an old screen element (subject without a class, or with only class names the
 *   old skins/screens use), so old bodies wrapped in .bxu-legacy keep the old skin (u33-overrides.css).` : ''}${Object.keys(report.renamedKeyframes).length ? `
 * - Keyframes renamed to avoid clashes with the app CSS: ${Object.entries(report.renamedKeyframes).map(([a, b]) => a + ' -> ' + b).join(', ')}.` : ''}
 * Third-party CSS included: Bootstrap v5.3 (MIT, https://github.com/twbs/bootstrap/blob/main/LICENSE),
 * DashLite 3.3.1 / Nioicon (Softnio, template licence purchased by Banxum; check per U33-DEC-37),
 * SimpleBar (MIT) rules as used by the design. Archivo: SIL Open Font License 1.1 (via @fontsource).
 */
`;
const body = root.toString().replace(/\n{2,}/g, '\n').trim();
const css = header + fontFaces.join('\n') + '\n' + body + '\n';
fs.mkdirSync(path.dirname(outFile), { recursive: true });
fs.writeFileSync(outFile, css);
report.outputBytes = Buffer.byteLength(css);
report.outputGzipBytes = zlib.gzipSync(css, { level: 9 }).length;
report.outputBrotliBytes = zlib.brotliCompressSync(css).length;
let ruleCount = 0;
root.walkRules(() => { ruleCount++; });
report.rules = ruleCount;
fs.writeFileSync(path.join(work, 'out/report.json'), JSON.stringify(report, null, 1));
console.log(JSON.stringify({ ...report, removedPrototype: report.removedPrototype.length, dynamicPrefixes: report.dynamicPrefixes.length }, null, 1));
