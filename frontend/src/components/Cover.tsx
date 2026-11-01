import { Link } from "react-router";
import { displayTitle } from "../lib/scores";
import type { Anime } from "../types";

/** detail: an optional line under the title, such as "Score 9.30". */
export function Cover({ anime, detail }: { anime: Anime; detail?: string | null }) {
  const title = displayTitle(anime);
  return (
    <Link to={`/anime/${anime.id}`} state={{ anime }} className="cover">
      {anime.picture ? (
        <img src={anime.picture} alt="" loading="lazy" width={225} height={318} />
      ) : (
        <span className="cover-blank" aria-hidden="true" />
      )}
      <span className="cover-title">{title}</span>
      {detail && <span className="cover-detail">{detail}</span>}
    </Link>
  );
}
