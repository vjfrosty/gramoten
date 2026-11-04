/**
 * Port of `src/gramoten/spelling.py`. Two things differ, neither in its results:
 *
 * - `bg_frequency` and `misspellings` hold their value in the key (`word \x01 value`), as
 *   the WASM trie reads keys only as text.
 * - No `word_starts.marisa`, which would not fit the plugin size limit: whether a known
 *   word begins with some letters is a prefix search in the two lists it was built from.
 */

import { once, onReset, text, trie } from "./data.ts";
import { first, isUpper, strip, upperFirst } from "./py.ts";

export const ALPHABET = "абвгдежзийклмнопрстуфхцчшщъьюя";

const FILL_TO = 5;
const SECOND_EDIT_STEPS = 100_000;

const SOUND_ALIKE: ReadonlyArray<readonly [string, string]> = [
  ["а", "ъ"], ["о", "у"], ["е", "и"], ["е", "я"], ["я", "ъ"], ["я", "а"], ["ю", "у"],
  ["б", "п"], ["в", "ф"], ["г", "к"], ["д", "т"], ["ж", "ш"], ["з", "с"], ["и", "й"],
  ["я", "йа"], ["я", "йъ"], ["ю", "йу"], ["щ", "шт"], ["ьо", "йо"],
  ["ия", "еъ"], ["ия", "иъ"], ["ия", "ийъ"], ["ия", "еа"], ["иа", "я"], ["еи", "ей"],
  ["стн", "сн"], ["здн", "зн"], ["ст", "с"], ["щт", "щ"], ["вств", "ств"], ["вств", "св"],
  ["дс", "ц"], ["тс", "ц"], ["жт", "щ"], ["хв", "ф"], ["ст", "з"], ["вз", "з"], ["стч", "шч"],
];

const SOUND_REWRITES = new Map<string, string[]>();
function addRewrite(from: string, to: string): void {
  const list = SOUND_REWRITES.get(from);
  if (list) list.push(to);
  else SOUND_REWRITES.set(from, [to]);
}
for (const [a, b] of SOUND_ALIKE) {
  addRewrite(a, b);
  addRewrite(b, a);
}
for (const c of ALPHABET) {
  addRewrite(c + c, c);
  addRewrite(c, c + c);
}
const SOUND_LONGEST = Math.max(...[...SOUND_REWRITES.keys()].map((k) => k.length));
const SOUND_CHANGES_MAX = 8;
const SOUND_COST = 0.5;
const FREQUENCY_WEIGHT = 0.3;

export const ABBREVIATIONS: ReadonlySet<string> = new Set(
  `г гр ул бул пл жк кв бл вх ет ап обл общ напр вкл др проф доц инж арх акад
ген полк зам св хр пр сл стр бр лв млн млрд хил тел факс жп сп изд прев ред ок прибл англ лат гр рус
нем фр ит исп мин сек ч т н сл ср вж срв гл чл ал т.е т.нар т.н пр.хр сл.хр
яну ян фев мар апр авг сеп сеп окт ное дек пон вт чет пет съб нед`.split(/\s+/),
);
export const UNITS: ReadonlySet<string> = new Set("км м см мм кг г мг л мл дка ха кв.м мб гб кб мвт квт вт".split(" "));

const COMBINING_FORMS: ReadonlySet<string> = new Set(
  "австро англо франко германо гръко индо афро испано италиано българо славяно юдео греко медиа".split(" "),
);

const ACRONYM_MAX = 5;

export type Extra = ReadonlySet<string>;
export const NO_WORDS: Extra = new Set();

function readWords(name: Parameters<typeof text>[0]): Set<string> {
  const out = new Set<string>();
  for (const line of text(name).split("\n")) {
    const word = strip(line.split("#")[0]).toLowerCase();
    if (word) out.add(word);
  }
  return out;
}

const projectWords = once(
  () =>
    new Set<string>([
      ...readWords("project_words.txt"),
      ...readWords("telecom_words.txt"),
      ...readWords("vocative_words.txt"),
      ...readWords("eu_words.txt"),
    ]),
);

const VALUE = "\x01";

function count(word: string): number {
  const key = trie("bg_frequency.marisa").firstKey(word + VALUE);
  return key === undefined ? 0 : Number.parseInt(key.slice(key.indexOf(VALUE) + 1), 16);
}

export function inDictionary(lower: string): boolean {
  return trie("bg_forms.marisa").has(lower);
}

const LOANWORDS: ReadonlySet<string> = new Set(["хаус", "реднек", "скраб", "друид"]);

const corrections = once(() => {
  const out = new Map<string, string>();
  for (const line of text("corrections.tsv").split("\n")) {
    const entry = strip(line.split("#")[0]);
    const tab = entry.indexOf("\t");
    if (tab >= 0 && entry.slice(tab + 1)) out.set(entry.slice(0, tab), entry.slice(tab + 1));
  }
  return out;
});

const forbiddenWords = once(() => {
  const out = new Set<string>([...readWords("forbidden_words.txt"), ...corrections().keys()]);
  for (const word of LOANWORDS) out.delete(word);
  return out;
});

/** The correction for this misspelling, if one is known. */
export function knownCorrection(word: string): string | null {
  const lower = word.toLowerCase();
  const own = corrections().get(lower);
  if (own !== undefined) return own;
  const key = trie("misspellings.marisa").firstKey(lower + VALUE);
  if (key !== undefined) return key.slice(key.indexOf(VALUE) + 1);
  if (lower.endsWith("ста") && inDictionary(`${lower.slice(0, -1)}та`)) return `${lower.slice(0, -1)}та`;
  return null;
}

/** A capitalised word the corpora know as a name. */
export function isName(word: string): boolean {
  return isUpper(first(word)) && trie("names.marisa").has(word.toLowerCase());
}

function known(lower: string, extra: Extra): boolean {
  if (extra.has(lower) || LOANWORDS.has(lower)) return true;
  if (corrections().has(lower)) return false;
  if (trie("bg_forms.marisa").has(lower)) return true;
  if (forbiddenWords().has(lower)) return false;
  return trie("modern_words.marisa").has(lower) || projectWords().has(lower);
}

/** True when every hyphen part is a known form, in any capitalisation. */
export function isCorrect(word: string, extra: Extra = NO_WORDS): boolean {
  if (isUpper(word) && [...word].length <= ACRONYM_MAX) return true;
  const lower = word.toLowerCase();
  if (known(lower, extra)) return true;
  const parts = lower.split("-");
  const last = parts[parts.length - 1];
  return (
    parts.length > 1 &&
    parts.slice(0, -1).every((p) => [...p].length <= 1 || known(p, extra) || COMBINING_FORMS.has(p)) &&
    ([...last].length <= 1 || known(last, extra))
  );
}

function edits(word: string, upto: number): Set<string> {
  const out = new Set<string>();
  // By character, not by UTF-16 unit: as in Python, `𝐀` is one letter to edit.
  const chars = [...word];
  const join = (from: number, to?: number): string => chars.slice(from, to).join("");
  const limit = Math.min(chars.length, upto);
  for (let i = 0; i <= limit; i++) {
    const a = join(0, i);
    const b = join(i);
    const rest = join(i + 1);
    if (b) out.add(a + rest);
    if (chars.length - i > 1) out.add(a + chars[i + 1] + chars[i] + join(i + 2));
    for (const c of ALPHABET) {
      if (b && c !== chars[i]) out.add(a + c + rest);
      out.add(a + c + b);
    }
  }
  return out;
}

function shape(suggestion: string, like: string): string {
  if (isUpper(like) && [...like].length > 1) return suggestion.toUpperCase();
  if (isUpper(first(like))) return upperFirst(suggestion);
  return suggestion;
}

/** Known words one edit away or spelt the way `word` sounds, as `spelling.suggest`. */
export function suggest(word: string, limit = 5, extra: Extra = NO_WORDS, deep = true): string[] {
  let found = ranked(word.toLowerCase(), extra, deep);
  const correction = knownCorrection(word);
  if (correction && (!correction.includes(" ") || corrections().has(word.toLowerCase()))) {
    found = [correction, ...found.filter((w) => w !== correction)];
  }
  return found.slice(0, limit).map((w) => shape(w, word));
}

function startsOf(words: Iterable<string>): Set<string> {
  const out = new Set<string>();
  for (const w of words) {
    for (let i = 1; i <= w.length; i++) out.add(w.slice(0, i));
  }
  return out;
}

const projectStarts = once(() => startsOf(projectWords()));

/** One entry per set of added words: a host keeps its set while the words stay the same. */
const addedCache = new WeakMap<Extra, { key: string; starts: Set<string> }>();
function added(extra: Extra): { key: string; starts: Set<string> } {
  let found = addedCache.get(extra);
  if (!found) {
    found = { key: [...extra].sort().join("\x00"), starts: startsOf(extra) };
    addedCache.set(extra, found);
  }
  return found;
}

const RANKED_MAX = 20_000;
const RANKED = new Map<string, string[]>();
onReset(() => RANKED.clear());

function ranked(lower: string, extra: Extra, deep: boolean): string[] {
  const key = `${lower}\x01${deep ? 1 : 0}\x01${added(extra).key}`;
  const hit = RANKED.get(key);
  if (hit) {
    RANKED.delete(key);
    RANKED.set(key, hit);
    return hit;
  }
  const [found, finished] = searchWords(lower, extra, deep);
  if (finished) {
    RANKED.set(key, found);
    if (RANKED.size > RANKED_MAX) RANKED.delete(RANKED.keys().next().value as string);
  }
  return found;
}

/** Forget every suggestion made. */
export function clearSuggestions(): void {
  RANKED.clear();
}

/** Whether some key of the lists begins with this: what `word_starts.marisa` answers. */
const inBigLists = (() => {
  const seen = new Map<string, boolean>();
  onReset(() => seen.clear());
  return (prefix: string): boolean => {
    let found = seen.get(prefix);
    if (found === undefined) {
      if (seen.size > 500_000) seen.clear();
      found =
        trie("bg_forms.marisa").firstKey(prefix) !== undefined ||
        trie("modern_words.marisa").firstKey(prefix) !== undefined;
      seen.set(prefix, found);
    }
    return found;
  };
})();

type Pred = (w: string) => boolean;

function searchWords(lower: string, extra: Extra, deep: boolean): [string[], boolean] {
  const forms = trie("bg_forms.marisa");
  const modern = trie("modern_words.marisa");
  const project = projectWords();
  const forbidden = forbiddenWords();
  const fixes = corrections();
  const addedStarts = added(extra).starts;
  const starts = projectStarts();

  const isKnown: Pred = (w) => {
    if (extra.has(w)) return true;
    if (forms.has(w)) return !fixes.has(w);
    return (modern.has(w) || project.has(w)) && !forbidden.has(w);
  };
  const opens: Pred = (prefix) => !prefix || starts.has(prefix) || addedStarts.has(prefix) || inBigLists(prefix);
  const reach = (w: string): number => {
    const chars = [...w];
    let low = 0;
    let high = chars.length;
    while (low < high) {
      const middle = Math.floor((low + high + 1) / 2);
      if (opens(chars.slice(0, middle).join(""))) low = middle;
      else high = middle - 1;
    }
    return low;
  };

  const cost = new Map<string, number>();
  for (const w of edits(lower, reach(lower))) {
    if (isKnown(w)) cost.set(w, 1);
  }
  const [sounds, soundsFinished] = soundAlikes(lower, opens, isKnown, SECOND_EDIT_STEPS);
  let finished = soundsFinished;
  for (const [w, changes] of sounds) {
    cost.set(w, Math.min(cost.get(w) ?? Number.POSITIVE_INFINITY, SOUND_COST * changes));
  }
  cost.delete(lower);
  let withinOne = 0;
  for (const c of cost.values()) if (c <= 1) withinOne++;
  if (deep && withinOne < FILL_TO) {
    const [two, twoFinished] = withinTwo(lower, opens, isKnown, SECOND_EDIT_STEPS);
    finished = twoFinished;
    for (const w of two) {
      if (w !== lower && !cost.has(w)) cost.set(w, 2);
    }
  }

  const ranks = [...cost.keys()].map((w) => {
    const used = count(w);
    return { w, score: (cost.get(w) as number) - FREQUENCY_WEIGHT * Math.log10(used + 1), used };
  });
  ranks.sort((a, b) => a.score - b.score || b.used - a.used || (a.w < b.w ? -1 : a.w > b.w ? 1 : 0));
  return [ranks.map((r) => r.w), finished];
}

function soundAlikes(text: string, opens: Pred, isKnown: Pred, steps: number): [Map<string, number>, boolean] {
  const word = [...text];
  const found = new Map<string, number>();
  const fewest = new Map<string, number>();
  const starts = new Map<string, boolean>();
  const begins = (prefix: string): boolean => {
    let value = starts.get(prefix);
    if (value === undefined) {
      value = opens(prefix);
      starts.set(prefix, value);
    }
    return value;
  };

  const stack: Array<[number, string, number]> = [[0, "", 0]];
  while (stack.length) {
    if (starts.size > steps) return [found, false];
    const [i, built, changes] = stack.pop() as [number, string, number];
    const state = `${i}\x01${built}`;
    if ((fewest.get(state) ?? SOUND_CHANGES_MAX + 1) <= changes) continue;
    fewest.set(state, changes);
    if (i === word.length) {
      if (changes && isKnown(built) && changes < (found.get(built) ?? SOUND_CHANGES_MAX + 1)) {
        found.set(built, changes);
      }
      continue;
    }
    if (begins(built + word[i])) stack.push([i + 1, built + word[i], changes]);
    if (changes === SOUND_CHANGES_MAX) continue;
    const longest = Math.min(SOUND_LONGEST, word.length - i);
    for (let n = 1; n <= longest; n++) {
      for (const written of SOUND_REWRITES.get(word.slice(i, i + n).join("")) ?? []) {
        if (begins(built + written)) stack.push([i + n, built + written, changes + 1]);
      }
    }
  }
  return [found, true];
}

function withinTwo(text: string, opens: Pred, isKnown: Pred, steps: number): [Set<string>, boolean] {
  const word = [...text];
  const found = new Set<string>();
  const seen = new Set<string>();
  const starts = new Map<string, boolean>();
  const begins = (prefix: string): boolean => {
    let value = starts.get(prefix);
    if (value === undefined) {
      value = opens(prefix);
      starts.set(prefix, value);
    }
    return value;
  };

  const n = word.length;
  const stack: Array<[number, string, number]> = [[0, "", 2]];
  while (stack.length) {
    if (starts.size > steps) return [found, false];
    const [i, built, left] = stack.pop() as [number, string, number];
    const state = `${i}\x01${left}\x01${built}`;
    if (seen.has(state)) continue;
    seen.add(state);
    const here = word[i];
    if (i < n) {
      if (begins(built + here)) stack.push([i + 1, built + here, left]);
    } else if (isKnown(built)) {
      found.add(built);
    }
    if (!left) continue;
    const down = left - 1;
    const alive: string[] = [];
    for (const c of ALPHABET) if (begins(built + c)) alive.push(c);
    if (i < n) {
      stack.push([i + 1, built, down]);
      for (const c of alive) {
        if (c !== here) stack.push([i + 1, built + c, down]);
      }
      if (i + 1 < n && here !== word[i + 1] && begins(built + word[i + 1] + here)) {
        stack.push([i + 2, built + word[i + 1] + here, down]);
      }
    }
    for (const c of alive) stack.push([i, built + c, down]);
  }
  return [found, true];
}
