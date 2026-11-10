// IP of Webby-Soft SRL.
// U33-DEC-31: every text of the investor area has a Swiss Standard German entry. The texts are the
// literal first arguments of t("..."), read with the TypeScript parser (nothing is executed). The
// public site (src/site) and the admin console stay English for now and are not checked.
import fs from "node:fs";
import path from "node:path";

import ts from "typescript";
import { describe, expect, it } from "vitest";

import design from "./locales/de-CH.design.json";
import drafts from "./locales/de-CH.drafts.json";

const SRC = path.resolve(__dirname, "..");
const INVESTOR_AREA = ["portal", "investorPortal", "i18n", "App.tsx"];

function sourceFiles(entry: string): string[] {
  const full = path.join(SRC, entry);
  if (fs.statSync(full).isFile()) return [full];
  return fs.readdirSync(full, { withFileTypes: true }).flatMap((item) => {
    const child = path.join(entry, item.name);
    if (item.isDirectory()) return item.name === "generated" ? [] : sourceFiles(child);
    return /\.tsx?$/.test(item.name) && !/\.test\.tsx?$/.test(item.name) && !/\.d\.ts$/.test(item.name) ? [path.join(SRC, child)] : [];
  });
}

function messageKeys(): Map<string, string> {
  const keys = new Map<string, string>();
  for (const file of INVESTOR_AREA.flatMap(sourceFiles)) {
    const source = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
    const visit = (node: ts.Node) => {
      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === "t") {
        const [first] = node.arguments;
        if (first && (ts.isStringLiteral(first) || ts.isNoSubstitutionTemplateLiteral(first)) && !keys.has(first.text)) {
          keys.set(first.text, path.relative(SRC, file));
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
  return keys;
}

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();

describe("de-CH catalog", () => {
  const catalog: Record<string, string> = { ...design, ...drafts };

  it("has a German text for every t() text of the investor area", () => {
    const missing = [...messageKeys()].filter(([key]) => !(key in catalog)).map(([key, file]) => `${file}: ${key}`);
    expect(missing).toEqual([]);
  });

  it("keeps the placeholders, uses no ß and keeps the two sources apart", () => {
    const wrong = Object.entries(catalog).filter(([key, value]) => placeholders(key).join() !== placeholders(value).join() || value.includes("ß") || !value.trim());
    expect(wrong).toEqual([]);
    expect(Object.keys(design).filter((key) => key in drafts)).toEqual([]);
  });
});
