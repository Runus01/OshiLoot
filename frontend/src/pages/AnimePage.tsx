import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import { api, ApiError } from "../api";
import { useRegion } from "../context";
import { describePrice, formatMoney } from "../lib/money";
import type { Anime, Country, FxRates, MerchResponse, Offer, StoreKind, StoreResult } from "../types";

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

      {!country && <p className="loading">Choose your country to see stores that ship to you.</p>}
      {country && !merch && <p className="loading">Checking stores that ship to {country.name}…</p>}
      {country &&
        merch &&
        SECTIONS.map(({ kind, title, note }) => {
          const stores = merch.stores.filter((s) => s.kind === kind);
          if (stores.length === 0) return null;
          return (
            <section key={kind} className="store-section" aria-labelledby={`section-${kind}`}>
              <h2 id={`section-${kind}`}>{title}</h2>
              <p className="muted">{note}</p>
              <OfferGrid stores={stores} country={country} fx={fx} />
              <ul className="store-links">
                {stores.map((store) => (
                  <StoreLink key={store.store} store={store} />
                ))}
              </ul>
            </section>
          );
        })}
    </article>
  );
}

function OfferGrid({ stores, country, fx }: { stores: StoreResult[]; country: Country; fx: FxRates | null }) {
  const offers = stores.flatMap((store) => store.offers.map((offer) => ({ store, offer })));
  if (offers.length === 0) return null;
  return (
    <ul className="offer-grid">
      {offers.map(({ store, offer }) => (
        <li key={offer.url}>
          <OfferCard offer={offer} storeName={store.name} country={country} fx={fx} />
        </li>
      ))}
    </ul>
  );
}

function OfferCard({
  offer,
  storeName,
  country,
  fx,
}: {
  offer: Offer;
  storeName: string;
  country: Country;
  fx: FxRates | null;
}) {
  const price = offer.price && describePrice(offer.price, country.currency, fx);
  return (
    <a className="offer" href={offer.url} target="_blank" rel="noopener sponsored">
      {offer.image ? <img src={offer.image} alt="" loading="lazy" /> : <span className="offer-blank" aria-hidden="true" />}
      <span className="offer-title">{offer.title}</span>
      {price && (
        <span className="price-tag">
          {price.original}
          {price.converted && <span className="price-converted">{price.converted}</span>}
        </span>
      )}
      <span className="offer-meta">{shippingText(offer, country)}</span>
      <span className="offer-meta">
        {storeName}
        {offer.condition ? `, ${offer.condition.toLowerCase()}` : ""}
      </span>
    </a>
  );
}

function shippingText(offer: Offer, country: Country): string {
  if (!offer.shipping) return `Shipping to ${country.name} shown at checkout`;
  if (offer.shipping.amount === 0) return `Free shipping to ${country.name}`;
  return `${formatMoney(offer.shipping.amount, offer.shipping.currency)} shipping to ${country.name}`;
}

function StoreLink({ store }: { store: StoreResult }) {
  if (!store.search_url) return null;
  const problem =
    store.status === "timeout"
      ? `${store.name} didn't answer in time, so live listings are missing. Its own search still works.`
      : store.status === "error"
        ? `${store.name} returned an error, so live listings are missing. Its own search still works.`
        : null;
  return (
    <li>
      <a className="store-link" href={store.search_url} target="_blank" rel="noopener sponsored">
        <span className="store-name">{store.name}</span>
        <span className="store-search">
          Search for <span lang={/[぀-ヿ一-龯]/.test(store.search_term) ? "ja" : undefined}>{store.search_term}</span>
        </span>
        {problem && <span className="store-problem">{problem}</span>}
        <span className="visually-hidden">(opens {store.name} in a new tab)</span>
      </a>
    </li>
  );
}
