// IP of Webby-Soft SRL.
// Renders the U33 design investor app (site/dist/app/mobile/banxum-prototype.html, served by the
// static server) through every route of inventories/routes.csv plus the states reached by clicking
// its controls (menus, dropdowns, dialogs, tabs, wizard steps), and records every token that a CSS
// selector can match: tag names, ids, classes, attribute names and attribute values.
// Usage: node crawl.js <out dir> <context: desk-light|desk-dark|mob-light|mob-dark> [maxClicksPerRoute]
// Output: <out>/tokens-<context>.json, <out>/dom-<context>/<route>.html (stripped route snapshots),
//         <out>/log-<context>.txt (runtime <style> additions, errors).
const fs = require('fs');
const path = require('path');
const { chromium, devices } = require('playwright');

const BASE = process.env.DESIGN_BASE || 'http://127.0.0.1:8090/app/mobile/banxum-prototype.html?lang=en';
const [outDir, contextName, maxClicksArg] = process.argv.slice(2);
const MAX_CLICKS = Number(maxClicksArg || 70);
const [device, theme] = contextName.split('-');

const projects = ['bx-1048', 'bx-1046', 'bx-1049', 'bx-1044', 'bx-1045', 'bx-1050', 'bx-1051', 'bx-1052', 'bx-1053', 'bx-1031', 'bx-1027', 'bx-1022', 'bx-1024', 'bx-1019', 'bx-1036', 'bx-1012'];
const investments = ['INV-10501', 'INV-10455', 'INV-10412', 'INV-10388', 'INV-10148', 'INV-10297', 'INV-10277', 'INV-10102'];
const settingsTabs = ['personal', 'security', 'bank-accounts', 'notifications', 'verification', 'agreements', 'preferences', 'declarations'];
const creditSections = ['summary', 'borrower', 'financials', 'security', 'terms', 'checks', 'documents'];
const onboardingSteps = ['details', 'email', 'phone', 'pin', 'identity', 'review', 'approved', 'company', 'security'];

const routes = [
  '#/overview', '#/projects', '#/projects/archive', '#/investments', '#/account', '#/transactions', '#/reports',
  '#/secondary', '#/auto-invest', '#/documents', '#/documents/contracts', '#/documents/legal', '#/notifications', '#/help',
  '#/originators', '#/originators/brueckfeld', '#/originators/lindmatt', '#/originators/poiana', '#/404',
  '#/login', '#/login/code', '#/signup', '#/signup/email', '#/forgot',
  ...settingsTabs.map(t => `#/settings/${t}`),
  ...onboardingSteps.map(s => `#/onboarding/${s}`),
  ...projects.map(p => `#/projects/${p}`),
  ...projects.slice(0, 6).map(p => `#/projects/${p}/invest`),
  ...projects.slice(0, 6).map(p => `#/projects/${p}/invest?step=review`),
  ...projects.slice(0, 3).map(p => `#/projects/${p}/invest?step=done`),
  ...projects.map(p => `#/projects/${p}/credit-file`),
  ...creditSections.map(s => `#/projects/bx-1046/credit-file?section=${s}`),
  '#/projects/bx-1031?from=archive', '#/projects/bx-1046?from=review', '#/projects/bx-1046/credit-file?from=review',
  ...investments.map(i => `#/investments/${i}`),
];
// Clicking every control on the long, repetitive pages is not needed: one route per kind is crawled deeply.
const deepCrawl = new Set([
  '#/overview', '#/projects', '#/projects/archive', '#/investments', '#/account', '#/transactions', '#/reports',
  '#/secondary', '#/auto-invest', '#/documents', '#/documents/legal', '#/notifications', '#/help', '#/originators',
  '#/originators/brueckfeld', '#/login', '#/signup', '#/forgot',
  ...settingsTabs.map(t => `#/settings/${t}`),
  '#/onboarding/details', '#/projects/bx-1048', '#/projects/bx-1046', '#/projects/bx-1045', '#/projects/bx-1031',
  '#/projects/bx-1048/invest', '#/projects/bx-1048/invest?step=review', '#/projects/bx-1045/invest?step=review',
  '#/projects/bx-1046/credit-file', '#/projects/bx-1046/credit-file?section=documents', '#/projects/bx-1046/credit-file?section=financials',
  ...investments.map(i => `#/investments/${i}`),
]);

const tokens = new Set();
const log = [];
const domDir = path.join(outDir, `dom-${contextName}`);
fs.mkdirSync(domDir, { recursive: true });

function collect(page) {
  return page.evaluate(() => {
    const out = new Set();
    const add = v => { if (v) String(v).split(/[\s,;:()"'=]+/).forEach(w => { if (w && w.length < 80) out.add(w); }); };
    for (const el of document.querySelectorAll('*')) {
      out.add(el.tagName.toLowerCase());
      for (const a of el.attributes) {
        out.add(a.name);
        if (a.name === 'class' || a.name === 'id' || a.name.startsWith('data-') || a.name.startsWith('aria-') || ['role', 'type', 'name', 'lang', 'dir', 'inputmode', 'for', 'scope', 'target', 'rel', 'autocomplete', 'loading', 'hidden', 'open', 'disabled', 'checked', 'selected', 'readonly', 'tabindex', 'href', 'value', 'placeholder', 'title', 'alt', 'colspan', 'rowspan', 'width', 'height', 'style'].includes(a.name)) {
          if (a.value.length < 300) add(a.value);
        }
      }
    }
    return [...out];
  });
}

async function styleCount(page) {
  return page.evaluate(() => [...document.querySelectorAll('style, link[rel=stylesheet]')].map(s => s.id || s.getAttribute('href') || `style:${s.textContent.length}`).join('|'));
}

async function addTokens(page) {
  try { (await collect(page)).forEach(t => tokens.add(t)); } catch (e) { log.push('collect ' + String(e).slice(0, 200)); }
}

async function snapshot(page, name) {
  try {
    const html = await page.evaluate(() => document.documentElement.outerHTML);
    const stripped = html
      .replace(/<script\b[\s\S]*?<\/script>/g, '')
      .replace(/<style\b[\s\S]*?<\/style>/g, '<style></style>')
      .replace(/data:[a-z/+.-]+;base64,[A-Za-z0-9+/=]+/g, 'data:...');
    fs.writeFileSync(path.join(domDir, name.replace(/[^a-z0-9-]+/gi, '_').slice(0, 120) + '.html'), stripped);
  } catch (e) { log.push('snapshot ' + name + ' ' + String(e).slice(0, 200)); }
}

async function closeEverything(page) {
  for (let i = 0; i < 2; i++) { try { await page.keyboard.press('Escape'); } catch (e) {} }
  await page.evaluate(() => {
    document.querySelectorAll('dialog[open]').forEach(d => { try { d.close(); } catch (e) {} });
    if (window.bootstrap && window.bootstrap.Modal) document.querySelectorAll('.modal.show').forEach(m => { try { window.bootstrap.Modal.getOrCreateInstance(m).hide(); } catch (e) {} });
    document.documentElement.classList.remove('mobile-menu-open');
  }).catch(() => {});
  await page.waitForTimeout(250);
}

async function candidates(page, scopeSelector) {
  return page.evaluate((scopeSelector) => {
    const scope = scopeSelector ? document.querySelector(scopeSelector) : document;
    if (!scope) return [];
    const sel = '[data-action], [data-bs-toggle], [data-ca-action], [data-ca-state], button, summary, [role=tab], [role=button], a[href="#"], a[href^="#/"], input[type=checkbox], input[type=radio], select, input[type=range], [aria-expanded]';
    const seen = new Set();
    const out = [];
    let n = 0;
    for (const el of scope.querySelectorAll(sel)) {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none') continue;
      if (el.closest('.nk-sidebar') && scopeSelector !== '.nk-sidebar') continue; // sidebar links are routes we visit anyway
      const href = el.getAttribute('href') || '';
      if (href.startsWith('#/') && !el.dataset.action) continue; // plain navigation: routes are visited directly
      const action = el.dataset.action || el.dataset.caAction || el.dataset.bsToggle || el.getAttribute('role') || el.tagName;
      if (['reset', 'sign-out', 'logout'].includes(action)) continue;
      const sig = [el.tagName, action, el.dataset.id || '', el.dataset.value || el.dataset.tab || el.dataset.filter || el.dataset.sort || el.dataset.view || '', (el.textContent || '').trim().slice(0, 30), el.getAttribute('aria-label') || '', el.type || ''].join('|');
      if (seen.has(sig)) continue;
      seen.add(sig);
      const id = 'c' + (n++);
      el.setAttribute('data-crawl-id', id);
      out.push({ id, sig });
    }
    return out;
  }, scopeSelector);
}

async function clickCandidate(page, cand) {
  const loc = page.locator(`[data-crawl-id="${cand.id}"]`);
  if (!(await loc.count())) return false;
  const tag = await loc.evaluate(el => el.tagName).catch(() => '');
  try {
    if (tag === 'SELECT') {
      const values = await loc.evaluate(el => [...el.options].map(o => o.value));
      for (const v of values.slice(0, 6)) { await loc.selectOption(v).catch(() => {}); await page.waitForTimeout(150); await addTokens(page); }
      return true;
    }
    if (tag === 'INPUT') {
      const type = await loc.evaluate(el => el.type);
      if (type === 'range') { await loc.evaluate(el => { el.value = el.min || 0; el.dispatchEvent(new Event('input', { bubbles: true })); el.value = el.max || 100; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }); return true; }
    }
    await loc.click({ timeout: 2500, force: true });
  } catch (e) {
    try { await loc.evaluate(el => el.click()); } catch (e2) { return false; }
  }
  await page.waitForTimeout(450);
  return true;
}

async function fillInputs(page) {
  // Text and number fields: an invalid value, then a valid one, to reach validation states.
  const inputs = page.locator('input[type=text]:visible, input[type=search]:visible, input:not([type]):visible, input[inputmode]:visible, input[type=number]:visible, input[type=email]:visible, textarea:visible');
  const count = Math.min(await inputs.count(), 8);
  for (let i = 0; i < count; i++) {
    const input = inputs.nth(i);
    for (const value of ['zzzz', '1', '1000000', '2.500,00']) {
      try { await input.fill(value, { timeout: 1000 }); await input.dispatchEvent('change'); await input.press('Enter').catch(() => {}); } catch (e) { break; }
      await page.waitForTimeout(150);
      await addTokens(page);
    }
  }
}

async function openRoute(page, hash) {
  await page.goto('about:blank');
  await page.goto(BASE + hash, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(700);
}

async function crawlScope(page, hash, scopeSelector, depth, budget) {
  // Click controls inside an open dialog/dropdown, one level deeper (wizards, confirmations).
  const list = await candidates(page, scopeSelector);
  let clicks = 0;
  for (const cand of list.slice(0, 18)) {
    if (budget.left-- <= 0) return;
    const ok = await clickCandidate(page, cand);
    if (!ok) continue;
    clicks++;
    await addTokens(page);
    if (depth < 3) {
      const scope = await openScope(page);
      if (scope && scope !== scopeSelector) await crawlScope(page, hash, scope, depth + 1, budget);
    }
  }
  return clicks;
}

async function openScope(page) {
  return page.evaluate(() => {
    if (document.querySelector('dialog[open]')) return 'dialog[open]';
    if (document.querySelector('.modal.show')) return '.modal.show';
    if (document.querySelector('.dropdown-menu.show')) return '.dropdown-menu.show';
    if (document.querySelector('.offcanvas.show')) return '.offcanvas.show';
    return null;
  }).catch(() => null);
}

(async () => {
  const browser = await chromium.launch();
  const opts = device === 'mob' ? { ...devices['iPhone 13'] } : { viewport: { width: 1440, height: 900 } };
  const ctx = await browser.newContext({ ...opts, acceptDownloads: false });
  await ctx.addInitScript(t => { try { localStorage.setItem('bxm-modern-responsive-theme-v1', t); } catch (e) {} }, theme);
  let page = null;
  const mainPages = new Set();
  ctx.on('page', p => { setTimeout(() => { if (!mainPages.has(p)) p.close().catch(() => {}); }, 50); });
  page = await ctx.newPage();
  mainPages.add(page);
  page.on('dialog', d => d.dismiss().catch(() => {}));
  page.on('pageerror', e => log.push('pageerror ' + String(e).slice(0, 200)));
  await page.goto(BASE + '#/overview', { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(1500);
  const baselineStyles = await styleCount(page);
  const started = Date.now();
  for (const hash of routes) {
    try {
      // A fresh document per route keeps one route's clicks from leaking state into the next.
      await page.goto('about:blank');
      await page.goto(BASE + hash, { waitUntil: 'load', timeout: 60000 });
      await page.waitForTimeout(900);
      await addTokens(page);
      await snapshot(page, hash);
      const shellStates = hash === '#/overview' ? [['#bxm-user-dropdown > a', 'user-menu'], ['#bxm-notification-dropdown > a', 'notif-menu'], ['.mobile-menu-toggle', 'mobile-menu'], ['.bxm-compact-toggle', 'compact']] : [];
      for (const [sel, name] of shellStates) {
        if (await page.locator(sel).count()) {
          await page.locator(sel).first().evaluate(el => el.click()).catch(() => {});
          await page.waitForTimeout(500);
          await addTokens(page);
          await snapshot(page, hash + '-' + name);
          await closeEverything(page);
          if (name === 'compact') { await page.locator(sel).first().evaluate(el => el.click()).catch(() => {}); await page.waitForTimeout(300); }
        }
      }
      if (process.env.NO_DEEP || !deepCrawl.has(hash)) continue;
      const clicked = new Set();
      const budget = { left: MAX_CLICKS };
      let rounds = 0;
      while (budget.left > 0 && rounds < 6) {
        rounds++;
        const list = (await candidates(page, null)).filter(c => !clicked.has(c.sig));
        if (!list.length) break;
        let navigated = false;
        for (const cand of list) {
          if (budget.left-- <= 0) break;
          clicked.add(cand.sig);
          const before = page.url();
          const ok = await clickCandidate(page, cand);
          if (!ok) continue;
          await addTokens(page);
          const scope = await openScope(page);
          if (scope) {
            if (scope !== '.dropdown-menu.show') await snapshot(page, hash + '-' + cand.sig.slice(0, 40));
            await crawlScope(page, hash, scope, 1, budget);
            await closeEverything(page);
          }
          if (page.url() !== before) {
            await addTokens(page);
            await openRoute(page, hash);
            navigated = true;
            break; // the view re-rendered: enumerate again, skipping what was clicked
          }
        }
        if (!navigated) break;
      }
      await fillInputs(page);
      const styles = await styleCount(page);
      if (styles !== baselineStyles) log.push(`styles changed on ${hash}: ${styles}`);
    } catch (e) {
      log.push('route ' + hash + ' ' + String(e).slice(0, 300));
      try { await page.close(); } catch (e2) {}
      page = await ctx.newPage();
      mainPages.add(page);
      page.on('dialog', d => d.dismiss().catch(() => {}));
    }
    process.stdout.write(`${contextName} ${hash} tokens=${tokens.size} t=${Math.round((Date.now() - started) / 1000)}s\n`);
  }
  fs.writeFileSync(path.join(outDir, `tokens-${contextName}.json`), JSON.stringify([...tokens].sort()));
  fs.writeFileSync(path.join(outDir, `log-${contextName}.txt`), log.join('\n'));
  await browser.close();
})();
