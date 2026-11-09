/** Port of `src/gramoten/orthography.py`: numbers, abbreviations and ѝ, by rule. */

import type { Hit } from "./lexical.ts";
import { analyse } from "./morphology.ts";
import { capitalize, finditer, fullmatch, lstrip, match, search, startsWithAny, toInt } from "./py.ts";
import { byPosition } from "./punctuation.ts";

const MONTHS = ["януари", "февруари", "март", "април", "май", "юни", "юли", "август", "септември", "октомври", "ноември", "декември"];
const NUMBER_ADJECTIVE = `годишн годишен месечн месечен дневн дневен седмичн седмичен часов минутн минутен секундн секунден
метров километров етажн етажен звезд стаен стайн литров кратн кратен степенн степенен членн членен томн томен
инчов ядрен процентн процентен сантиметров килограмов гигабайтов`.split(/\s+/);
const REFERENCE = String.raw`(?:параграф|член|чл\.|точка|т\.|алинея|ал\.|буква|раздел|глава|приложение)\s*$`;
const NUMBER_WORDS = "едно дву три четири пет шест седем осем девет десет двадесет тридесет сто хиляд".split(" ");
const VOWELS = "аеиоуъюяѝ";
const NOT_ORDINAL: ReadonlySet<string> = new Set(["те", "ма", "мата", "мина", "на", "ина", "ки", "ица"]);
const ORDINAL_ENDING = "[врмт]?(?:ият|ия|ата|ото|ите|ят|и|а|о|я)";

function hit(code: string, start: number, end: number, message: string, fix: string | null): Hit {
  return { code, start, end, message, fix };
}

const HEADS: Record<string, string> = { "1": "в", "2": "р", "3": "т", "4": "т" };

/** The consonant an ordinal suffix starts with after these digits: `в`, `р`, `т`, or none. */
function expectedHead(number: string): string {
  const tens = toInt(number.length > 1 ? number.slice(-2) : number) % 100;
  if (tens >= 11 && tens <= 19) return "";
  return HEADS[number[number.length - 1]] ?? "";
}

function pronoun(text: string): Hit[] {
  return finditer(String.raw`(?<![\w-])й(?![\w-])`, text).map((m) =>
    hit("pronoun_i", m.index, m.end, "The pronoun is written „ѝ“", "ѝ"),
  );
}

/** Whether the next word is a singular noun or adjective, so a `-ма` before it is an ordinal. */
function singularNext(after: string): boolean {
  const m = match("([а-яА-Я]+)", after);
  const readings = m ? analyse(m.group(1)) : [];
  return readings.length > 0 && readings.every((r) => r.tag.n === "s" && (r.tag.pos === "N" || r.tag.pos === "A"));
}

function ordinals(text: string): Hit[] {
  const hits: Hit[] = [];
  const months = MONTHS.join("|");
  for (const m of finditer(String.raw`(?<![\w.,/-])(\d{1,2})(?:ви|ри|ти|ми|и)(?=\s+(?:${months})(?![а-я]))`, text, "i")) {
    hits.push(hit("ordinal_date", m.index, m.end, "A day before the month takes no suffix", m.group(1)));
  }
  for (const m of finditer(String.raw`(?<![\w.,/-])(\d{1,4})-([а-я]{1,4})(?![\w-])`, text)) {
    const number = m.group(1);
    const suffix = m.group(2);
    const after = lstrip(text.slice(m.end, m.end + 12));
    if (startsWithAny(after.toLowerCase(), MONTHS)) {
      hits.push(hit("ordinal_date", m.index, m.end, "A day before the month takes no suffix", number));
      continue;
    }
    const head = expectedHead(number);
    const lastDigit = number[number.length - 1];
    if ((suffix === "ма" || suffix === "мата") && (lastDigit === "7" || lastDigit === "8") && singularNext(after)) {
      const ending = suffix.slice(1);
      hits.push(hit("ordinal_suffix", m.index, m.end, `After ${number} the ordinal takes one letter: ${number}-${ending}`, `${number}-${ending}`));
      continue;
    }
    if (NOT_ORDINAL.has(suffix) || !fullmatch(ORDINAL_ENDING, suffix)) continue;
    if (suffix === "ят" || suffix === "я" || ((suffix === `${head}ят` || suffix === `${head}я`) && head)) {
      const right = `${head}и${head && suffix.startsWith(head) ? suffix.slice(head.length) : suffix}`;
      hits.push(hit("ordinal_suffix", m.index, m.end, `The ordinal's article: ${number}-${right}`, `${number}-${right}`));
      continue;
    }
    if (!head && !VOWELS.includes(suffix[0]) && suffix.length > 1 && VOWELS.includes(suffix[1])) {
      hits.push(
        hit("ordinal_suffix", m.index, m.end, `After ${number} the ordinal takes one letter: ${number}-${suffix.slice(1)}`, `${number}-${suffix.slice(1)}`),
      );
    } else if (head && VOWELS.includes(suffix[0])) {
      hits.push(hit("ordinal_suffix", m.index, m.end, `After ${number} the ordinal takes „${head}“: ${number}-${head}${suffix}`, `${number}-${head}${suffix}`));
    }
  }
  for (const m of finditer(String.raw`(?<![\w-])([IVXLC]{1,8})-(ви|ри|ти|ми|и|ия|ият|та|ата|то)(?![\w-])`, text)) {
    hits.push(hit("ordinal_roman", m.index, m.end, "A Roman numeral takes no suffix", m.group(1)));
  }
  return hits;
}

function numberAdjectives(text: string): Hit[] {
  const hits: Hit[] = [];
  const stems = [...new Set(NUMBER_ADJECTIVE)].sort((a, b) => b.length - a.length).join("|");
  for (const m of finditer(String.raw`(?<![\w.,:-])(\d{1,4}) ((?:${stems})[а-я]*)(?![\w-])`, text)) {
    if (search(REFERENCE, text.slice(Math.max(0, m.index - 20), m.index), "i")) continue;
    const noun = match(String.raw`\s+([а-яА-Я]+)`, text.slice(m.end, m.end + 40));
    if (noun && analyse(noun.group(1)).some((r) => r.tag.n === "c")) continue; // the number counts the noun
    hits.push(hit("number_adjective", m.index, m.end, "A number and this adjective are joined by a hyphen", `${m.group(1)}-${m.group(2)}`));
  }
  const numbers = NUMBER_WORDS.join("|");
  for (const m of finditer(String.raw`(?<![\w-])((?:${numbers})[а-я]*)-((?:${numbers}|${stems})[а-я]*)(?![\w-])`.replace(`${numbers}|${stems}`, stems), text, "i")) {
    if (!startsWithAny(m.group(1).toLowerCase(), NUMBER_WORDS)) continue;
    hits.push(hit("number_adjective", m.index, m.end, "Written as one word", m.group(1) + m.group(2)));
  }
  return hits;
}

const PERCENT_ENDINGS: Record<string, string> = {
  на: "процентна",
  ен: "процентен",
  но: "процентно",
  ни: "процентни",
  ната: "процентната",
  ния: "процентния",
  ният: "процентният",
  ното: "процентното",
  ните: "процентните",
};

function percent(text: string): Hit[] {
  const endings = Object.keys(PERCENT_ENDINGS).sort((a, b) => b.length - a.length).join("|");
  return finditer(String.raw`(?<![\w.,])(\d{1,4}(?:,\d+)?) ?%-(${endings})(?![\w-])`, text).map((m) =>
    hit("percent_adjective", m.index, m.end, "Write the percentage adjective out", `${m.group(1)}-${PERCENT_ENDINGS[m.group(2)]}`),
  );
}

function titles(text: string): Hit[] {
  return finditer(String.raw`(?<![\w-])([Гг]-н|[Гг]-жа|[Гг]-ца|[Дд]-р)\.(?= [А-ЯA-Z])`, text).map((m) =>
    hit("title_period", m.index, m.end, `„${m.group(1)}“ takes no full stop`, m.group(1)),
  );
}

const WEEKDAYS = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"];
const DATE_PREPOSITIONS = ["през", "от", "до", "в", "във", "за", "след", "преди", "около"];
/** `Август` (the emperor) and `Септември` (a club, a town) are names after any word but `през`. */
const NAMES_TOO = ["август", "септември"];
const DATE_CAPITAL =
  String.raw`(?:(?<![\w.,/-])\d{1,2}[ \xa0]+(${MONTHS.map(capitalize).join("|")})` +
  String.raw`|(?<![\w-])(?:${DATE_PREPOSITIONS.join("|")}) (${[...MONTHS, ...WEEKDAYS]
    .filter((w) => !NAMES_TOO.includes(w))
    .map(capitalize)
    .join("|")})` +
  String.raw`|(?<![\w-])през (${NAMES_TOO.map(capitalize).join("|")}))(?![\w-])`;

function countOf(text: string, ch: string, end: number): number {
  let n = 0;
  for (let i = text.indexOf(ch); i !== -1 && i < end; i = text.indexOf(ch, i + 1)) n++;
  return n;
}

/** `5 Януари`, `през Май`, `в Понеделник` → lower case; never inside „…“. */
function dateCapitals(text: string): Hit[] {
  const hits: Hit[] = [];
  for (const m of finditer(DATE_CAPITAL, text)) {
    const group = [1, 2, 3].find((g) => m.group(g)) as number;
    if (countOf(text, "„", m.index) > countOf(text, "“", m.index) + countOf(text, "”", m.index)) continue;
    if (text.slice(m.end, m.end + 6) === " пазар") continue; // `Събота пазар`: a place
    hits.push(
      hit("date_capital", m.start(group), m.stop(group), "Months and days of the week are written in lower case", m.group(group).toLowerCase()),
    );
  }
  return hits;
}

const DETECTORS = [pronoun, ordinals, numberAdjectives, percent, titles, dateCapitals];

export function check(text: string): Hit[] {
  return byPosition(DETECTORS.flatMap((detector) => detector(text)));
}
