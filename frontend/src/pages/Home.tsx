import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { api, ApiError, SIGN_IN_URL, SIGN_OUT_URL } from "../api";
import { Cover } from "../components/Cover";
import { groupByScore } from "../lib/scores";
import { cachedList, cacheList, forgetLists, saveUsername, savedUsername } from "../lib/storage";
import type { Anime, ListEntry, ListStatus, SignInStatus } from "../types";

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

export function Home() {
  const [params, setParams] = useSearchParams();
  const [account, setAccount] = useState<SignInStatus | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [username, setUsername] = useState(savedUsername() ?? "");
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [lists, setLists] = useState<Lists | null>(null);
  const [tab, setTab] = useState<ListStatus>("completed");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (cacheKey: string, label: string, fetchLists: () => Promise<Lists>) => {
    setError(null);
    const cached = {
      completed: cachedList<ListEntry[]>(cacheKey, "completed"),
      watching: cachedList<ListEntry[]>(cacheKey, "watching"),
    };
    if (cached.completed && cached.watching) {
      setLists(cached as Lists);
      setLoadedFor(label);
      return;
    }
    setLoading(true);
    try {
      const fresh = await fetchLists();
      cacheList(cacheKey, "completed", fresh.completed);
      cacheList(cacheKey, "watching", fresh.watching);
      setLists(fresh);
      setLoadedFor(label);
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

  const errorMessage = error && (
    <p className="error" role="alert">
      {error}
    </p>
  );

  return (
    <>
      <section className="intro">
        <h1 className="headline">Merch for the anime you rated highest.</h1>
        <p className="lede">
          Enter your MyAnimeList username, or sign in if your list is private, to line up your
          anime by your own scores. Open any of them to see official and second-hand merch that
          ships to you.
        </p>
        {notice && (
          <p className="hint" role="status">
            {notice}
          </p>
        )}

        {account?.signed_in && account.username ? (
          <div className="username-form">
            <p>
              Signed in to MyAnimeList as <strong>{account.username}</strong>.{" "}
              {/* A normal navigation: the backend clears the cookie and redirects home. */}
              <a href={SIGN_OUT_URL} onClick={() => forgetLists(myCacheKey(account.username!))}>
                Sign{"\u00a0"}out
              </a>
            </p>
            {!lists && (
              <div className="field-row">
                <button
                  className="button"
                  type="button"
                  onClick={() => loadMyList(account)}
                  disabled={loading}
                >
                  {loading ? "Loading list…" : "Load my list"}
                </button>
              </div>
            )}
            <p className="hint">
              Private lists work too. Your sign-in stays in this browser, not on our server.
            </p>
            {errorMessage}
          </div>
        ) : (
          <>
            <form className="username-form" onSubmit={submit}>
              <label htmlFor="username">MyAnimeList username</label>
              <div className="field-row">
                <input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  spellCheck={false}
                  placeholder="your_username"
                  pattern="[A-Za-z0-9_\-]{2,16}"
                  title="2–16 letters, numbers, underscores or hyphens"
                  required
                />
                <button className="button" type="submit" disabled={loading}>
                  {loading ? "Loading list…" : "Load my list"}
                </button>
              </div>
              <p className="hint">This needs a public list. Nothing is saved on our server.</p>
              {errorMessage}
            </form>
            {account?.available && (
              <form className="username-form" action={SIGN_IN_URL} method="get">
                <p className="hint">List set to private?</p>
                <div>
                  <button className="button-quiet" type="submit">
                    Sign in with MyAnimeList
                  </button>
                </div>
              </form>
            )}
          </>
        )}
      </section>

      {lists && loadedFor && (
        <section className="list" aria-label={`${loadedFor}'s anime list`}>
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

      <Search />
    </>
  );
}

function Shelves({ entries, status }: { entries: ListEntry[]; status: ListStatus }) {
  if (entries.length === 0) {
    return (
      <p className="empty-note">
        Nothing marked as {status} on this list yet. Try the other tab, or search below.
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

function Search() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Anime[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      setResults(await api.search(query.trim()));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="search" aria-labelledby="search-title">
      <h2 id="search-title">Or search any anime</h2>
      <form className="field-row" onSubmit={submit} role="search">
        <label htmlFor="search-input" className="visually-hidden">
          Anime title
        </label>
        <input
          id="search-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Frieren, Bocchi the Rock!, 葬送のフリーレン"
          minLength={3}
          required
        />
        <button className="button-quiet" type="submit" disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {results && results.length === 0 && (
        <p className="empty-note">No anime matched “{query}”. Try the Japanese or romaji title.</p>
      )}
      {results && results.length > 0 && (
        <ul className="result-grid">
          {results.map((anime) => (
            <li key={anime.id}>
              <Cover anime={anime} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
