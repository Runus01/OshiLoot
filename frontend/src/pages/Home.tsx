import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { api, ApiError, SIGN_IN_URL, SIGN_OUT_URL } from "../api";
import { AnimeRow } from "../components/AnimeRow";
import { Cover } from "../components/Cover";
import { groupByScore } from "../lib/scores";
import { cachedList, cacheList, forgetLists, forgetUsername, saveUsername, savedUsername } from "../lib/storage";
import { seasonLabel } from "../lib/text";
import type { Anime, ListEntry, ListStatus, SeasonalAnime, SignInStatus } from "../types";

type Lists = Record<ListStatus, ListEntry[]>;

const TABS: { status: ListStatus; label: string }[] = [
  { status: "completed", label: "Completed" },
  { status: "watching", label: "Watching" },
];

// Set by the backend when MyAnimeList sends the user back (/?signin=...).
const SIGN_IN_NOTICES: Record<string, string> = {
  cancelled: "Sign-in cancelled. You can still load a public list by username.",
  failed: "Signing in with MyAnimeList didn't work. Try again, or load a public list by username.",
  out: "Signed out of MyAnimeList.",
};

// Signed-in lists are cached under a key no MAL username can have ("@" isn't allowed).
const myCacheKey = (username: string) => `@me-${username}`;

/**
 * Top to bottom: search, a short intro with the two ways to load a list, the loaded list,
 * then rows of anime to browse. The intro stays compact so the first row shows without
 * scrolling, on a laptop and on a phone.
 */
export function Home() {
  const [params, setParams] = useSearchParams();
  const [account, setAccount] = useState<SignInStatus | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [username, setUsername] = useState(savedUsername() ?? "");
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [cacheKey, setCacheKey] = useState<string | null>(null);
  const [lists, setLists] = useState<Lists | null>(null);
  const [tab, setTab] = useState<ListStatus>("completed");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (key: string, label: string, fetchLists: () => Promise<Lists>) => {
    setError(null);
    const cached = {
      completed: cachedList<ListEntry[]>(key, "completed"),
      watching: cachedList<ListEntry[]>(key, "watching"),
    };
    if (cached.completed && cached.watching) {
      setLists(cached as Lists);
      setLoadedFor(label);
      setCacheKey(key);
      return;
    }
    setLoading(true);
    try {
      const fresh = await fetchLists();
      cacheList(key, "completed", fresh.completed);
      cacheList(key, "watching", fresh.watching);
      setLists(fresh);
      setLoadedFor(label);
      setCacheKey(key);
    } catch (err) {
      setLists(null);
      setError(err instanceof ApiError ? err.message : "Something went wrong loading your list.");
      if (err instanceof ApiError && err.status === 401) {
        setAccount((current) => current && { ...current, signed_in: false, username: null });
      }
    } finally {
      setLoading(false);
    }
  };

  const loadPublicList = (name: string) => {
    const cleaned = name.trim();
    if (!cleaned) return;
    void load(cleaned, cleaned, async () => {
      const [completed, watching] = await Promise.all([
        api.userList(cleaned, "completed"),
        api.userList(cleaned, "watching"),
      ]);
      saveUsername(cleaned);
      return { completed, watching };
    });
  };

  const loadMyList = (status: SignInStatus) => {
    if (!status.username) return;
    void load(myCacheKey(status.username), status.username, async () => {
      // One request for both lists, so an expired token is refreshed only once.
      const mine = await api.myLists();
      return { completed: mine.completed, watching: mine.watching };
    });
  };

  /** Puts the page back as it was before a list was loaded, ready for another username. */
  const clearList = () => {
    if (cacheKey) forgetLists(cacheKey);
    if (!account?.signed_in) {
      forgetUsername();
      setUsername("");
    }
    setLists(null);
    setLoadedFor(null);
    setCacheKey(null);
    setError(null);
    setTab("completed");
  };

  useEffect(() => {
    const result = params.get("signin");
    if (result) {
      setNotice(SIGN_IN_NOTICES[result] ?? null);
      setParams({}, { replace: true });
    }
    api
      .signInStatus()
      .then((status) => {
        setAccount(status);
        if (status.signed_in && status.username) {
          loadMyList(status); // from this tab's cache when it has one, otherwise from MAL
          return;
        }
        // Returning visitors see their public list straight away (this tab's session cache).
        const name = savedUsername();
        if (name && cachedList(name, "completed") && cachedList(name, "watching")) {
          loadPublicList(name);
        }
      })
      .catch(() => setAccount({ available: false, signed_in: false, username: null }));
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    loadPublicList(username);
  };

  const signedIn = account?.signed_in && account.username ? account : null;

  return (
    <>
      <Search />

      <section className="hero" aria-labelledby="hero-title">
        <h1 className="headline" id="hero-title">
          Find treasures for your oshi!
        </h1>
        <p className="lede">Anime merch that ships to you, lined up by your MyAnimeList scores.</p>
        {notice && (
          <p className="hint" role="status">
            {notice}
          </p>
        )}

        {signedIn ? (
          <div className="list-actions">
            <p className="signed-in">
              Signed in to MyAnimeList as <strong>{signedIn.username}</strong>.{" "}
              {/* A normal navigation: the backend clears the cookie and redirects home. */}
              <a href={SIGN_OUT_URL} onClick={() => forgetLists(myCacheKey(signedIn.username!))}>
                Sign{" "}out
              </a>
            </p>
            {!lists && (
              <button className="button" type="button" onClick={() => loadMyList(signedIn)} disabled={loading}>
                {loading ? "Loading list…" : "Load my list"}
              </button>
            )}
          </div>
        ) : (
          <div className="list-actions">
            <form className="username-form" onSubmit={submit}>
              <label htmlFor="username" className="visually-hidden">
                MyAnimeList username
              </label>
              <input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                spellCheck={false}
                placeholder="MyAnimeList username"
                pattern="[A-Za-z0-9_\-]{2,16}"
                title="2–16 letters, numbers, underscores or hyphens"
                required
              />
              <button className="button" type="submit" disabled={loading}>
                {loading ? "Loading…" : "Load my list"}
              </button>
            </form>
            {account?.available && (
              <>
                <span className="list-or" aria-hidden="true">
                  or
                </span>
                <form action={SIGN_IN_URL} method="get">
                  <button className="button-mal" type="submit">
                    Sign in with MyAnimeList
                  </button>
                </form>
              </>
            )}
          </div>
        )}
        <p className="hint">
          {signedIn ? (
            "Your sign-in stays in this browser, not on our server."
          ) : (
            <>
              <span className="hint-long">Private list? Sign in with MyAnimeList instead. </span>
              Nothing is saved on our server.
            </>
          )}
        </p>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </section>

      {lists && loadedFor && (
        <section className="list" aria-label={`${loadedFor}'s anime list`}>
          <div className="list-head">
            <p className="list-owner">
              <strong>{loadedFor}</strong>'s list
            </p>
            <button type="button" className="button-small" onClick={clearList}>
              Clear list
            </button>
          </div>
          <div className="tabs" role="tablist">
            {TABS.map(({ status, label }) => (
              <button
                key={status}
                role="tab"
                type="button"
                aria-selected={tab === status}
                className="tab"
                onClick={() => setTab(status)}
              >
                {label} <span className="tab-count">{lists[status].length}</span>
              </button>
            ))}
          </div>
          <Shelves entries={lists[tab]} status={tab} />
        </section>
      )}

      <Browse />
    </>
  );
}

function Shelves({ entries, status }: { entries: ListEntry[]; status: ListStatus }) {
  if (entries.length === 0) {
    return (
      <p className="empty-note">
        Nothing marked as {status} on this list yet. Try the other tab, or search at the top.
      </p>
    );
  }
  return (
    <div role="tabpanel">
      {groupByScore(entries).map(({ score, entries: group }) => (
        <section key={score} className="shelf" aria-labelledby={`shelf-${score}`}>
          <div className="shelf-score">
            <span className="score-numeral" id={`shelf-${score}`} aria-label={score ? `Scored ${score}` : "Not scored"}>
              {score || "–"}
            </span>
            <span className="score-caption">
              {score ? `${group.length} anime` : `Not scored, ${group.length}`}
            </span>
          </div>
          <ul className="shelf-row">
            {group.map((entry) => (
              <li key={entry.anime.id}>
                <Cover anime={entry.anime} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

/** Search any anime: a slim bar at the top of the page, with results right under it. */
function Search() {
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState("");
  const [results, setResults] = useState<Anime[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const term = query.trim();
    setError(null);
    setLoading(true);
    try {
      setResults(await api.search(term));
      setSearched(term);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setQuery("");
    setSearched("");
    setResults(null);
    setError(null);
  };

  return (
    <section className="search" aria-label="Search any anime">
      <form className="search-bar" onSubmit={submit} role="search">
        <label htmlFor="search-input" className="visually-hidden">
          Search any anime
        </label>
        <input
          id="search-input"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search any anime"
          minLength={3}
          required
        />
        <button className="button" type="submit" disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {results && (
        <div className="search-results">
          <div className="list-head">
            <p className="list-owner">
              {results.length === 0 ? "No anime matched " : "Results for "}
              <strong>“{searched}”</strong>
              {results.length === 0 && ". Try the Japanese or romaji title."}
            </p>
            <button type="button" className="button-small" onClick={clear}>
              Clear search
            </button>
          </div>
          {results.length > 0 && (
            <ul className="result-grid">
              {results.map((anime) => (
                <li key={anime.id}>
                  <Cover anime={anime} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

type Row = "season" | "topRated" | "popular";

const scoreLine = (anime: Anime) => (anime.mean_score ? `Score ${anime.mean_score.toFixed(2)}` : null);

/** This season's new anime and the all-time favourites, for browsing without a search. */
function Browse() {
  const [season, setSeason] = useState<SeasonalAnime | null>(null);
  const [topRated, setTopRated] = useState<Anime[] | null>(null);
  const [popular, setPopular] = useState<Anime[] | null>(null);
  const [failed, setFailed] = useState<Record<Row, boolean>>({
    season: false,
    topRated: false,
    popular: false,
  });

  useEffect(() => {
    const controller = new AbortController();
    // These rows are extras: if one doesn't load, it's left out rather than shown as an error.
    const leaveOut = (row: Row) => (err: Error) => {
      if (err.name !== "AbortError") setFailed((current) => ({ ...current, [row]: true }));
    };
    api.seasonal(controller.signal).then(setSeason).catch(leaveOut("season"));
    api.topRated(controller.signal).then(setTopRated).catch(leaveOut("topRated"));
    api.popular(controller.signal).then(setPopular).catch(leaveOut("popular"));
    return () => controller.abort();
  }, []);

  return (
    <>
      {!failed.season && season?.anime.length !== 0 && (
        <AnimeRow
          id="browse-season"
          title="New this season"
          note={season ? `${seasonLabel(season.season, season.year)}, most followed first` : "Loading…"}
          anime={season?.anime ?? null}
        />
      )}
      {!failed.topRated && topRated?.length !== 0 && (
        <AnimeRow
          id="browse-top-rated"
          title="Top rated"
          note="All time, by MyAnimeList score"
          anime={topRated}
          detail={scoreLine}
        />
      )}
      {!failed.popular && popular?.length !== 0 && (
        <AnimeRow
          id="browse-popular"
          title="Most popular"
          note="All time, by MyAnimeList members"
          anime={popular}
        />
      )}
    </>
  );
}
