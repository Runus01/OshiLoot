import { useCallback, useEffect, useRef, useState, type PointerEvent } from "react";
import { Link } from "react-router";
import { api } from "../api";
import { useRegion } from "../context";
import { ITUNES_BADGE } from "../lib/apple";
import { hoverPreviewsOn, saveHoverPreviews } from "../lib/storage";
import { langOf } from "../lib/text";
import type { Anime, SongResponse, ThemeSong, Themes } from "../types";
import { PauseIcon, PlayIcon } from "./Icons";

const HOVER_DELAY_MS = 180; // a cursor passing over the list shouldn't start every song
const FADE_IN_MS = 250;
const FADE_OUT_MS = 150;

type Lookup = { state: "loading" } | { state: "done"; song: SongResponse | null };

/** The anime page's opening and ending themes, each playable on hover or with its button. */
export function ThemesSection({ anime }: { anime: Anime }) {
  const [themes, setThemes] = useState<Themes | null>(null);
  const [hoverOn, setHoverOn] = useState(hoverPreviewsOn);
  const previews = useSongPreviews(anime.id);

  useEffect(() => {
    const controller = new AbortController();
    setThemes(null);
    api
      .themes(anime.id, controller.signal)
      .then(setThemes)
      .catch(() => setThemes(null)); // theme songs are extra: leave the section out on failure
    return () => controller.abort();
  }, [anime.id]);

  if (!themes || (themes.openings.length === 0 && themes.endings.length === 0)) return null;
  return (
    <section className="themes-section" aria-labelledby="section-themes">
      <h2 id="section-themes">Theme songs</h2>
      <p className="muted">
        Rest your cursor on a song, or press its play button, to hear Apple's 30-second preview. Open a song for
        the CD single, the album and downloads. Previews courtesy of iTunes.
      </p>
      <label className="hover-toggle">
        <input
          type="checkbox"
          checked={hoverOn}
          onChange={(e) => {
            setHoverOn(e.target.checked);
            saveHoverPreviews(e.target.checked);
            if (!e.target.checked) previews.stop();
          }}
        />
        Play previews on hover
      </label>
      <div className="theme-columns">
        <ThemeList anime={anime} title="Opening theme" songs={themes.openings} previews={previews} hoverOn={hoverOn} />
        <ThemeList anime={anime} title="Ending theme" songs={themes.endings} previews={previews} hoverOn={hoverOn} />
      </div>
      {/* Below the lists, so the songs don't move under the cursor when it appears or goes. */}
      {previews.blocked && (
        <p className="hint" role="status">
          Your browser plays sound only after you've clicked on the page. Click anywhere once, then hover again.
        </p>
      )}
    </section>
  );
}

interface ListProps {
  anime: Anime;
  title: string;
  songs: ThemeSong[];
  previews: Previews;
  hoverOn: boolean;
}

function ThemeList({ anime, title, songs, previews, hoverOn }: ListProps) {
  if (songs.length === 0) return null;
  return (
    <div>
      <h3 className="theme-heading">{title}</h3>
      <ol className="theme-list">
        {songs.map((song) => (
          <li key={song.id}>
            <ThemeRow anime={anime} song={song} previews={previews} hoverOn={hoverOn} />
          </li>
        ))}
      </ol>
    </div>
  );
}

function ThemeRow({ anime, song, previews, hoverOn }: { anime: Anime; song: ThemeSong; previews: Previews; hoverOn: boolean }) {
  const timer = useRef<number | undefined>(undefined);
  const lookup = previews.lookups[song.id];
  const found = lookup?.state === "done" ? lookup.song : null;
  const track = found?.apple_status === "ok" ? found.track : null;
  const noPreview = lookup?.state === "done" && !track?.preview_url;
  const isActive = previews.active === song.id;
  const playing = isActive && previews.playing;
  const loading = isActive && !previews.playing;

  // Mouse only: a tap on a phone fires pointerenter too, and should open the song instead.
  const enter = (e: PointerEvent) => {
    if (e.pointerType !== "mouse" || !hoverOn) return;
    timer.current = window.setTimeout(() => previews.play(song), HOVER_DELAY_MS);
  };
  const leave = (e: PointerEvent) => {
    window.clearTimeout(timer.current);
    if (e.pointerType === "mouse") previews.stop(song.id);
  };
  useEffect(() => () => window.clearTimeout(timer.current), []);

  return (
    <div className="theme-row" data-state={playing ? "playing" : loading ? "loading" : undefined} onPointerEnter={enter} onPointerLeave={leave}>
      <button
        type="button"
        className="theme-play"
        onClick={() => {
          window.clearTimeout(timer.current); // the button decides now, not a pending hover
          if (playing) previews.stop(song.id);
          else previews.play(song);
        }}
        disabled={noPreview}
        aria-pressed={playing}
      >
        {playing ? <PauseIcon /> : <PlayIcon />}
        <span className="visually-hidden">
          {noPreview
            ? `No preview of ${song.title} in your country's Apple store`
            : `${playing ? "Pause" : "Play"} the preview of ${song.title}`}
        </span>
      </button>
      <Link
        to={`/anime/${anime.id}/song/${song.id}`}
        state={{ anime, theme: song, song: found ?? undefined }}
        className="theme-link"
      >
        {song.number && <span className="theme-number">{song.number}: </span>}
        <span className="theme-title">“{song.title}”</span>
        {song.title_native && <span lang="ja"> ({song.title_native})</span>}
        {song.artist && (
          <>
            {" "}
            by <span lang={langOf(song.artist)}>{song.artist}</span>
          </>
        )}
        {song.episodes && <span className="theme-eps"> ({song.episodes})</span>}
        {playing && <span className="now-playing" aria-hidden="true" />}
      </Link>
      {track && (
        <a className="theme-badge" href={track.url} target="_blank" rel="noopener sponsored">
          <img src={ITUNES_BADGE} alt={`Get ${song.title} on iTunes`} width={84} height={28} />
        </a>
      )}
    </div>
  );
}

type Previews = ReturnType<typeof useSongPreviews>;

/**
 * One audio player for the whole list, so only one song plays at a time.
 *
 * Each song is looked up in Apple's store the first time it's played, not when the page
 * opens: Apple allows about 20 searches a minute for the whole site. Lookups are kept for
 * the page, and the song page reuses them.
 */
function useSongPreviews(animeId: number) {
  const { country } = useRegion();
  const code = country?.code ?? null;
  const audio = useRef<HTMLAudioElement | null>(null);
  const pending = useRef(new Map<number, Promise<SongResponse | null>>());
  const wanted = useRef<number | null>(null);
  const fade = useRef(0);
  const [lookups, setLookups] = useState<Record<number, Lookup>>({});
  const [active, setActive] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    const player = new Audio();
    player.preload = "none";
    const onPlaying = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onEnded = () => {
      wanted.current = null;
      setActive(null);
    };
    player.addEventListener("playing", onPlaying);
    player.addEventListener("pause", onPause);
    player.addEventListener("ended", onEnded);
    audio.current = player;
    return () => {
      player.pause();
      player.removeAttribute("src"); // stop the download too
      player.load();
      player.removeEventListener("playing", onPlaying);
      player.removeEventListener("pause", onPause);
      player.removeEventListener("ended", onEnded);
      audio.current = null;
    };
  }, []);

  // A different country means a different Apple store: forget what was looked up.
  useEffect(() => {
    pending.current.clear();
    setLookups({});
  }, [animeId, code]);

  const lookup = useCallback(
    (theme: ThemeSong): Promise<SongResponse | null> => {
      if (!code) return Promise.resolve(null);
      let request = pending.current.get(theme.id);
      if (!request) {
        setLookups((all) => ({ ...all, [theme.id]: { state: "loading" } }));
        request = api
          .song(animeId, theme, code)
          .catch(() => null)
          .then((song) => {
            if (!song || song.apple_status === "busy" || song.apple_status === "error") {
              pending.current.delete(theme.id); // worth trying again later
            }
            setLookups((all) => ({ ...all, [theme.id]: { state: "done", song } }));
            return song;
          });
        pending.current.set(theme.id, request);
      }
      return request;
    },
    [animeId, code],
  );

  const fadeTo = useCallback((player: HTMLAudioElement, target: number, ms: number) => {
    const token = ++fade.current;
    const from = player.volume;
    const start = performance.now();
    return new Promise<void>((resolve) => {
      const step = (now: number) => {
        if (token !== fade.current) return resolve(); // a newer fade took over
        const t = Math.min(1, (now - start) / ms);
        try {
          player.volume = from + (target - from) * t;
        } catch {
          // iOS doesn't let pages set volume; it plays at full volume instead
        }
        if (t < 1) requestAnimationFrame(step);
        else resolve();
      };
      requestAnimationFrame(step);
    });
  }, []);

  const play = useCallback(
    async (theme: ThemeSong) => {
      wanted.current = theme.id;
      setActive(theme.id);
      const song = await lookup(theme);
      const player = audio.current;
      if (wanted.current !== theme.id || !player) return; // the cursor moved on meanwhile
      const url = song?.apple_status === "ok" ? song.track?.preview_url : null;
      if (!url) {
        wanted.current = null;
        setActive(null);
        return;
      }
      if (player.src !== url) player.src = url;
      player.currentTime = 0;
      player.volume = 0;
      try {
        await player.play();
        setBlocked(false);
        void fadeTo(player, 1, FADE_IN_MS);
      } catch (err) {
        // NotAllowedError: no click on the page yet. AbortError: another song took over.
        if ((err as DOMException).name === "NotAllowedError") setBlocked(true);
        if (wanted.current === theme.id) {
          wanted.current = null;
          setActive(null);
        }
      }
    },
    [lookup, fadeTo],
  );

  /** Stop the given song (or whatever is playing), fading out rather than cutting off. */
  const stop = useCallback(
    (themeId?: number) => {
      if (themeId !== undefined && wanted.current !== themeId) return;
      wanted.current = null;
      setActive(null);
      const player = audio.current;
      if (!player || player.paused) return;
      void fadeTo(player, 0, FADE_OUT_MS).then(() => {
        if (wanted.current === null) player.pause();
      });
    },
    [fadeTo],
  );

  return { lookups, active, playing, blocked, play, stop };
}
