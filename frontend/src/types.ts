// Mirrors the backend's Pydantic models (see /api/docs when the backend is running).

export type ListStatus = "completed" | "watching";

export interface AnimeTitles {
  main: string;
  en: string | null;
  ja: string | null;
  synonyms: string[];
}

export interface Anime {
  id: number;
  titles: AnimeTitles;
  picture: string | null;
  mean_score: number | null;
  media_type: string | null;
}

export interface ListEntry {
  anime: Anime;
  status: string;
  score: number; // 0 = not scored
}

/** Both lists of the user signed in with MyAnimeList (private lists included). */
export interface MyLists {
  username: string;
  completed: ListEntry[];
  watching: ListEntry[];
}

export interface SignInStatus {
  available: boolean; // sign-in is configured on this server
  signed_in: boolean;
  username: string | null;
}

export interface Money {
  amount: number;
  currency: string;
}

export interface Offer {
  title: string;
  url: string;
  image: string | null;
  price: Money | null;
  shipping: Money | null;
  condition: string | null;
  /** Character searches only: other cast members named in the listing. Empty = solo item. */
  others: string[];
}

export type StoreKind = "official" | "second_hand";
export type StoreStatus = "ok" | "timeout" | "error" | "not_configured";

export interface StoreResult {
  store: string;
  name: string;
  kind: StoreKind;
  status: StoreStatus;
  offers: Offer[];
  search_url: string | null;
  search_term: string;
  affiliate: boolean;
}

export interface Outlet {
  name: string;
  address: string;
  map_url: string;
}

/** A shop to visit in person in the user's country. */
export interface ShopResult {
  shop: string;
  name: string;
  note: string | null;
  website: string;
  search_url: string | null;
  search_term: string;
  outlets: Outlet[];
}

export interface MerchResponse {
  anime_id: number;
  character_id: number | null;
  country: string;
  stores: StoreResult[];
  shops: ShopResult[];
}

export type CharacterRole = "main" | "supporting" | "background";

export interface Character {
  id: number; // AniList character ID
  name: string;
  name_native: string | null;
  alternative: string[];
  image: string | null;
  role: CharacterRole | null;
}

export interface CharacterPage {
  anime_id: number;
  page: number;
  characters: Character[];
  has_next_page: boolean;
}

export type ThemeKind = "opening" | "ending";

export interface ThemeSong {
  id: number; // MyAnimeList theme ID
  kind: ThemeKind;
  number: string | null; // "1", or "S1" for specials
  title: string;
  title_native: string | null;
  artist: string;
  artist_native: string | null;
  episodes: string | null;
  text: string;
}

export interface Themes {
  anime_id: number;
  openings: ThemeSong[];
  endings: ThemeSong[];
}

export type AppleStatus = "ok" | "not_found" | "busy" | "error";

export interface AppleTrack {
  name: string;
  artist: string;
  album: string;
  artwork: string | null;
  preview_url: string | null;
  url: string;
  price: Money | null;
}

export interface DigitalRelease {
  name: string;
  kind: "single" | "ep" | "album";
  url: string;
  artwork: string | null;
  price: Money | null;
}

export interface MusicStore {
  store: string;
  name: string;
  note: string | null;
  search_url: string;
  search_term: string;
  affiliate: boolean;
}

export interface SongResponse {
  country: string;
  apple_status: AppleStatus;
  track: AppleTrack | null;
  releases: DigitalRelease[];
  apple_search_url: string;
  stores: MusicStore[];
}

export interface Country {
  code: string;
  name: string;
  currency: string;
}

export interface CountriesResponse {
  countries: Country[];
  detected: string | null;
}

export interface FxRates {
  base: string;
  date: string;
  rates: Record<string, number>;
}
