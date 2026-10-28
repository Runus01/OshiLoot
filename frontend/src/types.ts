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

export interface MerchResponse {
  anime_id: number;
  country: string;
  stores: StoreResult[];
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
