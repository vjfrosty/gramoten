"""The word lists for the WordPress plugin, from the Python package's own.

    uv run --group dev python wordpress/tools/build_data.py

Writes `wordpress/plugin/data/`. Everything is copied as it is, but for two changes:

- `bg_frequency.marisa` and `misspellings.marisa` hold binary values, and the WASM trie
  reads keys only as text. Here the value goes into the key: `word \\x01 value`.
- `word_starts.marisa` stays out, to keep the plugin under the WordPress.org limit of
  10 MB. It only answers faster what a prefix search in the other two lists answers.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import marisa_trie

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "gramoten" / "data"
OUT = ROOT / "wordpress" / "plugin" / "data"

COPIED = (
    "bg_forms.marisa",
    "bg_morph.marisa",
    "bg_morph_lemmas.marisa",
    "modern_words.marisa",
    "names.marisa",
    "bg_morph.json",
    "corrections.tsv",
    "eu_words.txt",
    "forbidden_words.txt",
    "gender_extra.tsv",
    "project_words.txt",
    "telecom_words.txt",
    "vocative_words.txt",
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in COPIED:
        shutil.copyfile(SOURCE / name, OUT / name)

    frequency = marisa_trie.RecordTrie("<I")
    frequency.load(str(SOURCE / "bg_frequency.marisa"))
    marisa_trie.Trie([f"{word}\x01{value[0]:x}" for word, value in frequency.items()]).save(
        str(OUT / "bg_frequency.marisa")
    )

    misspellings = marisa_trie.BytesTrie()
    misspellings.load(str(SOURCE / "misspellings.marisa"))
    # `known_correction` takes the first value, and the table has one per word.
    marisa_trie.Trie([f"{w}\x01{misspellings.get(w)[0].decode()}" for w in set(misspellings.keys())]).save(
        str(OUT / "misspellings.marisa")
    )

    total = sum(f.stat().st_size for f in OUT.iterdir())
    print(f"{len(list(OUT.iterdir()))} files, {total / 1e6:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
