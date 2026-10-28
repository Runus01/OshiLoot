// Browser storage can be unavailable (private mode, blocked site data), so every call is guarded.

const COUNTRY_KEY = "oshiloot.country";
const USERNAME_KEY = "oshiloot.username";

function read(storage: () => Storage, key: string): string | null {
  try {
    return storage().getItem(key);
  } catch {
    return null;
  }
}

function write(storage: () => Storage, key: string, value: string): void {
  try {
    storage().setItem(key, value);
  } catch {
    // not fatal: the app still works, it just won't remember
  }
}

const local = () => window.localStorage;
const session = () => window.sessionStorage;

export const savedCountry = () => read(local, COUNTRY_KEY);
export const saveCountry = (code: string) => write(local, COUNTRY_KEY, code);

export const savedUsername = () => read(local, USERNAME_KEY);
export const saveUsername = (name: string) => write(local, USERNAME_KEY, name);

// MyAnimeList's terms keep users' list data off our server, so the list lives in the
// browser only, and only for this tab session.
export function cachedList<T>(username: string, status: string): T | null {
  const raw = read(session, `oshiloot.list.${username.toLowerCase()}.${status}`);
  try {
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function cacheList(username: string, status: string, value: unknown): void {
  write(session, `oshiloot.list.${username.toLowerCase()}.${status}`, JSON.stringify(value));
}

/** "en-SG" → "SG". */
export function countryFromLocale(locale: string | undefined): string | null {
  const region = locale?.split("-").at(-1);
  return region && /^[A-Z]{2}$/.test(region) ? region : null;
}
