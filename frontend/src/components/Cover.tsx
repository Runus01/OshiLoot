import { Link } from "react-router";
import { displayTitle } from "../lib/scores";
import type { Anime } from "../types";

export function Cover({ anime }: { anime: Anime }) {
  const title = displayTitle(anime);
  return (
    <Link to={`/anime/${anime.id}`} state={{ anime }} className="cover">
      {anime.picture ? (
        <img src={anime.picture} alt="" loading="lazy" width={225} height={318} />
      ) : (
        <span className="cover-blank" aria-hidden="true" />
      )}
      <span className="cover-title">{title}</span>
    </Link>
  );
}
