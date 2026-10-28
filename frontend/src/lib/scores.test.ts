import { describe, expect, it } from "vitest";
import type { ListEntry } from "../types";
import { groupByScore } from "./scores";

const entry = (id: number, score: number, en: string | null, main = `Main ${id}`): ListEntry => ({
  anime: {
    id,
    titles: { main, en, ja: null, synonyms: [] },
    picture: null,
    mean_score: null,
    media_type: "tv",
  },
  status: "completed",
  score,
});

describe("groupByScore", () => {
  it("puts 10 first, counts down, and leaves unscored entries last", () => {
    const groups = groupByScore([entry(1, 7, "A"), entry(2, 0, "B"), entry(3, 10, "C"), entry(4, 7, "D")]);
    expect(groups.map((g) => g.score)).toEqual([10, 7, 0]);
    expect(groups[1].entries.map((e) => e.anime.id)).toEqual([1, 4]);
  });

  it("sorts within a score by English title, falling back to the main title", () => {
    const groups = groupByScore([entry(1, 9, null, "Zzz"), entry(2, 9, "Frieren"), entry(3, 9, null, "Bocchi")]);
    expect(groups[0].entries.map((e) => e.anime.id)).toEqual([3, 2, 1]);
  });

  it("treats out-of-range scores as unscored", () => {
    expect(groupByScore([entry(1, 11, "A"), entry(2, -1, "B")]).map((g) => g.score)).toEqual([0]);
  });

  it("returns nothing for an empty list", () => {
    expect(groupByScore([])).toEqual([]);
  });
});
