/**
 * The port against the Python package: same findings, same fixes, on every text of
 * `corpus.json` (`make_corpus.py`). Run with `npm test`.
 */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { check, clearSuggestions, fixText, type Issue, setData } from "../src/engine/index.ts";
import { loadData } from "./node_data.ts";

const CORPUS = join(dirname(fileURLToPath(import.meta.url)), "corpus.json");

interface Entry {
  text: string;
  extra: string[];
  issues: Issue[];
  fixed: string;
}

/** Python's `grammar.check` orders equal positions by a set's order: compare as a sorted list. */
const canon = (issues: Issue[]): string[] => issues.map((i) => JSON.stringify(i, Object.keys(i).sort())).sort();

test("every finding and fix matches the Python package", { skip: !existsSync(CORPUS) }, async () => {
  setData(await loadData());
  const corpus = JSON.parse(readFileSync(CORPUS, "utf-8")) as Entry[];
  const failures: string[] = [];
  let compared = 0;
  for (const item of corpus) {
    const extra = new Set(item.extra);
    clearSuggestions();
    const actual = canon(check(item.text, extra));
    const expected = canon(item.issues);
    compared += expected.length;
    if (JSON.stringify(actual) !== JSON.stringify(expected)) {
      const onlyPy = expected.filter((x) => !actual.includes(x));
      const onlyTs = actual.filter((x) => !expected.includes(x));
      failures.push(`TEXT ${JSON.stringify(item.text.slice(0, 160))}\n  python only: ${onlyPy.join("\n    ")}\n  ts only: ${onlyTs.join("\n    ")}`);
    }
    const fixed = fixText(item.text, extra);
    if (fixed !== item.fixed) {
      failures.push(`FIX ${JSON.stringify(item.text.slice(0, 160))}\n  python: ${JSON.stringify(item.fixed.slice(0, 200))}\n  ts:     ${JSON.stringify(fixed.slice(0, 200))}`);
    }
  }
  console.log(`${corpus.length} texts, ${compared} findings compared, ${failures.length} differences`);
  assert.equal(failures.length, 0, failures.slice(0, 15).join("\n\n"));
});
