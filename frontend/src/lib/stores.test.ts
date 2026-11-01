import { describe, expect, it } from "vitest";
import type { StoreResult } from "../types";
import { countLabel, groupStores, listingCount } from "./stores";

function store(id: string, extra: Partial<StoreResult> = {}): StoreResult {
  return {
    store: id,
    name: id,
    kind: "official",
    status: "ok",
    offers: [],
    search_url: `/go/${id}`,
    search_term: "Frieren",
    affiliate: false,
    live: false,
    total: null,
    more: false,
    ...extra,
  };
}

describe("listingCount and countLabel", () => {
  it("counts only stores OshiLoot can see into", () => {
    expect(listingCount(store("amiami"))).toBeNull();
    expect(listingCount(store("ebay", { live: true, total: 137 }))).toBe(137);
    expect(listingCount(store("ebay", { live: true, status: "timeout", total: 3 }))).toBeNull();
  });

  it("labels counts, with + when the store only says 'at least'", () => {
    expect(countLabel(store("ebay", { live: true, total: 1 }))).toBe("1 listing");
    expect(countLabel(store("ebay", { live: true, total: 37 }))).toBe("37 listings");
    expect(countLabel(store("otaku", { live: true, total: 10, more: true }))).toBe("10+ listings");
    expect(countLabel(store("amiami"))).toBeNull();
  });
});

describe("groupStores", () => {
  it("drops live stores with nothing, keeps link-only stores, and sorts by count", () => {
    const groups = groupStores([
      store("amiami"),
      store("otaku", { live: true, total: 0 }),
      store("ebay", { live: true, total: 12 }),
      store("shop", { live: true, total: 40 }),
      store("down", { live: true, status: "error" }),
    ]);
    expect(groups.found.map((s) => s.store)).toEqual(["shop", "ebay"]);
    expect(groups.empty.map((s) => s.store)).toEqual(["otaku"]);
    expect(groups.searchOnly.map((s) => s.store)).toEqual(["amiami", "down"]);
  });
});
