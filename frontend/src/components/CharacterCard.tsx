import { Link } from "react-router";
import { roleLabel } from "../lib/text";
import type { Anime, Character } from "../types";

/** A character's portrait and name, linking to merch of that character. */
export function CharacterCard({ anime, character, cast }: { anime: Anime; character: Character; cast: Character[] }) {
  const role = roleLabel(character.role);
  return (
    <Link
      to={`/anime/${anime.id}/character/${character.id}`}
      state={{ anime, character, cast }}
      className="character-card"
    >
      {character.image ? (
        <img src={character.image} alt="" loading="lazy" width={230} height={345} />
      ) : (
        <span className="character-blank" aria-hidden="true" />
      )}
      <span className="character-name">{character.name}</span>
      {character.name_native && (
        <span className="character-native" lang="ja">
          {character.name_native}
        </span>
      )}
      {role && <span className="character-role">{role}</span>}
    </Link>
  );
}
