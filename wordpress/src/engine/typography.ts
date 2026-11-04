/** Port of `src/gramoten/typography.py`: spaces, dashes, quotes, ellipses, prices. */

import { finditer, strip } from "./py.ts";
import { protectedRanges } from "./tokenize.ts";

const NBSP = " ";
const CURRENCY = String.raw`(?:лв\.?|лева|€|евро|EUR|BGN)`;
export const QUIET: ReadonlySet<string> = new Set(["nbsp_number_unit"]);
const UNITS = CURRENCY + String.raw`|%|GB|MB|TB|Mbps|Gbps|Mb/s|Gb/s|ГБ|МБ|мин\.?|мес\.?|г\.|бр\.|SMS|MMS`;

export interface Hit {
  code: string;
  start: number;
  end: number;
  message: string;
  /** null: the finding has no certain correction. */
  fix: string | null;
}

function rules(text: string): Hit[] {
  const out: Hit[] = [];
  const add = (code: string, start: number, end: number, message: string, fix: string | null): void => {
    out.push({ code, start, end, message, fix });
  };
  for (const m of finditer(
    String.raw`(?<![\w.,])(\d{1,3}(?:[  ]\d{3})+|\d+)(?:[.,](\d{1,2}))?[  ]?(лв\.?|лева|BGN)(?![^\W\d_])`,
    text,
  )) {
    add("currency_bgn", m.index, m.end, "A price in leva: prices are in euro", null);
  }
  for (const m of finditer(String.raw`(?<![\w.,])(€|EUR)[  ]?(\d+(?:[  ]\d{3})*(?:[.,]\d{1,2})?)(?!\d)`, text)) {
    add(
      "euro_symbol_position",
      m.index,
      m.end,
      "In Bulgarian the € sign goes after the amount",
      `${strip(m.group(2)).replaceAll(".", ",")} €`,
    );
  }
  for (const m of finditer(String.raw`(?<=\S)( {2,})(?=\S)`, text)) {
    add("double_space", m.start(1), m.stop(1), "More than one space", " ");
  }
  for (const m of finditer(String.raw`(?<=[^\W\d_])( +)([,.!?;:])(?=\s|$)`, text)) {
    add("space_before_punctuation", m.start(1), m.stop(2), "A space before the punctuation mark", m.group(2));
  }
  for (const m of finditer(String.raw`(?<=[А-Яа-я])([,;:!?])(?=[А-Яа-я])`, text)) {
    add("space_after_punctuation", m.start(1), m.stop(1), "No space after the punctuation mark", `${m.group(1)} `);
  }
  for (const m of finditer(String.raw`(?<=[^\W\d_]) - (?=[^\W\d_])`, text)) {
    add("dash", m.index, m.end, "A hyphen used as a dash", " – ");
  }
  for (const m of finditer(String.raw`(?<![\w\"])\"([^\"\n]{1,200}?)\"(?![\w\"])`, text)) {
    add("quotes", m.index, m.end, "Bulgarian quotation marks are „…“", `„${m.group(1)}“`);
  }
  for (const m of finditer(String.raw`(?<!\.)\.\.\.(?!\.)`, text)) {
    add("ellipsis", m.index, m.end, "Three dots are one character: …", "…");
  }
  for (const m of finditer(String.raw`(?<![\d.,])(\d{1,6})\.(\d{2})(?=\s*` + CURRENCY + ")", text)) {
    add("decimal_separator", m.index, m.end, "A price takes a decimal comma", `${m.group(1)},${m.group(2)}`);
  }
  for (const m of finditer(
    String.raw`(?<![\w.,])0([1-9]) (януари|февруари|март|април|май|юни|юли|август|септември|` +
      String.raw`октомври|ноември|декември)(?![^\W\d_])`,
    text,
    "i",
  )) {
    add("date_leading_zero", m.index, m.index + 2, "A day before the month has no leading zero", m.group(1));
  }
  for (const m of finditer(String.raw`(?<![\w.,])(?<!\d[  ])(\d{1,4})(г|в|хил|млн|млрд)\.(?=\s|$|[,;:)–—-])`, text)) {
    add(
      "abbreviation_space",
      m.index,
      m.end,
      "A space between the number and the abbreviation",
      `${m.group(1)} ${m.group(2)}.`,
    );
  }
  for (const m of finditer(String.raw`(?<![\w.,])\d{1,2}\.\d{1,2}\.(\d{4})(г)\.(?=\s|$|[,;:)–—-])`, text)) {
    add(
      "abbreviation_space",
      m.start(1),
      m.end,
      "A space between the number and the abbreviation",
      `${m.group(1)} ${m.group(2)}.`,
    );
  }
  for (const m of finditer(String.raw`(?<![\w.,])(\d[\d,]*) (` + UNITS + String.raw`)(?![^\W\d_])`, text)) {
    add(
      "nbsp_number_unit",
      m.stop(1),
      m.stop(1) + 1,
      "Keep the number and its unit on one line (non-breaking space)",
      NBSP,
    );
  }
  return out;
}

export function check(text: string): Hit[] {
  const ranges = protectedRanges(text);
  return rules(text).filter((hit) => !ranges.some(([start, end]) => hit.start < end && start < hit.end));
}
