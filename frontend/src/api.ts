import type {
  Anime,
  CountriesResponse,
  FxRates,
  ListEntry,
  ListStatus,
  MerchResponse,
} from "./types";

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

export const api = {
  userList: (username: string, status: ListStatus, signal?: AbortSignal) =>
    getJson<ListEntry[]>(
      `/api/anime/users/${encodeURIComponent(username)}/list?status=${status}`,
      signal,
    ),

  search: (query: string, signal?: AbortSignal) =>
    getJson<Anime[]>(`/api/anime/search?q=${encodeURIComponent(query)}`, signal),

  anime: (id: number, signal?: AbortSignal) => getJson<Anime>(`/api/anime/${id}`, signal),

  merch: (anime: Anime, country: string, signal?: AbortSignal) => {
    const params = new URLSearchParams({
      anime_id: String(anime.id),
      title: anime.titles.main,
      country,
    });
    if (anime.titles.en) params.set("title_en", anime.titles.en);
    if (anime.titles.ja) params.set("title_ja", anime.titles.ja);
    return getJson<MerchResponse>(`/api/merch?${params}`, signal);
  },

  countries: () => getJson<CountriesResponse>("/api/regions/countries"),

  fx: () => getJson<FxRates>("/api/regions/fx"),
};
