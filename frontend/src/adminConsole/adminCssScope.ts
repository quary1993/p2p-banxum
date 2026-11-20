// IP of Webby-Soft SRL.
// Audit S4-9 (after G-07): the admin stylesheet (src/styles.css) has general class names such as .row,
// .modal and .nav. A browser keeps the stylesheet of a lazy area after the route changes, so these rules
// reached the investor area and the public site when the admin console was opened first in the same tab.
//
// The build (vite.config.ts) puts this scope before every selector of src/styles.css:
//   .row { ... }  ->  :where(html.bxa) .row { ... }
// AdminSkin sets the class "bxa" on <html> only while the admin console is mounted. :where() adds no
// specificity, so the order of the rules inside the admin console does not change.
//
// This file is build code: it has no browser imports, and the application does not import it.

export const ADMIN_SCOPE_CLASS = "bxa";
export const ADMIN_SCOPE = `:where(html.${ADMIN_SCOPE_CLASS})`;

// The small part of the PostCSS rule node that the plugin uses.
type CssRule = {
  selectors: string[];
  parent?: { type: string; name?: string };
  source?: { input: { file?: string } };
};

/** True for src/styles.css (Vite can add a query after the file name). */
export function isAdminStylesheet(file: string | undefined): boolean {
  if (!file) return false;
  return file.replace(/\\/g, "/").split("?")[0].endsWith("/src/styles.css");
}

/** One selector below the admin scope. A selector that is in the scope stays as it is. */
export function scopeSelector(selector: string): string {
  const text = selector.trim();
  if (text.startsWith(ADMIN_SCOPE)) return text;
  if (/^(html|body|:root)(?![\w-])/.test(text)) {
    // A page-level rule cannot be below html.bxa; the build stops so that it cannot leak again.
    throw new Error(
      `src/styles.css: the selector "${text}" styles the page itself. Write it as "html.${ADMIN_SCOPE_CLASS}" in adminConsole/AdminSkin or below a class.`
    );
  }
  return `${ADMIN_SCOPE} ${text}`;
}

/** PostCSS plugin: scopes every rule of the admin stylesheet; other stylesheets are not changed. */
export function scopeAdminStyles() {
  return {
    postcssPlugin: "banxum-scope-admin-styles",
    Rule(rule: CssRule) {
      if (!isAdminStylesheet(rule.source?.input.file)) return;
      // The steps of @keyframes (from, to, 50%) are not selectors.
      if (rule.parent?.type === "atrule" && /keyframes$/.test(rule.parent.name ?? "")) return;
      rule.selectors = rule.selectors.map(scopeSelector);
    }
  };
}
