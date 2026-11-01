import type { StoreResult } from "../types";

/** How many listings a store found, or null when OshiLoot can't see its stock. */
export function listingCount(store: StoreResult): number | null {
  if (!store.live || store.status !== "ok") return null;
  return store.total ?? store.offers.length;
}

/** "37 listings", "10+ listings", "1 listing". */
export function countLabel(store: StoreResult): string | null {
  const count = listingCount(store);
  if (count === null) return null;
  const plus = store.more ? "+" : "";
  return `${count}${plus} ${count === 1 && !plus ? "listing" : "listings"}`;
}

export interface StoreGroups {
  /** Stores OshiLoot can see into that have matches, the most first. */
  found: StoreResult[];
  /** Stores that don't share their stock (or didn't answer): a search link is all we have. */
  searchOnly: StoreResult[];
  /** Stores OshiLoot can see into with no matches. These are left off the page. */
  empty: StoreResult[];
}

export function groupStores(stores: StoreResult[]): StoreGroups {
  const groups: StoreGroups = { found: [], searchOnly: [], empty: [] };
  for (const store of stores) {
    const count = listingCount(store);
    if (count === null) {
      if (store.search_url) groups.searchOnly.push(store);
    } else if (count > 0) {
      groups.found.push(store);
    } else {
      groups.empty.push(store);
    }
  }
  groups.found.sort((a, b) => (listingCount(b) ?? 0) - (listingCount(a) ?? 0));
  return groups;
}
