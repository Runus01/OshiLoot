import { describePrice, formatMoney } from "../lib/money";
import { countLabel, groupStores } from "../lib/stores";
import { langOf, listNames, type StoreOffer } from "../lib/text";
import type { Country, FxRates, Offer, ShopResult, StoreResult } from "../types";

export function OfferGrid({ items, country, fx }: { items: StoreOffer[]; country: Country; fx: FxRates | null }) {
  if (items.length === 0) return null;
  return (
    <ul className="offer-grid">
      {items.map(({ store, offer }) => (
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
      {offer.others.length > 0 && <span className="offer-with">With {listNames(offer.others)}</span>}
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

/**
 * Each store's own search. Stores OshiLoot can see into show how many listings they have,
 * and are left out when they have none. The rest don't share their stock, so they're listed
 * separately as plain searches.
 */
export function StoreLinks({ stores }: { stores: StoreResult[] }) {
  const { found, searchOnly } = groupStores(stores);
  return (
    <>
      {found.length > 0 && (
        <ul className="store-links">
          {found.map((store) => (
            <StoreLink key={store.store} store={store} />
          ))}
        </ul>
      )}
      {searchOnly.length > 0 && (
        <div className="store-also">
          <h3 className="subheading">{found.length > 0 ? "Also search" : "Search these stores"}</h3>
          <p className="muted">These stores don't share their stock with OshiLoot, so open them to see what they have.</p>
          <ul className="store-links">
            {searchOnly.map((store) => (
              <StoreLink key={store.store} store={store} />
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

function StoreLink({ store }: { store: StoreResult }) {
  if (!store.search_url) return null;
  const count = countLabel(store);
  const problem =
    store.status === "timeout"
      ? `${store.name} didn't answer in time, so its listings are missing. Its own search still works.`
      : store.status === "error"
        ? `${store.name} returned an error, so its listings are missing. Its own search still works.`
        : null;
  return (
    <li>
      <a className="store-link" href={store.search_url} target="_blank" rel="noopener sponsored">
        <span className="store-name">
          {store.name}
          {count && <span className="store-count">{count}</span>}
        </span>
        <span className="store-search">
          {count ? "See them all for " : "Search for "}
          <span lang={langOf(store.search_term)}>{store.search_term}</span>
        </span>
        {problem && <span className="store-problem">{problem}</span>}
        <span className="visually-hidden">(opens {store.name} in a new tab)</span>
      </a>
    </li>
  );
}

/**
 * Said once, above the store sections, when no store OshiLoot can see into has anything.
 */
export function NoListingsNote({ stores, term, country }: { stores: StoreResult[]; term: string; country: Country }) {
  const { found, searchOnly } = groupStores(stores);
  if (found.length > 0) return null;
  return (
    <p className="no-listings" role="status">
      {searchOnly.length > 0
        ? `No live listings found for “${term}” in stores that ship to ${country.name}. The stores below don't share their stock, so search them directly.`
        : `No products found for “${term}” in online stores that ship to ${country.name}.`}
    </p>
  );
}

/** Shops to visit in person in the user's country, with directions to each outlet. */
export function ShopsSection({ shops, country }: { shops: ShopResult[]; country: Country }) {
  if (shops.length === 0) return null;
  return (
    <section className="store-section" aria-labelledby="section-shops">
      <h2 id="section-shops">Shops in {country.name}</h2>
      <p className="muted">Browse in person. Outlets change, so check opening hours before you go.</p>
      <ul className="shop-list">
        {shops.map((shop) => (
          <li key={shop.shop}>
            <ShopCard shop={shop} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function ShopCard({ shop }: { shop: ShopResult }) {
  return (
    <article className="shop">
      <h3 className="shop-name">{shop.name}</h3>
      {shop.note && <p className="shop-note">{shop.note}</p>}
      <ul className="outlets">
        {shop.outlets.map((outlet) => (
          <li key={outlet.name} className="outlet">
            <span className="outlet-name">{outlet.name}</span>
            <span className="outlet-address">{outlet.address}</span>
            <a className="outlet-map" href={outlet.map_url} target="_blank" rel="noopener">
              Directions<span className="visually-hidden"> to {shop.name}, {outlet.name} (opens Google Maps)</span>
            </a>
          </li>
        ))}
      </ul>
      <p className="shop-links">
        {shop.search_url && (
          <a href={shop.search_url} target="_blank" rel="noopener sponsored">
            Search their online shop for <span lang={langOf(shop.search_term)}>{shop.search_term}</span>
          </a>
        )}
        <a href={shop.website} target="_blank" rel="noopener sponsored">
          Website<span className="visually-hidden"> of {shop.name} (opens in a new tab)</span>
        </a>
      </p>
    </article>
  );
}
