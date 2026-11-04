/** Port of `src/gramoten/messages_bg.py`: the Bulgarian wording of every finding's message. */

import { memo, rx } from "./py.ts";

const TABLE: ReadonlyArray<readonly [string, string]> = [
  ["Not in the dictionary", "Думата не е в речника"],
  ["Latin and Cyrillic letters mixed in one word", "Латински и кирилски букви в една дума"],
  ["A price in leva: prices are in euro", "Цена в лева: цените са в евро"],
  ["In Bulgarian the € sign goes after the amount", "На български знакът € се пише след сумата"],
  ["More than one space", "Повече от един интервал"],
  ["A space before the punctuation mark", "Интервал пред препинателния знак"],
  ["No space after the punctuation mark", "Липсва интервал след препинателния знак"],
  ["A hyphen used as a dash", "Дефис вместо тире"],
  ["Bulgarian quotation marks are „…“", "Българските кавички са „…“"],
  ["Three dots are one character: …", "Многоточието е един знак: …"],
  ["A price takes a decimal comma", "Цената се пише с десетична запетая"],
  ["A space between the number and the abbreviation", "Интервал между числото и съкращението"],
  ["A day before the month has no leading zero", "Денят пред месеца се пише без водеща нула"],
  [
    "Keep the number and its unit on one line (non-breaking space)",
    "Числото и мерната единица да са на един ред (непрекъсваем интервал)",
  ],
  ["Comma before the second „нито“", "Запетая пред второто „нито“"],
  ["Comma before „{}“", "Запетая пред „{0}“"],
  ["Comma after the greeting, before the name", "Запетая след поздрава, пред името"],
  ["Set the name off with commas", "Обръщението се отделя със запетаи"],
  ["„{}“ is one conjunction; the comma goes before it", "„{0}“ е един съюз; запетаята е пред него"],
  ["The comma goes before the preposition: „…, {}“", "Запетаята е пред предлога: „…, {0}“"],
  ["Two commas typed for the opening quote „", "Две запетаи вместо отваряща кавичка „"],
  ["Two punctuation marks in a row", "Два препинателни знака един след друг"],
  ["A bracket with no partner", "Скоба без съответна скоба"],
  ["„ is never closed", "Кавичката „ не е затворена"],
  ["After a preposition the word takes the short article (-а/-я)", "След предлог думата е с кратък член (-а/-я)"],
  ["Before в or ф write „във“", "Пред в или ф се пише „във“"],
  ["„във“ goes only before в or ф; here „в“", "„във“ се пише само пред в или ф; тук – „в“"],
  ["Before с or з write „със“", "Пред с или з се пише „със“"],
  ["„със“ goes only before с or з; here „с“", "„със“ се пише само пред с или з; тук – „с“"],
  ["„най-“ is written with a hyphen and no space", "„най-“ се пише с дефис, без интервал"],
  ["„най-“ is written with a hyphen", "„най-“ се пише с дефис"],
  ["Written together: „{}“", "Пише се слято: „{0}“"],
  ["„{}“ twice", "„{0}“ два пъти"],
  ["A range of numbers takes an en dash, no spaces", "Интервал от числа се пише със средно тире, без интервали"],
  ["The pronoun is written „ѝ“", "Местоимението се пише „ѝ“"],
  ["A day before the month takes no suffix", "Датата пред името на месеца се пише без окончание"],
  ["After {} the ordinal takes one letter: {}", "Редното числително след {0} е с една буква: {1}"],
  ["After {} the ordinal takes „{}“: {}", "Редното числително след {0} е с „{1}“: {2}"],
  ["The ordinal's article: {}", "Членът на редното числително е с „и“: {0}"],
  ["A Roman numeral takes no suffix", "Римската цифра се пише без окончание"],
  ["A number and this adjective are joined by a hyphen", "Числото и прилагателното се свързват с дефис"],
  ["Written as one word", "Пише се слято"],
  ["Write the percentage adjective out", "Прилагателното за процент се изписва с думи"],
  ["„{}“ takes no full stop", "„{0}“ се пише без точка"],
  ["Only the first word of the phrase takes the article", "Само първата дума от словосъчетанието се членува"],
  [
    "After „е“ the masculine word takes the full article (-ят/-ът)",
    "След „е“ думата от мъжки род е с пълен член (-ят/-ът)",
  ],
  [
    "After a number a masculine noun takes the count form",
    "След число съществителното от мъжки род е в бройна форма",
  ],
  ["After „{}“ use the plural, not the count form", "След „{0}“ се пише множествено число, а не бройна форма"],
  ["The verb agrees with „Вие“: 2nd person plural", "Глаголът се съгласува с „Вие“: 2 л. мн. ч."],
];

const escapeText = (s: string): string => s.replace(/[\\^$.*+?()[\]{}|/]/g, "\\$&");

const PATTERNS = TABLE.map(([en, bg]) => [rx(`^${en.split("{}").map(escapeText).join("(.+?)")}$`, "s"), bg] as const);

/** The message in Bulgarian, or unchanged when no entry matches it. */
export const bulgarian = memo((message: string): string => {
  for (const [pattern, bg] of PATTERNS) {
    const m = pattern.exec(message);
    if (m) return bg.replace(/\{(\d)\}/g, (_, n: string) => m[Number(n) + 1]);
  }
  return message;
}, 4096);
