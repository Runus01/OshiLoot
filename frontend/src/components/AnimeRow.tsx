import { useCallback, useEffect, useRef, useState } from "react";
import type { Anime } from "../types";
import { Cover } from "./Cover";
import { ChevronIcon } from "./Icons";

const PLACEHOLDERS = 8;

interface Props {
  id: string;
  title: string;
  note: string;
  anime: Anime[] | null; // null while loading
}

/**
 * A titled shelf of covers that scrolls sideways: swipe on a phone, or use the arrow
 * buttons with a mouse. Keyboard users tab through the covers, which scrolls the row.
 */
export function AnimeRow({ id, title, note, anime }: Props) {
  const list = useRef<HTMLUListElement>(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);

  const measure = useCallback(() => {
    const row = list.current;
    if (!row) return;
    setAtStart(row.scrollLeft <= 4);
    setAtEnd(row.scrollLeft + row.clientWidth >= row.scrollWidth - 4);
  }, []);

  useEffect(() => {
    const row = list.current;
    if (!row) return;
    measure();
    const resize = new ResizeObserver(measure);
    resize.observe(row);
    return () => resize.disconnect();
  }, [anime, measure]);

  const scroll = (direction: 1 | -1) => {
    const row = list.current;
    row?.scrollBy({ left: direction * row.clientWidth * 0.85, behavior: "smooth" });
  };

  return (
    <section className="browse" aria-labelledby={id}>
      <div className="browse-head">
        <div>
          <h2 id={id}>{title}</h2>
          <p className="muted">{note}</p>
        </div>
        {/* For mouse users only: keyboards and screen readers reach every cover anyway. */}
        <div className="browse-arrows" aria-hidden="true">
          <button type="button" className="arrow-button" tabIndex={-1} onClick={() => scroll(-1)} disabled={atStart}>
            <ChevronIcon direction="left" />
          </button>
          <button type="button" className="arrow-button" tabIndex={-1} onClick={() => scroll(1)} disabled={atEnd}>
            <ChevronIcon direction="right" />
          </button>
        </div>
      </div>
      <ul className="shelf-row" ref={list} onScroll={measure} aria-busy={anime === null}>
        {anime
          ? anime.map((item) => (
              <li key={item.id}>
                <Cover anime={item} />
              </li>
            ))
          : Array.from({ length: PLACEHOLDERS }, (_, i) => (
              <li key={i} aria-hidden="true">
                <span className="cover-blank cover-loading" />
              </li>
            ))}
      </ul>
    </section>
  );
}
