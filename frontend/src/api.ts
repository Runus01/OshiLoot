import type {
  Anime,
  Character,
  CharacterPage,
  CountriesResponse,
  FxRates,
  ListEntry,
  ListStatus,
  MerchResponse,
  MyLists,
  SeasonalAnime,
  SignInStatus,
  SongResponse,
  ThemeSong,
  Themes,
} from "./types";

// Full-page navigations, not fetches: the backend redirects to MyAnimeList and back.
export const SIGN_IN_URL = "/api/anime/auth/login";
export const SIGN_OUT_URL = "/api/anime/auth/logout";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { signal, headers: { Accept: "application/json" } });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError("Can't reach the server. Check your connection and try again.", 0);
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // keep the generic message
    }
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

function titleParams(anime: Anime, country: string): URLSearchParams {
  const params = new URLSearchParams({
    anime_id: String(anime.id),
    title: anime.titles.main,
    country,
  });
  if (anime.titles.en) params.set("title_en", anime.titles.en);
  if (anime.titles.ja) params.set("title_ja", anime.titles.ja);
  return params;
}

let myListsInFlight: Promise<MyLists> | null = null;

export const api = {
  userList: (username: string, status: ListStatus, signal?: AbortSignal) =>
    getJson<ListEntry[]>(
      `/api/anime/users/${encodeURIComponent(username)}/list?status=${status}`,
      signal,
    ),

  signInStatus: () => getJson<SignInStatus>("/api/anime/auth/me"),

  // Uses the HttpOnly sign-in cookie, which the browser sends automatically (same origin).
  myLists: () => {
    // Share one request between overlapping callers (React StrictMode runs effects twice in
    // development). MAL revokes a refresh token once used, so two parallel refreshes would
    // sign the user out.
    myListsInFlight ??= getJson<MyLists>("/api/anime/me/lists").finally(() => {
      myListsInFlight = null;
    });
    return myListsInFlight;
  },

  search: (query: string, signal?: AbortSignal) =>
    getJson<Anime[]>(`/api/anime/search?q=${encodeURIComponent(query)}`, signal),

  anime: (id: number, signal?: AbortSignal) => getJson<Anime>(`/api/anime/${id}`, signal),

  // The home page rows.
  seasonal: (signal?: AbortSignal) => getJson<SeasonalAnime>("/api/anime/seasonal", signal),
  popular: (signal?: AbortSignal) => getJson<Anime[]>("/api/anime/popular", signal),

  merch: (anime: Anime, country: string, signal?: AbortSignal) =>
    getJson<MerchResponse>(`/api/merch?${titleParams(anime, country)}`, signal),

  characters: (animeId: number, page: number, signal?: AbortSignal) =>
    getJson<CharacterPage>(`/api/anime/${animeId}/characters?page=${page}`, signal),

  character: (characterId: number, signal?: AbortSignal) =>
    getJson<Character>(`/api/anime/characters/${characterId}`, signal),

  /** Merch for one character. The cast lets the server tell solo items from group ones. */
  characterMerch: (
    anime: Anime,
    character: Character,
    cast: Character[],
    country: string,
    signal?: AbortSignal,
  ) => {
    const params = titleParams(anime, country);
    params.set("character_id", String(character.id));
    params.set("character", character.name);
    if (character.name_native) params.set("character_ja", character.name_native);
    for (const member of cast.slice(0, 50)) {
      if (member.id !== character.id) {
        params.append("cast", member.name_native ? `${member.name}|${member.name_native}` : member.name);
      }
    }
    return getJson<MerchResponse>(`/api/merch/character?${params}`, signal);
  },

  themes: (animeId: number, signal?: AbortSignal) =>
    getJson<Themes>(`/api/anime/${animeId}/themes`, signal),

  song: (animeId: number, theme: ThemeSong, country: string, signal?: AbortSignal) => {
    const params = new URLSearchParams({
      anime_id: String(animeId),
      theme_id: String(theme.id),
      title: theme.title,
      artist: theme.artist || theme.artist_native || "Unknown",
      country,
    });
    if (theme.title_native) params.set("title_native", theme.title_native);
    if (theme.artist_native) params.set("artist_native", theme.artist_native);
    return getJson<SongResponse>(`/api/music/song?${params}`, signal);
  },

  countries: () => getJson<CountriesResponse>("/api/regions/countries"),

  fx: () => getJson<FxRates>("/api/regions/fx"),
};
