// IP of Webby-Soft SRL.
// Audit S4-9: the admin stylesheet styles nothing outside the admin console. The build scopes every rule
// of src/styles.css to html.bxa, and the admin skin sets that class only while the console is mounted.
import fs from "node:fs";
import path from "node:path";

import { render } from "@testing-library/react";
import postcss from "postcss";
import { describe, expect, test } from "vitest";

import { ADMIN_SCOPE, ADMIN_SCOPE_CLASS, isAdminStylesheet, scopeAdminStyles, scopeSelector } from "./adminCssScope";
import { AdminSkin } from "./AdminSkin";

const STYLESHEET = path.resolve(__dirname, "..", "styles.css");

async function build(css: string, from: string) {
  const result = await postcss([scopeAdminStyles()]).process(css, { from });
  return result.root;
}

describe("admin stylesheet scope", () => {
  test("every rule of styles.css is below the admin scope, and no rule is lost", async () => {
    const source = fs.readFileSync(STYLESHEET, "utf8");
    const before: string[] = [];
    postcss.parse(source).walkRules((rule) => {
      before.push(...rule.selectors);
    });
    const after: string[] = [];
    (await build(source, STYLESHEET)).walkRules((rule) => {
      after.push(...rule.selectors);
    });

    expect(after).toHaveLength(before.length);
    expect(after.filter((selector) => !selector.startsWith(`${ADMIN_SCOPE} `))).toEqual([]);
    // The rule the audit named: .row no longer applies to every page.
    expect(before).toContain(".row");
    expect(after).toContain(`${ADMIN_SCOPE} .row`);
    expect(after).not.toContain(".row");
  });

  test("rules in a media query are scoped; the steps of keyframes are not", async () => {
    const css = "@media (max-width: 600px) { .row, .col { display: block } } @keyframes spin { from { opacity: 0 } to { opacity: 1 } }";
    const text = (await build(css, STYLESHEET)).toString();

    expect(text).toContain(`${ADMIN_SCOPE} .row, ${ADMIN_SCOPE} .col`);
    expect(text).toContain("from { opacity: 0 }");
    expect(text).not.toContain(`${ADMIN_SCOPE} from`);
  });

  test("only the admin stylesheet is changed", async () => {
    const other = path.resolve(__dirname, "..", "portal", "u33", "u33-overrides.css");

    expect((await build(".row { display: flex }", other)).toString()).toBe(".row { display: flex }");
    expect(isAdminStylesheet(`${STYLESHEET}?direct`)).toBe(true);
    expect(isAdminStylesheet(path.resolve(__dirname, "..", "site", "styles.css"))).toBe(false);
    expect(isAdminStylesheet(undefined)).toBe(false);
  });

  test("the scope adds no specificity and is applied one time only", () => {
    expect(ADMIN_SCOPE).toBe(":where(html.bxa)");
    expect(scopeSelector(scopeSelector("table.tbl td.num"))).toBe(":where(html.bxa) table.tbl td.num");
  });

  test.each(["body", "html", ":root", "body.dark .row"])("a page-level rule (%s) stops the build", (selector) => {
    expect(() => scopeSelector(selector)).toThrow(/styles the page itself/);
  });
});

describe("admin skin", () => {
  test("html has the admin class only while the admin console is mounted", () => {
    const html = document.documentElement;
    expect(html.classList.contains(ADMIN_SCOPE_CLASS)).toBe(false);

    const first = render(<AdminSkin><p>console</p></AdminSkin>);
    const second = render(<AdminSkin><p>console</p></AdminSkin>);
    expect(html.classList.contains(ADMIN_SCOPE_CLASS)).toBe(true);

    // One of two mounts leaves (StrictMode, a remount): the class stays.
    first.unmount();
    expect(html.classList.contains(ADMIN_SCOPE_CLASS)).toBe(true);
    // The admin console is gone (a route change to the investor area or the public site).
    second.unmount();
    expect(html.classList.contains(ADMIN_SCOPE_CLASS)).toBe(false);
  });
});
