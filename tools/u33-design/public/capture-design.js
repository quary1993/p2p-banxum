// IP of Webby-Soft SRL.
// Captures the U33 public design (EN): rendered DOM after the design JS ran, and full-page
// screenshots, for the desktop edition (1440x900) and the mobile edition (390x844, iPhone 13).
// Usage: node capture-design.js <outDir> [base=http://127.0.0.1:8090]
// Output: <out>/dom/<edition>-<page>.html, <out>/shots/<edition>-<page>.png
// Extra states (menus open, calculator, forms) are captured as <edition>-<page>--<state>.
const { chromium, devices } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT = process.argv[2];
const BASE = process.argv[3] || 'http://127.0.0.1:8090';
const PAGES = ['index', 'about', 'companies', 'originators', 'contact', 'residential', 'manufacturing', 'winery', 'terms', 'privacy', 'risks', 'opportunities'];

const STATES = {
  index: [
    ['lang-open', async (p) => { await p.click('.language-trigger'); }],
    ['business-open', async (p, ed) => {
      if (ed === 'mobile') { await p.click('.mobile-menu-toggle'); await p.waitForTimeout(300); }
      await p.click('.business-menu summary');
    }],
    ['menu-open', async (p, ed) => { if (ed === 'mobile') await p.click('.mobile-menu-toggle'); }],
    ['calc-error', async (p) => { await p.fill('#investment-amount', '5'); }],
    ['faq-second', async (p) => { const s = await p.$$('#faq .faq-item summary'); if (s[1]) await s[1].click(); }],
  ],
  contact: [
    ['topic', async (p) => { const b = await p.$$('[data-topic]'); if (b[0]) await b[0].click(); }],
    ['submitted', async (p) => {
      await p.fill('#contact-name', 'Ana Test').catch(() => {});
      await p.fill('#contact-email', 'ana@example.com').catch(() => {});
      await p.fill('#contact-message', 'Hello').catch(() => {});
      await p.evaluate(() => { const f = document.querySelector('[data-contact-form]'); f.querySelectorAll('input[type=checkbox][required]').forEach((c) => (c.checked = true)); f.requestSubmit(); });
    }],
  ],
  companies: [
    ['submitted', async (p) => { await p.evaluate(() => { const f = document.querySelector('[data-preview-form]'); f.querySelectorAll('input,select,textarea').forEach((el) => { if (el.type === 'checkbox') el.checked = true; else if (el.tagName === 'SELECT') el.selectedIndex = el.options.length - 1; else if (el.type === 'email') el.value = 'a@b.ch'; else el.value = '100000'; }); f.requestSubmit(); }); }],
  ],
};

async function capture(browser, edition, page) {
  const ctx = await browser.newContext(
    edition === 'desktop'
      ? { viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' }
      : { ...devices['iPhone 13'], deviceScaleFactor: 2, reducedMotion: 'reduce' }
  );
  const p = await ctx.newPage();
  const url = `${BASE}/${edition === 'mobile' ? 'mobile/' : ''}${page}.html?lang=en`;
  await p.goto(url, { waitUntil: 'networkidle' });
  await p.waitForTimeout(600);
  const dom = await p.evaluate(() => document.documentElement.outerHTML);
  fs.writeFileSync(path.join(OUT, 'dom', `${edition}-${page}.html`), dom);
  await p.screenshot({ path: path.join(OUT, 'shots', `${edition}-${page}.png`), fullPage: true });
  await p.screenshot({ path: path.join(OUT, 'shots', `${edition}-${page}--top.png`) });
  for (const [state, act] of STATES[page] || []) {
    await p.goto(url, { waitUntil: 'networkidle' });
    await p.waitForTimeout(300);
    try {
      await act(p, edition);
      await p.waitForTimeout(400);
      const sdom = await p.evaluate(() => document.documentElement.outerHTML);
      fs.writeFileSync(path.join(OUT, 'dom', `${edition}-${page}--${state}.html`), sdom);
      await p.screenshot({ path: path.join(OUT, 'shots', `${edition}-${page}--${state}.png`) });
    } catch (error) {
      console.log('state failed', edition, page, state, error.message.split('\n')[0]);
    }
  }
  console.log('captured', edition, page, p.url());
  await ctx.close();
}

(async () => {
  fs.mkdirSync(path.join(OUT, 'dom'), { recursive: true });
  fs.mkdirSync(path.join(OUT, 'shots'), { recursive: true });
  const browser = await chromium.launch();
  const only = process.env.PAGES ? process.env.PAGES.split(',') : PAGES;
  for (const edition of ['desktop', 'mobile']) {
    for (const page of only) await capture(browser, edition, page);
  }
  await browser.close();
})();
