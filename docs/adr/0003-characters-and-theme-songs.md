# 3. Characters from AniList, theme songs from MyAnimeList and Apple

Status: accepted, October 2026

## Context

OshiLoot lets people pick their *oshi*, their favourite character, and see merch of that
character, and it lists each anime's opening and ending songs with a preview and places to
buy them. Neither fits the existing data source:

- MyAnimeList's official API has no characters. It does return theme songs, through the
  undocumented `opening_themes` and `ending_themes` fields, but only as one line of text
  each (`#1: "Yuusha (勇者)" by YOASOBI (eps 1-16)`).
- No anime database has song previews or prices.
- The site is meant to earn affiliate commission, so every source must allow commercial use.

## Decision

- **Characters come from AniList's GraphQL API**, looked up by MyAnimeList ID, which AniList
  stores for each anime. It's free for commercial use under US$150 revenue a month. Jikan,
  the alternative, copies MyAnimeList's website, which MAL's API agreement doesn't cover.
  It lives in the anime module as a `CharacterSource` beside the MAL `AnimeSource`.
- **Theme songs come from MyAnimeList** and are parsed into title, native title, artist and
  episodes (`app/anime/themes.py`). Lines that don't fit keep their full text.
- **Previews and digital purchases come from Apple's iTunes Search API**, in the user's own
  country store, in a new `music` module. Apple's terms shape the song page: the preview
  sits beside Apple's badge with a "courtesy of iTunes" credit, is streamed rather than
  stored, and appears only on the page that sells the song. Apple picks the 30 seconds, so
  it's often but not always the chorus.
- **Previews play on hover in the anime's song list.** Each song is looked up in Apple's
  store only when someone first hovers over it or presses its play button, not when the page
  opens, which keeps a page of eight songs from spending eight of Apple's twenty searches a
  minute. Once found, the row shows Apple's badge beside the song, as Apple's terms require.
  Browsers allow sound only after a click on the page, so a page opened straight from a link
  says to click once; a page reached from the user's list is already allowed.
- **CDs and vinyl are search links** (CDJapan, Tower Records Japan), as neither has a
  public search API.
- **A character's merch is sorted by the listing titles.** The browser sends the cast, and
  the merch module checks which other cast members each listing names: none means a solo
  item, any means a group item. Names that the anime's title contains, or that several
  characters share (the Forger family), are ignored, because they can't tell characters apart.

## Consequences

- AniList allows 30 requests a minute and Apple about 20, both per server. Character pages
  and song lookups are cached for a day; a rate-limited answer is never cached, and the page
  says to try again in a minute rather than failing.
- Above US$150 a month in revenue, AniList needs a commercial licence. That's a business
  task to do before it's needed, not a code change.
- Sorting by listing titles is a heuristic: a listing that doesn't name everyone on the
  item lands in the solo group. Only stores with a search API (eBay today) return listings
  to sort; link-out stores search for "anime + character" instead.
- The `music` module only imports `app.core`, so import-linter keeps it as independent as
  the other four.
