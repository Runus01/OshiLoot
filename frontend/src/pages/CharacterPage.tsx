import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import { api, ApiError } from "../api";
import { OfferGrid, ShopsSection, StoreLinks } from "../components/Offers";
import { useRegion } from "../context";
import { displayTitle } from "../lib/scores";
import { roleLabel, splitByCompany } from "../lib/text";
import type { Anime, Character, MerchResponse } from "../types";

interface FromAnimePage {
  anime?: Anime;
  character?: Character;
  cast?: Character[];
}

/** Remounts per character, so going from one character to another starts clean. */
export function CharacterRoute() {
  const { id, characterId } = useParams();
  return <CharacterPage key={`${id}-${characterId}`} />;
}

function CharacterPage() {
  const params = useParams();
  const location = useLocation();
  const { country, fx } = useRegion();
  const animeId = Number(params.id);
  const characterId = Number(params.characterId);
  const state = (location.state as FromAnimePage | null) ?? {};

  const [anime, setAnime] = useState<Anime | null>(state.anime?.id === animeId ? state.anime : null);
  const [character, setCharacter] = useState<Character | null>(
    state.character?.id === characterId ? state.character : null,
  );
  const [cast, setCast] = useState<Character[] | null>(state.cast ?? null);
  const [merch, setMerch] = useState<MerchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Arriving from a link or a refresh, rather than from the anime page: fetch what's missing.
  useEffect(() => {
    if (anime && character && cast) return;
    const controller = new AbortController();
    const { signal } = controller;
    (async () => {
      const [loadedAnime, page] = await Promise.all([
        anime ?? api.anime(animeId, signal),
        cast ? null : api.characters(animeId, 1, signal),
      ]);
      const members = cast ?? page?.characters ?? [];
      const found =
        character ?? members.find((c) => c.id === characterId) ?? (await api.character(characterId, signal));
      setAnime(loadedAnime);
      setCast(members);
      setCharacter(found);
    })().catch((err) => {
      if (err.name !== "AbortError") setError(err instanceof ApiError ? err.message : "Couldn't load this character.");
    });
    return () => controller.abort();
    // Runs once per character page; the state it reads only fills in what was missing.
  }, [animeId, characterId]);

  useEffect(() => {
    if (!anime || !character || !cast || !country) return;
    const controller = new AbortController();
    setMerch(null);
    api
      .characterMerch(anime, character, cast, country.code, controller.signal)
      .then(setMerch)
      .catch((err) => {
        if (err.name !== "AbortError") setError(err instanceof ApiError ? err.message : "Couldn't load merch.");
      });
    return () => controller.abort();
  }, [anime, character, cast, country]);

  if (error) {
    return (
      <section className="empty">
        <p className="error" role="alert">
          {error}
        </p>
        <Link to={`/anime/${animeId}`}>Back to the anime</Link>
      </section>
    );
  }
  if (!anime || !character) return <p className="loading">Loading character…</p>;

  const animeTitle = displayTitle(anime);
  const role = roleLabel(cast?.find((c) => c.id === character.id)?.role ?? character.role);
  const { solo, group } = merch ? splitByCompany(merch.stores) : { solo: [], group: [] };
  const term = merch?.stores.find((s) => s.kind === "official")?.search_term;
  const stores = merch
    ? [...merch.stores.filter((s) => s.kind === "official"), ...merch.stores.filter((s) => s.kind !== "official")]
    : [];

  return (
    <article className="character-page">
      <Link to={`/anime/${anime.id}`} state={{ anime }} className="back-link">
        Back to {animeTitle}
      </Link>
      <header className="character-header">
        {character.image ? (
          <img src={character.image} alt="" className="character-portrait" width={230} height={345} />
        ) : (
          <span className="character-portrait character-blank" aria-hidden="true" />
        )}
        <div>
          <p className="kicker">{role ? `${role} character in ${animeTitle}` : animeTitle}</p>
          <h1 className="anime-title">{character.name}</h1>
          {character.name_native && (
            <p className="anime-alt" lang="ja">
              {character.name_native}
            </p>
          )}
        </div>
      </header>

      {!country && <p className="loading">Choose your country to see stores that ship to you.</p>}
      {country && !merch && (
        <p className="loading">
          Looking for {character.name} merch that ships to {country.name}…
        </p>
      )}
      {country && merch && (
        <>
          {solo.length > 0 && (
            <section className="store-section" aria-labelledby="section-solo">
              <h2 id="section-solo">Just {character.name}</h2>
              <p className="muted">Listings that name {character.name} and no one else from the cast.</p>
              <OfferGrid items={solo} country={country} fx={fx} />
            </section>
          )}
          {group.length > 0 && (
            <section className="store-section" aria-labelledby="section-group">
              <h2 id="section-group">{character.name} with others</h2>
              <p className="muted">Sets, posters and group goods that include {character.name}.</p>
              <OfferGrid items={group} country={country} fx={fx} />
            </section>
          )}
          <section className="store-section" aria-labelledby="section-search">
            <h2 id="section-search">Search stores for {character.name}</h2>
            <p className="muted">
              {solo.length + group.length === 0
                ? `No live listings to sort right now. Each store below opens its own search${term ? ` for “${term}”` : ""}.`
                : "Each store opens its own search, with more than the live listings above."}
            </p>
            <StoreLinks stores={stores} />
          </section>
          <ShopsSection shops={merch.shops} country={country} />
        </>
      )}
    </article>
  );
}
