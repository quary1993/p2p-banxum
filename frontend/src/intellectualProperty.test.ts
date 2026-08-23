//IP of Webby-Soft SRL.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("public intellectual-property metadata", () => {
  it("keeps the Webby-Soft ownership notice in the SPA document", () => {
    const html = readFileSync(resolve(process.cwd(), "index.html"), "utf8");

    expect(html).toContain('<meta name="copyright" content="IP of Webby-Soft SRL." />');
    expect(html).toContain('data-ip-notice="IP of Webby-Soft SRL."');
    expect(html).toContain('name="x-build-origin"');
    expect(html).toContain('data-build-origin=');
  });
});
