/**
 * The word lists the rules read. The host loads them (`load.ts` in the browser, the tests
 * from disk) and hands them over once, with `setData`.
 */

export interface WordTrie {
  readonly size: number;
  has(key: string): boolean;
  /** Every key starting with `prefix`. */
  keys(prefix: string): string[];
  /** One key starting with `prefix`, or `undefined` when none does. */
  firstKey(prefix: string): string | undefined;
}

export interface Data {
  tries: Record<string, WordTrie>;
  /** The text lists, by file name. */
  texts: Record<string, string>;
}

/** The files the checker needs, by kind: `tools/build_data.py` writes them. */
export const TRIE_FILES = [
  "bg_forms.marisa",
  "bg_frequency.marisa",
  "bg_morph.marisa",
  "bg_morph_lemmas.marisa",
  "misspellings.marisa",
  "modern_words.marisa",
  "names.marisa",
] as const;

export const TEXT_FILES = [
  "bg_morph.json",
  "corrections.tsv",
  "eu_words.txt",
  "forbidden_words.txt",
  "gender_extra.tsv",
  "project_words.txt",
  "telecom_words.txt",
  "vocative_words.txt",
] as const;

let current: Data | null = null;
const resets: Array<() => void> = [];

export function setData(data: Data): void {
  current = data;
  for (const reset of resets) reset();
}

export function trie(name: (typeof TRIE_FILES)[number]): WordTrie {
  if (!current) throw new Error("gramoten: setData has not been called");
  return current.tries[name];
}

export function text(name: (typeof TEXT_FILES)[number]): string {
  if (!current) throw new Error("gramoten: setData has not been called");
  return current.texts[name] ?? "";
}

/** `fn`'s result, made once per `setData`: a word list parsed from its file. */
export function once<T>(fn: () => T): () => T {
  let made = false;
  let value: T;
  resets.push(() => {
    made = false;
  });
  return () => {
    if (!made) {
      value = fn();
      made = true;
    }
    return value;
  };
}

/** Registers a cache to empty when the data changes. */
export function onReset(reset: () => void): void {
  resets.push(reset);
}
