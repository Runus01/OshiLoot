import type { CharacterRole, Offer, Season, StoreResult, ThemeSong } from "../types";

/** Hiragana, katakana or kanji: mark such text lang="ja" so it renders in a Japanese font. */
export const looksJapanese = (text: string) => /[぀-ヿ㐀-鿿]/.test(text);

export const langOf = (text: string) => (looksJapanese(text) ? "ja" : undefined);

/** "Opening 1", "Ending S1", or just "Opening" when MyAnimeList gives no number. */
export function themeLabel(theme: ThemeSong): string {
  const kind = theme.kind === "opening" ? "Opening" : "Ending";
  return theme.number ? `${kind} ${theme.number}` : kind;
}

/** "Fall 2026": the season names MyAnimeList uses. */
export function seasonLabel(season: Season, year: number): string {
  return `${season[0].toUpperCase()}${season.slice(1)} ${year}`;
}

export function roleLabel(role: CharacterRole | null): string | null {
  if (!role) return null;
  return role[0].toUpperCase() + role.slice(1);
}

export interface StoreOffer {
  store: StoreResult;
  offer: Offer;
}

/** Character pages: items with only this character, and items they share with others. */
export function splitByCompany(stores: StoreResult[]): { solo: StoreOffer[]; group: StoreOffer[] } {
  const all = stores.flatMap((store) => store.offers.map((offer) => ({ store, offer })));
  return {
    solo: all.filter(({ offer }) => offer.others.length === 0),
    group: all.filter(({ offer }) => offer.others.length > 0),
  };
}

/** "Fern", "Fern and Stark", "Fern, Stark and Himmel". */
export function listNames(names: string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}
