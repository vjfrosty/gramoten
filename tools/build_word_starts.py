"""Every start of every word form in the two big word lists, for the suggestion search.

    uv run --no-project --python 3.13 --with marisa-trie==1.4.1 python -I tools/build_word_starts.py

The suggestion search asks, letter by letter, whether any known word begins with the
letters built so far. One exact lookup in a trie of every start answers that 3 times as
fast as asking each word list for a key with that prefix. This writes
`gramoten/data/word_starts.marisa`: every start (`к`, `ко`, ..., `котка`) of every form in
`bg_forms.marisa` and `modern_words.marisa`. The text word lists (project words and the
words an app adds) are small, so their starts are made when the checker loads.

Run it after `build_bg_forms.py` and `build_inflections.py`, which rewrite those two
lists; `tests/test_spelling.py` fails while the file is out of date. Built from the
bgOffice dictionary, so it is under MPL-1.1 like it (NOTICE).
"""

from __future__ import annotations

from pathlib import Path

import marisa_trie

DATA = Path(__file__).resolve().parents[1] / "src" / "gramoten" / "data"
OUT = DATA / "word_starts.marisa"


def starts(words) -> set[str]:
    out: set[str] = set()
    for w in words:
        out.update(w[:i] for i in range(1, len(w) + 1))
    return out


def main() -> None:
    words: list[str] = []
    for name in ("bg_forms.marisa", "modern_words.marisa"):
        trie = marisa_trie.Trie()
        trie.load(str(DATA / name))
        words += trie.keys()
    every = starts(words)
    marisa_trie.Trie(sorted(every)).save(str(OUT))
    print(f"{len(every):,} starts of {len(words):,} forms -> {OUT.name}")


if __name__ == "__main__":
    main()
