import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import { api, ApiError } from "../api";
import { PauseIcon, PlayIcon } from "../components/Icons";
import { useRegion } from "../context";
import { ITUNES_BADGE } from "../lib/apple";
import { formatMoney } from "../lib/money";
import { displayTitle } from "../lib/scores";
import { langOf, themeLabel } from "../lib/text";
import type { Anime, AppleTrack, DigitalRelease, MusicStore, SongResponse, ThemeSong } from "../types";

const RELEASE_KIND = { single: "Single", ep: "EP", album: "Album" } as const;

interface FromAnimePage {
  anime?: Anime;
  theme?: ThemeSong;
  song?: SongResponse; // already looked up when the song was previewed on the anime page
}

export function SongRoute() {
  const { id, themeId } = useParams();
  return <SongPage key={`${id}-${themeId}`} />;
}

function SongPage() {
  const params = useParams();
  const location = useLocation();
  const { country } = useRegion();
  const animeId = Number(params.id);
  const themeId = Number(params.themeId);
  const state = (location.state as FromAnimePage | null) ?? {};

  const [anime, setAnime] = useState<Anime | null>(state.anime?.id === animeId ? state.anime : null);
  const [theme, setTheme] = useState<ThemeSong | null>(state.theme?.id === themeId ? state.theme : null);
  const [song, setSong] = useState<SongResponse | null>(state.theme?.id === themeId ? (state.song ?? null) : null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (anime && theme) return;
    const controller = new AbortController();
    const { signal } = controller;
    Promise.all([anime ?? api.anime(animeId, signal), theme ? null : api.themes(animeId, signal)])
      .then(([loadedAnime, themes]) => {
        const found = theme ?? [...(themes?.openings ?? []), ...(themes?.endings ?? [])].find((t) => t.id === themeId);
        if (!found) throw new ApiError("This anime has no theme song with that ID.", 404);
        setAnime(loadedAnime);
        setTheme(found);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err instanceof ApiError ? err.message : "Couldn't load this song.");
      });
    return () => controller.abort();
  }, [animeId, themeId]);

  useEffect(() => {
    if (!theme || !country) return;
    if (song?.country === country.code) return; // looked up already, for this country
    const controller = new AbortController();
    setSong(null);
    api
      .song(animeId, theme, country.code, controller.signal)
      .then(setSong)
      .catch((err) => {
        if (err.name !== "AbortError") setError(err instanceof ApiError ? err.message : "Couldn't look up this song.");
      });
    return () => controller.abort();
  }, [animeId, theme, country]);

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
  if (!anime || !theme) return <p className="loading">Loading song…</p>;

  const animeTitle = displayTitle(anime);
  return (
    <article className="song-page">
      <Link to={`/anime/${anime.id}`} state={{ anime }} className="back-link">
        Back to {animeTitle}
      </Link>
      <header className="song-header">
        <p className="kicker">
          {themeLabel(theme)} · {animeTitle}
          {theme.episodes && ` · ${theme.episodes}`}
        </p>
        <h1 className="anime-title" lang={langOf(theme.title)}>
          {theme.title}
        </h1>
        {theme.title_native && (
          <p className="anime-alt" lang="ja">
            {theme.title_native}
          </p>
        )}
        {theme.artist && (
          <p className="song-artist">
            by <span lang={langOf(theme.artist)}>{theme.artist}</span>
            {theme.artist_native && <span lang="ja"> ({theme.artist_native})</span>}
          </p>
        )}
      </header>

      {!country && <p className="loading">Choose your country to see where to buy this song.</p>}
      {country && !song && <p className="loading">Looking for this song in Apple's {country.name} store…</p>}
      {country && song && (
        <>
          <AppleSection song={song} countryName={country.name} />
          <CdSection stores={song.stores} />
        </>
      )}
    </article>
  );
}

function AppleSection({ song, countryName }: { song: SongResponse; countryName: string }) {
  if (song.apple_status !== "ok" || !song.track) {
    const reason =
      song.apple_status === "not_found"
        ? `This song isn't in Apple's ${countryName} store under this name.`
        : "Apple's store didn't answer just now, so there's no preview. Try again in a minute.";
    return (
      <section className="store-section" aria-labelledby="section-digital">
        <h2 id="section-digital">Digital</h2>
        <p className="muted">{reason}</p>
        <p>
          <a href={song.apple_search_url} target="_blank" rel="noopener sponsored">
            Search Apple Music for this song
          </a>
        </p>
      </section>
    );
  }
  return (
    <section className="store-section" aria-labelledby="section-digital">
      <h2 id="section-digital">Listen and download</h2>
      <Preview track={song.track} />
      {song.releases.length > 0 && (
        <>
          <h3 className="subheading">Releases with this song</h3>
          <ul className="release-grid">
            {song.releases.map((release) => (
              <li key={release.url}>
                <ReleaseCard release={release} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function Preview({ track }: { track: AppleTrack }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);

  const toggle = () => {
    const player = audio.current;
    if (!player) return;
    if (player.paused) player.play().catch(() => setPlaying(false));
    else player.pause();
  };

  return (
    <div className="preview">
      {track.artwork ? (
        <img src={track.artwork} alt="" className="preview-art" width={300} height={300} />
      ) : (
        <span className="preview-art offer-blank" aria-hidden="true" />
      )}
      <div className="preview-body">
        <p className="preview-track">
          <span lang={langOf(track.name)}>{track.name}</span>
          <span className="muted">
            {" "}
            · <span lang={langOf(track.album)}>{track.album}</span>
          </span>
        </p>
        {track.preview_url ? (
          <>
            <button type="button" className="preview-button" onClick={toggle} aria-pressed={playing}>
              {playing ? <PauseIcon /> : <PlayIcon />}
              {playing ? "Pause preview" : "Play 30-second preview"}
            </button>
            <span className="preview-progress" aria-hidden="true">
              <span style={{ width: `${progress * 100}%` }} />
            </span>
            {/* Streamed from Apple, never stored: Apple's terms for previews. */}
            <audio
              ref={audio}
              src={track.preview_url}
              preload="none"
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onEnded={() => setProgress(0)}
              onTimeUpdate={(e) => {
                const { currentTime, duration } = e.currentTarget;
                setProgress(duration ? currentTime / duration : 0);
              }}
            />
          </>
        ) : (
          <p className="muted">Apple has no preview for this song.</p>
        )}
        <div className="preview-buy">
          <a href={track.url} target="_blank" rel="noopener sponsored" className="apple-badge">
            <img src={ITUNES_BADGE} alt="Get it on iTunes" width={150} height={50} />
          </a>
          {track.price && (
            <span className="price-tag">Song {formatMoney(track.price.amount, track.price.currency)}</span>
          )}
        </div>
        <p className="credit">Preview courtesy of iTunes. Apple chooses which 30 seconds play.</p>
      </div>
    </div>
  );
}

function ReleaseCard({ release }: { release: DigitalRelease }) {
  return (
    <a className="offer" href={release.url} target="_blank" rel="noopener sponsored">
      {release.artwork ? (
        <img src={release.artwork} alt="" loading="lazy" />
      ) : (
        <span className="offer-blank" aria-hidden="true" />
      )}
      <span className="offer-title" lang={langOf(release.name)}>
        {release.name}
      </span>
      {release.price && (
        <span className="price-tag">{formatMoney(release.price.amount, release.price.currency)}</span>
      )}
      <span className="offer-meta">{RELEASE_KIND[release.kind]} on Apple Music and iTunes</span>
    </a>
  );
}

function CdSection({ stores }: { stores: MusicStore[] }) {
  if (stores.length === 0) return null;
  return (
    <section className="store-section" aria-labelledby="section-cds">
      <h2 id="section-cds">CDs and vinyl</h2>
      <p className="muted">
        The CD single, the albums it's on, and vinyl pressings all show up in these searches. Filter by format on the
        store's page.
      </p>
      <ul className="store-links">
        {stores.map((store) => (
          <li key={store.store}>
            <a className="store-link" href={store.search_url} target="_blank" rel="noopener sponsored">
              <span className="store-name">{store.name}</span>
              <span className="store-search">
                Search for <span lang={langOf(store.search_term)}>{store.search_term}</span>
              </span>
              {store.note && <span className="store-search">{store.note}</span>}
              <span className="visually-hidden">(opens {store.name} in a new tab)</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
