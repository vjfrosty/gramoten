/** Port of `src/gramoten/mixed_script.py`: Latin letters hidden in Cyrillic words, and the reverse. */

import { finditer, search } from "./py.ts";
import { isCorrect } from "./spelling.ts";
import { CYRILLIC, LATIN } from "./tokenize.ts";

const LATINS = [..."aeopcxyAEOPCXYBKMHT"];
const CYRILLICS = [..."аеорсхуАЕОРСХУВКМНТ"];
const LATIN_TO_CYRILLIC = new Map(LATINS.map((c, i) => [c, CYRILLICS[i]]));
const CYRILLIC_TO_LATIN = new Map(LATINS.map((c, i) => [CYRILLICS[i], c]));

function fixPart(part: string): string | null {
  const cyr = finditer(CYRILLIC, part).length;
  const lat = finditer(LATIN, part).length;
  if (!(cyr && lat)) return part;
  if (cyr === lat) return null;
  const table = cyr > lat ? LATIN_TO_CYRILLIC : CYRILLIC_TO_LATIN;
  const foreign = cyr > lat ? LATIN : CYRILLIC;
  let out = "";
  for (const ch of part) {
    if (search(foreign, ch)) {
      const mapped = table.get(ch);
      if (mapped === undefined) return null;
      out += mapped;
    } else {
      out += ch;
    }
  }
  return out;
}

/** The word in one script per hyphen part, or null when that is not certain. */
export function fix(word: string): string | null {
  const parts = word.split("-").map(fixPart);
  if (parts.some((p) => p === null)) {
    const cyrillic = [...word].map((c) => LATIN_TO_CYRILLIC.get(c) ?? c).join("");
    return !search(LATIN, cyrillic) && isCorrect(cyrillic) ? cyrillic : null;
  }
  const fixed = parts.join("-");
  return fixed !== word ? fixed : null;
}
