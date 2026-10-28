import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { Cover } from "../components/Cover";
import { groupByScore } from "../lib/scores";
import { cachedList, cacheList, saveUsername, savedUsername } from "../lib/storage";
import type { Anime, ListEntry, ListStatus } from "../types";

type Lists = Record<ListStatus, ListEntry[]>;

const TABS: { status: ListStatus; label: string }[] = [
  { status: "completed", label: "Completed" },
  { status: "watching", label: "Watching" },
];

export function Home() {
  const [username, setUsername] = useState(savedUsername() ?? "");
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [lists, setLists] = useState<Lists | null>(null);
  const [tab, setTab] = useState<ListStatus>("completed");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadList = async (name: string) => {
    const cleaned = name.trim();
    if (!cleaned) return;
    setError(null);
    const cached = {
      completed: cachedList<ListEntry[]>(cleaned, "completed"),
      watching: cachedList<ListEntry[]>(cleaned, "watching"),
    };
    if (cached.completed && cached.watching) {
      setLists(cached as Lists);
      setLoadedFor(cleaned);
      return;
    }
    setLoading(true);
    try {
      const [completed, watching] = await Promise.all([
        api.userList(cleaned, "completed"),
        api.userList(cleaned, "watching"),
      ]);
      cacheList(cleaned, "completed", completed);
      cacheList(cleaned, "watching", watching);
      saveUsername(cleaned);
      setLists({ completed, watching });
      setLoadedFor(cleaned);
    } catch (err) {
      setLists(null);
      setError(err instanceof ApiError ? err.message : "Something went wrong loading your list.");
    } finally {
      setLoading(false);
    }
  };

  // Returning visitors see their list straight away (from this tab's session cache).
  useEffect(() => {
    const name = savedUsername();
    if (name && cachedList(name, "completed") && cachedList(name, "watching")) void loadList(name);
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void loadList(username);
  };

  return (
    <>
      <section className="intro">
        <h1 className="headline">Merch for the anime you rated highest.</h1>
        <p className="lede">
          Enter your MyAnimeList username to line up your list by your own scores. Open any
          anime to see official and second-hand merch that ships to you.
        </p>
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
          <p className="hint">Your list must be public. Nothing is saved on our server.</p>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
        </form>
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
