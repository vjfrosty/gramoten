/** The word lists over HTTP, for the browser. */

import { Trie } from "marisa-trie-wasm";

import { type Data, TEXT_FILES, TRIE_FILES, type WordTrie } from "./engine/index.ts";

function adapt(trie: Trie): WordTrie {
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

async function get(url: string): Promise<Response> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response;
}

/** Every list, from `base` (with a final slash); `version` keeps a stale cache out after an update. */
export async function loadData(base: string, version: string): Promise<Data> {
  const url = (name: string): string => `${base}${name}?ver=${encodeURIComponent(version)}`;
  const [tries, texts] = await Promise.all([
    Promise.all(
      TRIE_FILES.map(async (name) => {
        const response = await get(url(name));
        return [name, adapt(await Trie.load(await response.arrayBuffer()))] as const;
      }),
    ),
    Promise.all(
      TEXT_FILES.map(async (name) => {
        const response = await get(url(name));
        return [name, await response.text()] as const;
      }),
    ),
  ]);
  return { tries: Object.fromEntries(tries), texts: Object.fromEntries(texts) };
}
