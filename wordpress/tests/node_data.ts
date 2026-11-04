/** The word lists from `plugin/data/`, for the tests and timing scripts under Node. */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { Trie } from "marisa-trie-wasm";

import { type Data, TEXT_FILES, TRIE_FILES, type WordTrie } from "../src/engine/index.ts";

export const DATA_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "plugin", "data");

export function adapt(trie: Trie): WordTrie {
  return {
    size: trie.size,
    has: (key) => trie.lookup(key) !== null,
    keys: (prefix) => Array.from(trie.predictiveSearch(prefix), ([, key]) => key),
    firstKey: (prefix) => {
      for (const [, key] of trie.predictiveSearch(prefix)) return key;
      return undefined;
    },
  };
}

export async function loadData(): Promise<Data> {
  const tries: Data["tries"] = {};
  for (const name of TRIE_FILES) {
    const file = readFileSync(join(DATA_DIR, name));
    tries[name] = adapt(await Trie.load(file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength)));
  }
  const texts: Data["texts"] = {};
  for (const name of TEXT_FILES) texts[name] = readFileSync(join(DATA_DIR, name), "utf-8");
  return { tries, texts };
}
