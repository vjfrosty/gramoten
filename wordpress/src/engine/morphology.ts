/** Port of `src/gramoten/morphology.py`: a word form's readings, and a lemma's forms. */

import { once, onReset, text, trie } from "./data.ts";
import { memo } from "./py.ts";

export type Tag = Record<string, string | undefined>;

export interface Reading {
  readonly lemma: number;
  readonly slot: number;
  readonly tag: Tag;
  readonly base: string;
}

const tags = once(() => JSON.parse(text("bg_morph.json")).tags as string[]);

type Lemma = readonly [base: string, pos: string, stem: string | string[]];

const lemmaAt = memo((index: number): Lemma => {
  const key = trie("bg_morph_lemmas.marisa").firstKey(`${index.toString(16)}\x01`);
  if (key === undefined) throw new RangeError(`no lemma ${index}`);
  const [, base, pos, stem] = key.split("\x01");
  return [base, pos, stem.startsWith("\x02") ? stem.slice(1).split("\x02") : stem];
}, 20_000);

const parsed = memo((tag: string): Tag => {
  const parts = tag.split("|");
  const out: Tag = {};
  for (const part of parts.slice(1)) {
    const [name, value] = part.split("=");
    out[name] = value;
  }
  out.pos = parts[0];
  return out;
}, 1024);

export const parseTag = parsed;

/** Every reading of a word form, looked up lowercased; none for an unknown word. */
export const analyse = memo((word: string): readonly Reading[] => {
  const all = tags();
  const out = trie("bg_morph.marisa")
    .keys(`${word.toLowerCase()}\x01`)
    .map((key): Reading => {
      const rest = key.slice(key.indexOf("\x01") + 1);
      const at = rest.indexOf("\x02");
      const lemma = Number.parseInt(rest.slice(0, at), 16);
      const slot = Number.parseInt(rest.slice(at + 1), 16);
      return {
        lemma,
        slot,
        tag: parsed(all[slot]),
        get base() {
          return lemmaAt(lemma)[0];
        },
      };
    });
  return out.sort((a, b) => a.lemma - b.lemma || a.slot - b.slot);
}, 50_000);

/** `{tag: [forms]}` of a lemma. */
export const forms = memo((lemma: number): Map<string, string[]> => {
  const all = tags();
  const morph = trie("bg_morph.marisa");
  const stem = lemmaAt(lemma)[2];
  const keys = Array.isArray(stem) ? stem.flatMap((f) => morph.keys(`${f}\x01`)) : morph.keys(stem);
  const mark = `\x01${lemma.toString(16)}\x02`;
  const out = new Map<string, string[]>();
  for (const key of keys.sort()) {
    const at = key.indexOf(mark);
    if (at < 0) continue;
    const tag = all[Number.parseInt(key.slice(at + mark.length), 16)];
    const list = out.get(tag);
    if (list) list.push(key.slice(0, at));
    else out.set(tag, [key.slice(0, at)]);
  }
  return out;
}, 20_000);

/** The lemma's forms whose tag has every feature asked for. */
export function inflect(lemma: number, want: Record<string, string | undefined>): string[] {
  const out: string[] = [];
  for (const [tag, found] of forms(lemma)) {
    const features = parsed(tag);
    if (Object.entries(want).every(([k, v]) => features[k] === v)) {
      for (const f of found) if (!out.includes(f)) out.push(f);
    }
  }
  return out;
}

for (const cache of [lemmaAt, parsed, analyse, forms]) onReset(cache.clear);
