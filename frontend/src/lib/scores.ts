import type { ListEntry } from "../types";

export interface ScoreGroup {
  score: number; // 10..1, or 0 for "not scored"
  entries: ListEntry[];
}

/** Group a list by the user's score: 10 first, down to 1, with unscored entries last. */
export function groupByScore(entries: ListEntry[]): ScoreGroup[] {
  const groups = new Map<number, ListEntry[]>();
  for (const entry of entries) {
    const valid = Number.isInteger(entry.score) && entry.score >= 1 && entry.score <= 10;
    const score = valid ? entry.score : 0;
    groups.set(score, [...(groups.get(score) ?? []), entry]);
  }
  const rank = (score: number) => (score === 0 ? -1 : score);
  return [...groups.entries()]
    .sort(([a], [b]) => rank(b) - rank(a))
    .map(([score, group]) => ({
      score,
      entries: group.sort((x, y) => displayTitle(x.anime).localeCompare(displayTitle(y.anime))),
    }));
}

export function displayTitle(anime: { titles: { en: string | null; main: string } }): string {
  return anime.titles.en ?? anime.titles.main;
}
