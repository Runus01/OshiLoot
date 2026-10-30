import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import { api, ApiError } from "../api";
import { CharacterCard } from "../components/CharacterCard";
import { OfferGrid, ShopsSection, StoreLinks } from "../components/Offers";
import { ThemesSection } from "../components/ThemeSongs";
import { useRegion } from "../context";
import type { Anime, Character, MerchResponse, StoreKind } from "../types";

const SECTIONS: { kind: StoreKind; title: string; note: string }[] = [
  { kind: "official", title: "Official stores", note: "New, licensed merchandise." },
  { kind: "second_hand", title: "Second-hand", note: "Pre-owned and resale listings." },
];

export function AnimePage() {
  const { id } = useParams();
  const location = useLocation();
  const { country, fx } = useRegion();
  const animeId = Number(id);
  const fromList = (location.state as { anime?: Anime } | null)?.anime;

  const [anime, setAnime] = useState<Anime | null>(fromList?.id === animeId ? fromList : null);
  const [merch, setMerch] = useState<MerchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (anime?.id === animeId) return;
    const controller = new AbortController();
    api
      .anime(animeId, controller.signal)
      .then(setAnime)
      .catch((err) => {
        if (err.name !== "AbortError") setError(err instanceof ApiError ? err.message : "Couldn't load this anime.");
      });
    return () => controller.abort();
  }, [animeId, anime]);

  useEffect(() => {
    if (!anime || !country) return;
    const controller = new AbortController();
    setMerch(null);
    api
      .merch(anime, country.code, controller.signal)
      .then(setMerch)
      .catch((err) => {
        if (err.name !== "AbortError") setError(err instanceof ApiError ? err.message : "Couldn't load merch.");
      });
    return () => controller.abort();
  }, [anime, country]);

  if (error) {
    return (
      <section className="empty">
        <p className="error" role="alert">
          {error}
        </p>
        <Link to="/">Back to your list</Link>
      </section>
    );
  }

  if (!anime) return <p className="loading">Loading anime…</p>;

  const { titles } = anime;
  return (
    <article className="anime">
      <Link to="/" className="back-link">
        Back to your list
      </Link>
      <header className="anime-header">
        {anime.picture && <img src={anime.picture} alt="" className="anime-cover" width={225} height={318} />}
        <div>
          <h1 className="anime-title">{titles.en ?? titles.main}</h1>
          {titles.en && titles.en !== titles.main && <p className="anime-alt">{titles.main}</p>}
          {titles.ja && (
            <p className="anime-alt" lang="ja">
              {titles.ja}
            </p>
          )}
          {anime.mean_score && <p className="muted">MyAnimeList average {anime.mean_score.toFixed(2)}</p>}
        </div>
      </header>

      <CharactersSection anime={anime} />

      {!country && <p className="loading">Choose your country to see stores that ship to you.</p>}
      {country && !merch && <p className="loading">Checking stores that ship to {country.name}…</p>}
      {country &&
        merch &&
        SECTIONS.map(({ kind, title, note }) => {
          const stores = merch.stores.filter((s) => s.kind === kind);
          if (stores.length === 0) return null;
          const items = stores.flatMap((store) => store.offers.map((offer) => ({ store, offer })));
          return (
            <section key={kind} className="store-section" aria-labelledby={`section-${kind}`}>
              <h2 id={`section-${kind}`}>{title}</h2>
              <p className="muted">{note}</p>
              <OfferGrid items={items} country={country} fx={fx} />
              <StoreLinks stores={stores} />
            </section>
          );
        })}
      {country && merch && <ShopsSection shops={merch.shops} country={country} />}

      <ThemesSection anime={anime} />
    </article>
  );
}

const STEP = 12; // characters shown at first, and added per "Show more"

function CharactersSection({ anime }: { anime: Anime }) {
  const [characters, setCharacters] = useState<Character[] | null>(null);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [visible, setVisible] = useState(STEP);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setCharacters(null);
    setError(null);
    setPage(1);
    setVisible(STEP);
    api
      .characters(anime.id, 1, controller.signal)
      .then((res) => {
        setCharacters(res.characters);
        setHasNext(res.has_next_page);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err instanceof ApiError ? err.message : "Couldn't load characters.");
      });
    return () => controller.abort();
  }, [anime.id]);

  if (error) {
    return (
      <section className="characters-section" aria-labelledby="section-characters">
        <h2 id="section-characters">Characters</h2>
        <p className="error">{error}</p>
      </section>
    );
  }
  if (characters === null) return <p className="loading">Loading characters…</p>;
  if (characters.length === 0) return null;

  const canShowMore = visible < characters.length || hasNext;
  const showMore = async () => {
    if (visible + STEP <= characters.length || !hasNext) {
      setVisible((v) => v + STEP);
      return;
    }
    setLoadingMore(true);
    try {
      const next = await api.characters(anime.id, page + 1);
      setCharacters([...characters, ...next.characters]);
      setHasNext(next.has_next_page);
      setPage(page + 1);
      setVisible((v) => v + STEP);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load more characters.");
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <section className="characters-section" aria-labelledby="section-characters">
      <h2 id="section-characters">Characters</h2>
      <p className="muted">Pick your oshi to see merch of just them, or of them with the rest of the cast.</p>
      <ul className="character-grid">
        {characters.slice(0, visible).map((character) => (
          <li key={character.id}>
            <CharacterCard anime={anime} character={character} cast={characters} />
          </li>
        ))}
      </ul>
      {canShowMore && (
        <button type="button" className="button-quiet more-button" onClick={showMore} disabled={loadingMore}>
          {loadingMore ? "Loading…" : "Show more characters"}
        </button>
      )}
    </section>
  );
}
