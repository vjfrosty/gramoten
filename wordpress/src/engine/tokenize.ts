/** Port of `src/gramoten/tokenize.py`: the words of a text, and the ranges no check may touch. */

import { finditer, hasDigit, rx, search } from "./py.ts";

const PROTECTED = String.raw`%%\[.*?\]%%|%%=.*?=%%|%%[^%\s]+%%|\b(?:https?://|www\.)\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+`;

export const INVISIBLE = "­​‌‍⁠﻿̀́";
const STRIP = new RegExp(`[${INVISIBLE}]`, "gv");

const PIECE = String.raw`[^\W_](?:[^\W_]|[${INVISIBLE}])*`;
const TOKEN = `${PIECE}(?:-${PIECE})*`;

export const CYRILLIC = "[Ѐ-ӿ]";
export const LATIN = "[A-Za-z]";

export class Word {
  readonly text: string;
  readonly start: number;
  readonly end: number;

  constructor(text: string, start: number, end: number) {
    this.text = text;
    this.start = start;
    this.end = end;
  }

  /** The word without invisible characters: what the dictionary is asked about. */
  get clean(): string {
    return this.text.replace(STRIP, "");
  }

  get parts(): string[] {
    return this.clean.split("-");
  }

  /** A hyphen part with Cyrillic and Latin letters in it. */
  get mixedScript(): boolean {
    return this.parts.some((p) => search(CYRILLIC, p) !== null && search(LATIN, p) !== null);
  }

  /** Cyrillic letters only: no digit, no Latin, no single letter. */
  get spellable(): boolean {
    const word = this.clean;
    return (
      [...word].length > 1 && !hasDigit(word) && search(LATIN, word) === null && search(CYRILLIC, word) !== null
    );
  }
}

const BEFORE = 200;

/** What comes before `end`, for a search anchored at `$`: see `tokenize.before`. */
export function before(text: string, end: number): string {
  return end <= BEFORE ? text.slice(0, end) : `x${text.slice(end - BEFORE, end)}`;
}

export function protectedRanges(text: string): Array<[number, number]> {
  return finditer(PROTECTED, text, "s").map((m) => [m.index, m.end]);
}

export function tokens(text: string): Word[] {
  const out: Word[] = [];
  const token = rx(TOKEN, "g");
  let cursor = 0;
  for (const [start, end] of [...protectedRanges(text), [text.length, text.length]]) {
    // A slice, as `finditer(text, cursor, start)` ends the string at `start`.
    const piece = text.slice(cursor, start);
    token.lastIndex = 0;
    for (let m = token.exec(piece); m; m = token.exec(piece)) {
      out.push(new Word(m[0], cursor + m.index, cursor + m.index + m[0].length));
    }
    cursor = end;
  }
  return out;
}

/** The tokens a spelling check reads: Cyrillic words, and mixed-script ones to report. */
export function words(text: string): Word[] {
  return tokens(text).filter((t) => t.spellable || t.mixedScript);
}
