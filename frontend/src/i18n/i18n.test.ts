// IP of Webby-Soft SRL.
import { afterEach, describe, expect, it } from "vitest";
import { registerMessages, setLocale, t } from "./index";

describe("message catalog", () => {
  afterEach(() => setLocale("en"));

  it("returns the English text and fills placeholders", () => {
    expect(t("Welcome back, {name}", { name: "Ana" })).toBe("Welcome back, Ana");
    expect(t("Unknown {thing}")).toBe("Unknown {thing}");
  });

  it("uses a registered translation and falls back to English", () => {
    registerMessages("de-CH", { "Available balance": "Verfügbares Guthaben" });
    setLocale("de-CH");
    expect(t("Available balance")).toBe("Verfügbares Guthaben");
    expect(t("Not translated yet")).toBe("Not translated yet");
  });
});
