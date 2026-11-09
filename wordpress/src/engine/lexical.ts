/** Port of `src/gramoten/lexical.py`: grammar and usage, the forms a spellchecker cannot see. */

import { analyse } from "./morphology.ts";
import { capitalize, endsWithAny, finditer, first, fullmatch, isUpper, match, search, sub, toInt, upperFirst } from "./py.ts";
import { byPosition, normalise } from "./punctuation.ts";
import { inDictionary, isCorrect } from "./spelling.ts";

const W = "[А-Яа-яЍѝ]";
const B = String.raw`(?<![\w-])`;
const E = String.raw`(?![\w-])`;

const PREPS = `в във на с със за от до при чрез без към по през под над пред срещу според след
преди между сред заради около покрай извън измежду поради съгласно спрямо относно посредством
вследствие у върху зад край из въз подир отвъд`.split(/\s+/);

export interface Hit {
  code: string;
  start: number;
  end: number;
  message: string;
  /** The replacement; `""` deletes the span. */
  fix: string | null;
}

function hit(code: string, start: number, end: number, message: string, fix: string | null): Hit {
  return { code, start, end, message, fix };
}

function known(word: string): boolean {
  return word
    .toLowerCase()
    .split("-")
    .every((part) => !search("[а-я]", part) || inDictionary(part));
}

function caseLike(fix: string, like: string): string {
  return isUpper(first(like)) ? upperFirst(fix) : fix;
}

/** `сайтът` → `сайта`, `новият` → `новия`; null unless it is a masculine full article. */
function shortOfFull(word: string): string | null {
  const low = word.toLowerCase();
  if (!inDictionary(low) || [..."аяи"].some((end) => inDictionary(low + end))) return null;
  const readings = analyse(low);
  if (readings.length && !readings.some((r) => r.tag.d === "f")) return null;
  if (low.endsWith("ът")) {
    const base = low.slice(0, -2);
    const short = `${base}а`;
    if (base.length >= 2 && inDictionary(base) && inDictionary(short)) return caseLike(short, word);
  } else if (low.endsWith("ят")) {
    const short = low.slice(0, -1);
    const bases = [low.slice(0, -2), `${low.slice(0, -2)}й`, low.endsWith("ият") ? low.slice(0, -3) : ""];
    if (inDictionary(short) && bases.some((b) => b && b.length >= 2 && inDictionary(b))) return caseLike(short, word);
  }
  return null;
}

function articleAfterPreposition(text: string): Hit[] {
  const hits: Hit[] = [];
  const pattern = `${B}(${[...PREPS, ...PREPS.map(capitalize)].join("|")}) ((?:най-|по-)?${W}+(?:ът|ят))${E}`;
  for (const m of finditer(pattern, text)) {
    const word = m.group(2);
    const core = sub("^(?:най-|по-)", "", word);
    if (isUpper(first(core)) && core.toLowerCase() !== "вашият") continue;
    const short = shortOfFull(core);
    if (!short) continue;
    const after = text.slice(m.end, m.end + 120).split(/[,.;:!?–—()]/)[0];
    if (["преди", "след", "докато", "без", "вместо"].includes(m.group(1).toLowerCase()) && search(String.raw`(?<![\w-])да(?![\w-])`, after)) {
      continue; // `преди изпълнителят да…`: the subject of a да-clause
    }
    hits.push(
      hit(
        "article_after_preposition",
        m.start(2),
        m.stop(2),
        "After a preposition the word takes the short article (-а/-я)",
        word.slice(0, word.length - core.length) + short,
      ),
    );
  }
  return hits;
}

const ROMAN = "[IVXLCM]+";
const LATIN_SOUND: Record<string, string> = { f: "ф", v: "в", s: "с", z: "з" };

/** The next word's first sound, or null when it is read letter by letter or unsure. */
function firstSound(word: string): string | null {
  if (fullmatch(ROMAN, word)) return null;
  const head = match(String.raw`[^\W\d_]+`, word);
  if (head === null || search(String.raw`\d`, word) || isUpper(head.group(0))) return null;
  const letter = first(word).toLowerCase();
  if (match("[а-я]", letter)) return letter;
  return LATIN_SOUND[letter] ?? null;
}

const DIGITS = [..."0123456789"];

function vS(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(String.raw`(?<![\w-])(в|във|В|Във|с|със|С|Със)( [„\"«(]?)([\w][\w-]*)`, text)) {
    const prep = m.group(1);
    const following = m.group(3);
    if (text.slice(m.start(1) - 1, m.start(1)) === "." || text.slice(m.stop(1), m.stop(1) + 1) !== " ") continue;
    if (["в", "във", "с", "със"].includes(following.toLowerCase())) continue;
    const sound = firstSound(following);
    if (sound === null) continue;
    const low = prep.toLowerCase();
    const stressed = ["и", "или", "извън", "без", "вън"].includes(following.toLowerCase());
    if (low === "в" && "вф".includes(sound)) {
      hits.push(hit("v_vav", m.start(1), m.stop(1), "Before в or ф write „във“", caseLike("във", prep)));
    } else if (low === "във" && !"вф".includes(sound) && !stressed) {
      hits.push(hit("v_vav", m.start(1), m.stop(1), "„във“ goes only before в or ф; here „в“", caseLike("в", prep)));
    } else if (low === "с" && "сз".includes(sound)) {
      if (endsWithAny(text.slice(m.start(1) - 2, m.start(1)).trim(), DIGITS)) continue; // `5 с`: a unit
      hits.push(hit("s_sas", m.start(1), m.stop(1), "Before с or з write „със“", caseLike("със", prep)));
    } else if (low === "със" && !"сз".includes(sound) && !stressed) {
      hits.push(hit("s_sas", m.start(1), m.stop(1), "„със“ goes only before с or з; here „с“", caseLike("с", prep)));
    }
  }
  return hits;
}

const NOT_AFTER_NAI: ReadonlySet<string> = new Set(["и", "да", "не", "ми", "ти", "му", "ѝ", "й", "ни", "ви", "им", "се", "си", "е"]);

function superlative(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(`${B}([Нн]ай)(?: +| *- +| +- *)(${W}+)${E}`, text)) {
    const word = m.group(2);
    if (known(word) && !NOT_AFTER_NAI.has(word.toLowerCase())) {
      hits.push(hit("superlative_hyphen", m.index, m.end, "„най-“ is written with a hyphen and no space", `${m.group(1)}-${word}`));
    }
  }
  for (const m of finditer(`${B}([Нн]ай)(${W}{3,})${E}`, text)) {
    const whole = m.group(0);
    const tail = m.group(2);
    if (!known(whole) && known(tail) && !isUpper(first(whole))) {
      hits.push(hit("superlative_hyphen", m.index, m.end, "„най-“ is written with a hyphen", `${m.group(1)}-${tail}`));
    }
  }
  return hits;
}

const TOGETHER: ReadonlyArray<readonly [string, string]> = [
  ["в същност", "всъщност"],
  ["из общо", "изобщо"],
  ["из веднъж", "изведнъж"],
  ["в последствие", "впоследствие"],
  ["в следствие", "вследствие"],
  ["в къщи", "вкъщи"],
  ["на всякъде", "навсякъде"],
  ["на пример", "например"],
  ["за винаги", "завинаги"],
  ["на последък", "напоследък"],
  ["из цяло", "изцяло"],
  ["по някога", "понякога"],
  ["в предвид", "предвид"],
  ["впредвид", "предвид"],
  ["пред вид", "предвид"],
  ["до сега", "досега"],
  ["до тогава", "дотогава"],
  ["на скоро", "наскоро"],
  ["за напред", "занапред"],
  ["на вън", "навън"],
  ["от вън", "отвън"],
  ["от вътре", "отвътре"],
  ["в ляво", "вляво"],
  ["в дясно", "вдясно"],
  ["на ляво", "наляво"],
  ["на дясно", "надясно"],
  ["на горе", "нагоре"],
  ["на долу", "надолу"],
  ["до кога", "докога"],
  ["до когато", "докогато"],
  ["до тук", "дотук"],
  ["до там", "дотам"],
  ["до преди", "допреди"],
  ["до къде", "докъде"],
  ["до където", "докъдето"],
  ["до някъде", "донякъде"],
  ["до колко", "доколко"],
  ["до колкото", "доколкото"],
  ["от тук", "оттук"],
  ["от там", "оттам"],
  ["от кога", "откога"],
  ["по настоящем", "понастоящем"],
  ["на вред", "навред"],
  ["по-вече", "повече"],
  ["по-не", "поне"],
  ["от части", "отчасти"],
  ["от колкото", "отколкото"],
  ["до като", "докато"],
  ["по ради", "поради"],
  ["из между", "измежду"],
  ["току що", "току-що"],
  ["ноу хау", "ноу-хау"],
  ["министър председател", "министър-председател"],
];
const TOGETHER_PATTERN = `${B}(?:${[...TOGETHER]
  .sort((a, b) => b[0].length - a[0].length)
  .map(([wrong]) => wrong.replaceAll(" ", " +"))
  .join("|")})${E}`;
const TOGETHER_BY = new Map(TOGETHER);

const JOINED_ADJECTIVE =
  `${B}((?:[Тт]ъмно|[Сс]ветло|[Бб]ледо|[Яя]рко)(?: +|-)([а-я]+)` +
  `|[Нн]аучно(?: +|-)(изследователск[а-я]*)` +
  `|[Сс]ветовно +(известн[а-я]*))${E}`;

const SPLIT_PREFIX = `${B}([Пп]ра|[Пп]ре|[Пп]ри|[Пп]ро)- +([а-я]+)${E}`;

function splitPrefixes(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(SPLIT_PREFIX, text)) {
    const joined = m.group(1) + m.group(2);
    if (isCorrect(joined)) hits.push(hit("written_together", m.index, m.end, `Written together: „${joined}“`, joined));
  }
  return hits;
}

function joinedAdjectives(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(JOINED_ADJECTIVE, text)) {
    const start = match("[А-Яа-я]+", m.group(1)) as NonNullable<ReturnType<typeof match>>;
    const second = m.group(2) || m.group(3) || m.group(4);
    const joined = start.group(0) + second;
    const readings = analyse(second);
    if (!readings.length || !readings.every((r) => r.tag.pos === "A")) continue;
    if (!isCorrect(joined)) continue;
    hits.push(hit("written_together", m.index, m.end, `Written together: „${joined}“`, joined));
  }
  return hits;
}

const AFTER_DOKOLKO: ReadonlySet<string> = new Set(
  "е са съм си сме сте бил била било били би ще да се ли не ми ти му ѝ й им ни ви го я ги".split(" "),
);
const COUNTED_VERB_FORMS: ReadonlySet<string> = new Set(["души"]);

function notCounted(after: string): boolean {
  const m = match(String.raw`\s*(\w+)`, after);
  if (!m) return true;
  const word = m.group(1).toLowerCase();
  if (AFTER_DOKOLKO.has(word)) return true;
  const readings = analyse(word);
  return readings.length > 0 && readings.every((r) => r.tag.pos === "V") && !COUNTED_VERB_FORMS.has(word);
}

function together(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(TOGETHER_PATTERN, text, "i")) {
    const wrong = sub(" +", " ", m.group(0).toLowerCase());
    const right = TOGETHER_BY.get(wrong) as string;
    const preceding = text.slice(Math.max(0, m.index - 20), m.index);
    const after = text.slice(m.end, m.end + 30);
    if ((wrong === "до сега" || wrong === "до тогава") && search(String.raw`[Оо]т \S+ $`, preceding)) continue;
    if (wrong === "от части" && match(String.raw` (на|от)\b`, after)) continue;
    if (wrong === "на пример" && search(String.raw`(дава|даде|дадат|дадем|посочва|посочи|служи|послужи)\w* *$`, preceding)) continue;
    if (["в ляво", "в дясно", "на ляво", "на дясно"].includes(wrong) && match(String.raw` \w+(та|то|те|ия|ият)\b`, after)) continue;
    if (
      wrong === "от колкото" &&
      !search(String.raw`(?:повече|по-|(?<![\w-])по [а-я]|различн|друг|предпоч|вместо)[^.!?]*$`, text.slice(Math.max(0, m.index - 80), m.index).toLowerCase())
    ) {
      continue; // no comparison, so no `отколкото`
    }
    if ((wrong === "до колко" || wrong === "до колкото") && !notCounted(after)) continue;
    const message = right.includes("-") ? `Written with a hyphen: „${right}“` : `Written together: „${right}“`;
    hits.push(hit("written_together", m.index, m.end, message, caseLike(right, m.group(0))));
  }
  return hits;
}

const FUNCTION: ReadonlySet<string> = new Set(
  `и а но или да не ще се за на в във с със от до по при към без през че ако като
който която което които това този тази тези е са`.split(/\s+/),
);

function repeated(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(`${B}(${W}+) +(\\1)${E}`, text, "i")) {
    const word = m.group(1).toLowerCase();
    if (text.slice(m.stop(2), m.stop(2) + 1) === ")") continue; // `букви з) и и)`: a list letter
    if (FUNCTION.has(word) && word === m.group(2).toLowerCase()) {
      hits.push(hit("repeated_word", m.start(2) - 1, m.stop(2), `„${word}“ twice`, ""));
    }
  }
  return hits;
}

function range(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(String.raw`(?<![\w.,/:+-])(\d{1,4}) ?- ?(\d{1,4})(?![\w.,/:+-]|-)(?= ?(?:[а-яА-Я%€]|$))`, text)) {
    if (toInt(m.group(2)) > toInt(m.group(1))) {
      hits.push(hit("number_range", m.index, m.end, "A range of numbers takes an en dash, no spaces", `${m.group(1)}–${m.group(2)}`));
    }
  }
  return hits;
}

const DETECTORS = [articleAfterPreposition, vS, superlative, together, joinedAdjectives, splitPrefixes, repeated, range];

/** The rules of one text; offsets are into `text`. */
export function check(text: string): Hit[] {
  const normal = normalise(text);
  const hits = DETECTORS.flatMap((detector) => detector(normal)).map((h) =>
    h.fix === null || normal.slice(h.start, h.end) === text.slice(h.start, h.end) ? h : { ...h, fix: null },
  );
  return byPosition(hits);
}
