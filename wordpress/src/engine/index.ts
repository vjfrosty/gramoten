/**
 * Bulgarian spelling, format and punctuation checks: a TypeScript port of the `gramoten`
 * Python package's `check`, `apply_fixes` and `fix_text`.
 *
 * The Python package is the source of the rules. `tests/difftest.test.ts` runs both over
 * the same texts and fails on any difference, so a rule changed there shows up here.
 */

import * as grammar from "./grammar.ts";
import * as lexical from "./lexical.ts";
import { bulgarian } from "./messages_bg.ts";
import * as mixedScript from "./mixed_script.ts";
import * as orthography from "./orthography.ts";
import { first, isUpper, search } from "./py.ts";
import * as punctuation from "./punctuation.ts";
import { ABBREVIATIONS, type Extra, isCorrect, isName, NO_WORDS, suggest, UNITS } from "./spelling.ts";
import { before, words } from "./tokenize.ts";
import * as typography from "./typography.ts";

export { clearSuggestions, type Extra } from "./spelling.ts";
export { type Data, setData, TEXT_FILES, TRIE_FILES, type WordTrie } from "./data.ts";

export type Kind = "spelling" | "format" | "punctuation" | "grammar";

export interface Issue {
  code: string;
  kind: Kind;
  start: number;
  end: number;
  text: string;
  suggestions: string[];
  /** The replacement for text[start:end] when the writer accepts "Fix". */
  fix: string | null;
  message: string;
  message_bg: string;
  /** Counted in the panel and applied by "Fix all", never underlined. */
  quiet: boolean;
}

const DEEP_SUGGESTIONS_PER_CALL = 20;

function take(left: number[]): boolean {
  if (left[0] <= 0) return false;
  left[0] -= 1;
  return true;
}

function sentenceStart(text: string, start: number): boolean {
  return search(String.raw`(^|[.!?…:;]\s*|[„\"«(]\s*|\n\s*|^\W*)$`, before(text, start)) !== null;
}

function issue(
  text: string,
  code: string,
  kind: Kind,
  start: number,
  end: number,
  suggestions: readonly (string | null | undefined)[],
  fix: string | null,
  message: string,
  quiet = false,
): Issue {
  return {
    code,
    kind,
    start,
    end,
    text: text.slice(start, end),
    // A fix of `""` deletes the span: there is no word to suggest.
    suggestions: suggestions.filter((s): s is string => Boolean(s)),
    fix,
    message,
    message_bg: bulgarian(message),
    quiet,
  };
}

function checkSpelling(text: string, extra: Extra, deep: number[]): Issue[] {
  const found: Issue[] = [];
  for (const word of words(text)) {
    const clean = word.clean;
    if (word.mixedScript) {
      const fixed = mixedScript.fix(word.text);
      found.push(
        issue(text, "mixed_script", "format", word.start, word.end, [fixed], fixed, "Latin and Cyrillic letters mixed in one word"),
      );
    } else if (isUpper(first(clean)) && !isUpper(clean) && !sentenceStart(text, word.start)) {
      // A capital inside a sentence is a name, almost never a typo.
    } else if (
      isName(clean) ||
      UNITS.has(clean.toLowerCase()) ||
      (ABBREVIATIONS.has(clean.toLowerCase()) && text.slice(word.end, word.end + 1) === ".")
    ) {
      // Known as it is.
    } else if (!isCorrect(clean, extra)) {
      found.push(
        issue(
          text,
          "spelling",
          "spelling",
          word.start,
          word.end,
          suggest(clean, 5, extra, take(deep)),
          null,
          "Not in the dictionary",
        ),
      );
    }
  }
  return found;
}

function checkWith(text: string, extra: Extra, deep: number[]): Issue[] {
  const found = checkSpelling(text, extra, deep);
  for (const h of typography.check(text)) {
    found.push(issue(text, h.code, "format", h.start, h.end, [h.fix], h.fix, h.message, typography.QUIET.has(h.code)));
  }
  for (const h of punctuation.check(text)) {
    found.push(issue(text, h.code, "punctuation", h.start, h.end, [h.fix], h.fix, h.message));
  }
  for (const h of [...lexical.check(text), ...grammar.check(text)]) {
    found.push(issue(text, h.code, "grammar", h.start, h.end, [h.fix], h.fix, h.message));
  }
  for (const h of orthography.check(text)) {
    const kind = h.code === "pronoun_i" ? "grammar" : "format";
    found.push(issue(text, h.code, kind, h.start, h.end, [h.fix], h.fix, h.message));
  }
  return punctuation.byPosition(found);
}

/** Spelling, format and punctuation of one text, ordered by position. */
export function check(text: string, extra: Extra = NO_WORDS): Issue[] {
  return checkWith(text, extra, [DEEP_SUGGESTIONS_PER_CALL]);
}

/** `check` of each text, sharing the limit on the two-edit suggestion search. */
export function checkMany(texts: readonly string[], extra: Extra = NO_WORDS): Issue[][] {
  const deep = [DEEP_SUGGESTIONS_PER_CALL];
  return texts.map((text) => checkWith(text, extra, deep));
}

/** `text` with the fix of every issue that carries one applied; see `apply_fixes`. */
export function applyFixes(text: string, issues: readonly Issue[], codes?: ReadonlySet<string>): string {
  const chosen: Issue[] = [];
  let end = -1;
  const ordered = [...issues].sort((a, b) => a.start - b.start || a.end - b.end);
  for (const i of ordered) {
    if (i.fix === null || (codes && !codes.has(i.code))) continue;
    if (text.slice(i.start, i.end) !== i.text || i.start < end) continue;
    chosen.push(i);
    end = i.end;
  }
  let out = text;
  for (const i of chosen.reverse()) out = out.slice(0, i.start) + i.fix + out.slice(i.end);
  return out;
}

const FIX_ROUNDS = 5;

/** `text` with every certain fix applied, checking again until nothing changes. */
export function fixText(text: string, extra: Extra = NO_WORDS, codes?: ReadonlySet<string>): string {
  let out = text;
  for (let round = 0; round < FIX_ROUNDS; round++) {
    const fixed = applyFixes(out, check(out, extra), codes);
    if (fixed === out) break;
    out = fixed;
  }
  return out;
}
