/** Port of `src/gramoten/punctuation.py`: Bulgarian commas and punctuation, by rule. */

import { finditer, fullmatch, match, search, sub } from "./py.ts";
import { inDictionary } from "./spelling.ts";
import { before } from "./tokenize.ts";

// `(?i:…)` written out: inline flags are too new for some browsers.
const FIRST_NAME = "[fF][iI][rR][sS][tT]_?[nN][aA][mM][eE]";
const NAME_PH = String.raw`(?:\{P:(?:${FIRST_NAME}|[nN][aA][mM][eE]|[iI][mM][eE])\}|%%=?[^%]{0,30}(?:${FIRST_NAME}|[iI][mM][eE])[^%]{0,20}%%)`;
const LATINS = [..."aeopcxyAEOPCXYBKMHT"];
const CYRILLICS = [..."аеорсхуАЕОРСХУВКМНТ"];
const LAT2CYR = new Map(LATINS.map((c, i) => [c, CYRILLICS[i]]));
const CYR = "[А-Яа-яЁёЍѝЪъ]";
const WORD = "[A-Za-zА-Яа-яЁёЍѝЪъ]+";

/** Same length as `text`: lookalike letters made Cyrillic, other placeholders masked. */
export function normalise(text: string): string {
  let t = sub(
    WORD,
    (w) =>
      search(CYR, w) && search("[A-Za-z]", w)
        ? [...w].map((c) => LAT2CYR.get(c) ?? c).join("")
        : w,
    text,
  );
  t = sub("(?<=[а-я] )a(?= [а-я])", "а", t);
  t = sub(
    String.raw`%%\[.*?\]%%|%%=.*?=%%|%%[^%\s]{1,60}%%|\{P:[^{}]{1,60}\}`,
    (m) => (fullmatch(NAME_PH, m) ? m : "◊".repeat(m.length)),
    t,
    "s",
  );
  t = sub(String.raw`\b(?:https?://|www\.)\S+`, (m) => "◊".repeat(m.length), t);
  return t.replaceAll("\xa0", " ");
}

const set = (words: string): ReadonlySet<string> => new Set(words.trim().split(/\s+/));

const NO_COMMA_PREV = set(`
и а но или ни нито че да не пък та па ами ала
само дори даже именно особено едва тъкмо точно чак поне още също просто включително
може би сигурно вероятно навярно освен и още
който която което които чийто чиято чието чиито когато където защото ако докато отколкото
понеже като щом макар въпреки преди след за без
понякога обикновено често винаги главно предимно най-вече единствено отчасти почти най-малко
например всъщност впрочем наистина следователно обаче действително навярно сякаш както
по-специално веднага ама май добре
`);
const PREPS = set(`в във на с със за от до при чрез без към по през под над пред срещу според след
преди между сред заради около въпреки покрай извън освен измежду поради съгласно спрямо
относно посредством вследствие благодарение у върху зад край из въз вместо подир отвъд`);
const REL = "(?:който|която|което|които|чийто|чиято|чието|чиито|когото)";
const CONJ: ReadonlyArray<readonly [string, ReadonlySet<string>]> = [
  ["че", set("въпреки макар така освен само като все случай положение условие затова дето нали ето щом тъй независимо")],
  ["защото", new Set()],
  ["понеже", new Set()],
  ["когато", set("от до тогава")],
  ["където", set("от до там")],
  ["ако", set("освен като")],
  ["докато", set("до")],
  ["отколкото", new Set()],
  ["след като", set("секунди секунда минути минута часа час дни ден седмици седмица месеца месец години година")],
  ["тъй като", new Set()],
  ["въпреки че", new Set()],
  ["макар че", new Set()],
  ["за да", new Set()],
  ["без да", new Set()],
  ["както и", new Set()],
];
const GREETINGS = "(?:Здравей|Здравейте|Добър ден|Добро утро|Добър вечер|Привет|Здрасти)";
const GREET_NOT_VOC = set("отново пак и на от за днес още всички");
const SPLIT_COMPOUNDS = [
  "въпреки, че",
  "макар, че",
  "след, като",
  "тъй, като",
  "без, да",
  "в случай, че",
  "при положение, че",
  "при условие, че",
  "освен, ако",
  "като, че ли",
];

export interface Hit {
  code: string;
  start: number;
  end: number;
  message: string;
  fix: string | null;
}

function hit(code: string, start: number, end: number, message: string, fix: string | null = null): Hit {
  return { code, start, end, message, fix };
}

function prevWord(text: string, idx: number): [string | null, number | null] {
  const window = before(text, idx);
  const m = search(String.raw`([\w\-}%»“”\")]+)(\s+)$`, window);
  return m ? [m.group(1), idx - window.length + m.start(1)] : [null, null];
}

/** A token that can end a clause; a placeholder or a short unknown token keeps the rule quiet. */
function okPrev(word: string): boolean {
  if (word.includes("◊")) return false;
  if (!fullmatch(String.raw`[\w\-]*[\wА-Яа-я][%“”\")]*|[\w\-]*%|[0-9][\w.,]*`, word)) return false;
  const bare = sub(String.raw`[%“”\")]+$`, "", word);
  return [...word].length > 4 || !search(CYR, bare) || inDictionary(bare.toLowerCase());
}

function commaBefore(text: string, prevStart: number, prev: string, end: number): [number, string] {
  const gap = prevStart + prev.length;
  return [gap, `,${text.slice(gap, end)}`];
}

function conjunctions(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const [conj, glue] of CONJ) {
    for (const m of finditer(String.raw`(?<![\w-])${conj.replaceAll(" ", String.raw`\s+`)}(?![\w-])`, text)) {
      const s = m.index;
      if (s === 0 || text[s - 1] !== " ") continue;
      const [prev, prevStart] = prevWord(text, s);
      if (!prev || prevStart === null || !okPrev(prev)) continue;
      const low = prev.toLowerCase();
      if (NO_COMMA_PREV.has(low) || glue.has(low) || PREPS.has(low)) continue;
      if (search(String.raw`(може би|като че ли|дори и|само и|още повече|преди всичко)\s+$`, before(text, s).toLowerCase())) {
        continue;
      }
      const [gap, fixed] = commaBefore(text, prevStart, prev, m.end);
      hits.push(hit("comma_before_conjunction", gap, m.end, `Comma before „${conj}“`, fixed));
    }
  }
  return hits;
}

function relatives(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(String.raw`(?<![\w-])${REL}(?![\w-])`, text)) {
    const s = m.index;
    if (s === 0 || text[s - 1] !== " ") continue;
    const [prev, prevStart] = prevWord(text, s);
    if (!prev || prevStart === null || !okPrev(prev)) continue;
    if (NO_COMMA_PREV.has(prev.toLowerCase()) || PREPS.has(prev.toLowerCase())) continue;
    if (
      match(
        String.raw`\s*(и да е|и да|иска|искаш|искате|желаеш|желаете|предпочиташ|предпочитате|` +
          String.raw`харесаш|харесате|ти харесва|Ви харесва|ви харесва)(?![\w-])`,
        text,
        m.end,
      )
    ) {
      continue; // free relative: "вземи която искаш" takes no comma
    }
    const [gap, fixed] = commaBefore(text, prevStart, prev, m.end);
    hits.push(hit("comma_before_relative", gap, m.end, `Comma before „${m.group(0)}“`, fixed));
  }
  return hits;
}

function adversative(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(String.raw`(?<![\w-])но(?![\w-])`, text)) {
    const s = m.index;
    if (s === 0 || text[s - 1] !== " " || !match(String.raw` [а-яА-Я0-9{%„\"]`, text.slice(m.end, m.end + 2))) continue;
    const [prev, prevStart] = prevWord(text, s);
    if (
      !prev ||
      prevStart === null ||
      !okPrev(prev) ||
      NO_COMMA_PREV.has(prev.toLowerCase()) ||
      PREPS.has(prev.toLowerCase())
    ) {
      continue;
    }
    const [gap, fixed] = commaBefore(text, prevStart, prev, m.end);
    hits.push(hit("comma_before_conjunction", gap, m.end, "Comma before „но“", fixed));
  }
  return hits;
}

function repeated(text: string): Hit[] {
  return finditer(String.raw`(?:^|(?<=[,:;.!?] ))(нито|Нито) ([^,.;:!?]{1,60}?) (нито)(?![\w-])`, text).map((m) =>
    hit("comma_repeated_conjunction", m.start(3) - 1, m.stop(3), "Comma before the second „нито“", ", нито"),
  );
}

function vocative(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(
    String.raw`(?<![\w-])(${GREETINGS})( +)(${NAME_PH}|[А-ЯA-Z][а-яa-z]+|приятели|приятелю|клиенти)`,
    text,
  )) {
    if (GREET_NOT_VOC.has(m.group(3).toLowerCase())) continue;
    hits.push(hit("comma_vocative", m.index, m.end, "Comma after the greeting, before the name", `${m.group(1)}, ${m.group(3)}`));
  }
  for (const m of finditer(NAME_PH, text)) {
    const [prev] = prevWord(text, m.index);
    const badAfter = match(" [а-яА-Яa-zA-Z]", text.slice(m.end, m.end + 2));
    const badBefore =
      prev !== null && search("^[а-яА-Я]", prev) && !PREPS.has(prev.toLowerCase()) && !fullmatch(GREETINGS, prev);
    if (badAfter || badBefore) hits.push(hit("comma_vocative", m.index, m.end, "Set the name off with commas"));
  }
  return hits;
}

function splitCompounds(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const pattern of SPLIT_COMPOUNDS) {
    for (const m of finditer(String.raw`(?<![\w-])${pattern}(?![\w-])`, text, "i")) {
      const whole = m.group(0).replaceAll(",", "");
      hits.push(hit("comma_inside_compound", m.index, m.end, `„${whole}“ is one conjunction; the comma goes before it`, whole));
    }
  }
  for (const m of finditer(
    String.raw`(?<![\w-])(в|във|на|с|със|за|от|до|при|чрез|без|към|по|през|под|над|пред|у|` +
      String.raw`върху|зад|из), (${REL})(?![\w-])`,
    text,
  )) {
    hits.push(
      hit("comma_inside_compound", m.index, m.end, `The comma goes before the preposition: „…, ${m.group(1)} ${m.group(2)}“`),
    );
  }
  return hits;
}

function marks(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(String.raw`(?<![,\w]),,(?=[„\"“]?[^\W\d_])`, text)) {
    hits.push(hit("comma_comma_quote", m.index, m.end, "Two commas typed for the opening quote „", "„"));
  }
  for (const m of finditer(String.raw`([,;:]) ?([,;:])|([,;]) ?(\.)(?!\.)`, text)) {
    if (
      m.group(0) === ",," &&
      match(String.raw`[„\"“]?[^\W\d_]`, text, m.end) &&
      !match(String.raw`[,\w]`, m.index ? text.slice(m.index - 1, m.index) : "")
    ) {
      continue; // reported above as `comma_comma_quote`
    }
    if (search(String.raw`\(\s*$`, before(text, m.index)) || match(String.raw`[,;:. ]*\)`, text, m.end)) continue;
    if (search(`${GREETINGS}$`, before(text, m.index))) continue;
    hits.push(hit("double_punctuation", m.index, m.end, "Two punctuation marks in a row"));
  }
  return hits;
}

function balance(text: string): Hit[] {
  const hits: Hit[] = [];
  const stack: number[] = [];
  for (const m of finditer("[()]", text)) {
    const i = m.index;
    if (text[i] === "(") stack.push(i);
    else if (stack.length) stack.pop();
    else if (!search(String.raw`(?:^|\s|\()(?:[0-9а-яa-zА-ЯA-Z]{1,2}|[ivxlcIVXLC]{1,6})$|[:;]-?$`, before(text, i))) {
      hits.push(hit("unbalanced_bracket", i, i + 1, "A bracket with no partner"));
    }
  }
  for (const i of stack) hits.push(hit("unbalanced_bracket", i, i + 1, "A bracket with no partner"));
  const opened: number[] = [];
  for (const m of finditer(String.raw`[„“”\"]`, text)) {
    if (m.group(0) === "„") opened.push(m.index);
    else if (opened.length) opened.pop();
  }
  for (const i of opened) hits.push(hit("unbalanced_quote", i, i + 1, "„ is never closed"));
  return hits;
}

const DETECTORS = [conjunctions, relatives, adversative, repeated, vocative, splitCompounds, marks, balance];

/** Sorted as the rules sort their findings; a stable sort, as Python's. */
export function byPosition<T extends { start: number; end: number; code: string }>(hits: T[]): T[] {
  return hits.sort((a, b) => a.start - b.start || a.end - b.end || (a.code < b.code ? -1 : a.code > b.code ? 1 : 0));
}

/** Every hit, ordered by position; offsets are into `text`. */
export function check(text: string): Hit[] {
  const normal = normalise(text);
  const hits = DETECTORS.flatMap((detector) => detector(normal)).map((h) =>
    h.fix === null || normal.slice(h.start, h.end) === text.slice(h.start, h.end) ? h : { ...h, fix: null },
  );
  return byPosition(hits);
}
