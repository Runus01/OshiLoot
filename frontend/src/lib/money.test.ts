import { describe, expect, it } from "vitest";
import type { FxRates } from "../types";
import { convert, describePrice } from "./money";
import { countryFromLocale } from "./storage";

const fx: FxRates = { base: "EUR", date: "2026-10-27", rates: { EUR: 1, JPY: 160, SGD: 1.5, USD: 1.1 } };

describe("convert", () => {
  it("converts through EUR", () => {
    expect(convert({ amount: 4800, currency: "JPY" }, "SGD", fx)).toBeCloseTo(45);
  });

  it("returns the amount unchanged for the same currency, even without rates", () => {
    expect(convert({ amount: 12, currency: "SGD" }, "SGD", null)).toBe(12);
  });

  it("returns null when a currency has no ECB rate", () => {
    expect(convert({ amount: 500, currency: "TWD" }, "SGD", fx)).toBeNull();
  });
});

describe("describePrice", () => {
  it("shows the original price with an approximate local price", () => {
    const { original, converted } = describePrice({ amount: 4800, currency: "JPY" }, "SGD", fx, "en-SG");
    expect(original).toContain("4,800");
    expect(converted).toMatch(/^≈ .*45\.00$/);
  });

  it("skips the conversion when currencies match", () => {
    expect(describePrice({ amount: 20, currency: "USD" }, "USD", fx, "en-US").converted).toBeNull();
  });
});

describe("countryFromLocale", () => {
  it("reads the region from a browser locale", () => {
    expect(countryFromLocale("en-SG")).toBe("SG");
    expect(countryFromLocale("zh-Hant-TW")).toBe("TW");
    expect(countryFromLocale("en")).toBeNull();
    expect(countryFromLocale(undefined)).toBeNull();
  });
});
