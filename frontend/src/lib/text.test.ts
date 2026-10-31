import { describe, expect, it } from "vitest";
import type { Offer, StoreResult, ThemeSong } from "../types";
import { listNames, looksJapanese, roleLabel, seasonLabel, splitByCompany, themeLabel } from "./text";

const theme = (kind: ThemeSong["kind"], number: string | null): ThemeSong => ({
  id: 1,
  kind,
  number,
  title: "Yuusha",
  title_native: "勇者",
  artist: "YOASOBI",
  artist_native: null,
  episodes: "eps 1-16",
  text: "",
});

const offer = (title: string, others: string[] = []): Offer => ({
  title,
  url: `/go/${title}`,
  image: null,
  price: null,
  shipping: null,
  condition: null,
  others,
});

describe("themeLabel", () => {
  it("names openings and endings, including specials", () => {
    expect(themeLabel(theme("opening", "1"))).toBe("Opening 1");
    expect(themeLabel(theme("ending", "S1"))).toBe("Ending S1");
    expect(themeLabel(theme("ending", null))).toBe("Ending");
  });
});

describe("splitByCompany", () => {
  it("separates solo items from group items", () => {
    const store: StoreResult = {
      store: "ebay",
      name: "eBay",
      kind: "second_hand",
      status: "ok",
      search_url: null,
      search_term: "Frieren Fern",
      affiliate: false,
      offers: [offer("Fern stand"), offer("Fern and Stark poster", ["Stark"])],
    };
    const { solo, group } = splitByCompany([store]);
    expect(solo.map((o) => o.offer.title)).toEqual(["Fern stand"]);
    expect(group.map((o) => o.offer.title)).toEqual(["Fern and Stark poster"]);
  });
});

describe("text helpers", () => {
  it("joins names like a sentence", () => {
    expect(listNames(["Stark"])).toBe("Stark");
    expect(listNames(["Stark", "Himmel"])).toBe("Stark and Himmel");
    expect(listNames(["Stark", "Himmel", "Eisen"])).toBe("Stark, Himmel and Eisen");
  });

  it("spots Japanese text and labels roles", () => {
    expect(looksJapanese("葬送のフリーレン")).toBe(true);
    expect(looksJapanese("Frieren")).toBe(false);
    expect(roleLabel("supporting")).toBe("Supporting");
    expect(roleLabel(null)).toBeNull();
  });
});

describe("seasonLabel", () => {
  it("capitalises the season and adds the year", () => {
    expect(seasonLabel("fall", 2026)).toBe("Fall 2026");
    expect(seasonLabel("winter", 2027)).toBe("Winter 2027");
  });
});
