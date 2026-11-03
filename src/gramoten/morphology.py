"""Bulgarian morphology: a word form's readings, and a lemma's forms.

Built by `tools/morphology/hunspell_morph.py` from the bgOffice spell-check
dictionary (`tools/bg_BG/`, taken under MPL-1.1) and gramoten's own list of
pronouns, numerals and other closed word classes. The Hunspell file gives each
word's forms; the tags are worked out from how those forms relate (see the
builder). Every form from the dictionary is a form the spelling check knows; the
own list adds a few it does not (colloquial numerals such as `двайсет`, `ѝ`).

* `data/bg_morph.marisa`: the keys `form \\x01 lemma \\x02 tag` (lemma and tag
  index in hex): a form's readings are one prefix search.
* `data/bg_morph.json`: the tags.
* `data/bg_morph_lemmas.marisa`: each lemma's base form, part of speech and stem
  (the start its forms share, or the list of its forms where they share less than
  2 letters), as the keys `index  base  pos  stem`, so a lemma's forms
  are a prefix search too. A trie loads in milliseconds; 64,000 lemmas as JSON took
  80 ms and 15 MB.

A tag is `POS|feat=val|...`: POS `N` noun, `Np` name, `Nm` month, `A` adjective,
`V` verb, `P…` pronouns, `Mc`/`Mo` numerals, `R` preposition, `C` conjunction,
`T` particle; features `g` gender (m/f/n), `n` number (s/p/c, c the count form),
`d` definiteness (i/h/f/d: none, short, full, definite), `p` person, `v` tense or
participle, `voc` vocative, `case`, `clitic`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from functools import lru_cache

import marisa_trie

from ._data import DATA


class Lemmas(Sequence):
    """Every lemma as `[base, pos, stem]`, by index, read from a trie on demand."""

    def __init__(self, trie: marisa_trie.Trie) -> None:
        self._trie = trie

    def __len__(self) -> int:
        return len(self._trie)

    @lru_cache(maxsize=20_000)  # noqa: B019 - one instance, kept for the process
    def __getitem__(self, index: int) -> list:  # type: ignore[override]
        if not 0 <= index < len(self._trie):
            raise IndexError(index)
        key = next(self._trie.iterkeys(f"{index:x}"))
        _, base, pos, stem = key.split("")
        return [base, pos, stem[1:].split("") if stem.startswith("") else stem]

    def __iter__(self) -> Iterator[list]:
        return (self[i] for i in range(len(self)))


@lru_cache(maxsize=1)
def _data() -> tuple[marisa_trie.Trie, list[str], Lemmas]:
    trie = marisa_trie.Trie()
    trie.load(str(DATA / "bg_morph.marisa"))
    lemmas = marisa_trie.Trie()
    lemmas.load(str(DATA / "bg_morph_lemmas.marisa"))
    tags = json.loads((DATA / "bg_morph.json").read_text(encoding="utf-8"))["tags"]
    return trie, tags, Lemmas(lemmas)


@lru_cache(maxsize=1024)
def parse_tag(tag: str) -> dict[str, str]:
    parts = tag.split("|")
    out = dict(part.split("=") for part in parts[1:])
    out["pos"] = parts[0]
    return out


class Reading(tuple):
    """`(lemma index, tag index, tag dict)`."""

    __slots__ = ()
    lemma = property(lambda self: self[0])
    slot = property(lambda self: self[1])
    tag = property(lambda self: self[2])

    @property
    def base(self) -> str:
        return _data()[2][self[0]][0]


@lru_cache(maxsize=50_000)
def analyse(word: str) -> tuple[Reading, ...]:
    """Every reading of a word form, looked up lowercased; `()` for an unknown word."""
    trie, tags, _ = _data()
    out = []
    for key in trie.keys(word.lower() + "\x01"):
        lemma, _, index = key[key.index("\x01") + 1 :].partition("\x02")
        out.append(Reading((int(lemma, 16), int(index, 16), dict(parse_tag(tags[int(index, 16)])))))
    return tuple(sorted(out, key=lambda r: (r[0], r[1])))


@lru_cache(maxsize=20_000)
def forms(lemma: int) -> dict[str, list[str]]:
    """`{tag: [forms]}` of a lemma."""
    trie, tags, lemmas = _data()
    stem = lemmas[lemma][2]
    candidates = [trie.keys(f + "\x01") for f in stem] if isinstance(stem, list) else [trie.keys(stem)]
    mark = f"\x01{lemma:x}\x02"
    out: dict[str, list[str]] = {}
    for key in sorted(k for found in candidates for k in found):
        form, sep, index = key.partition(mark)
        if sep:
            out.setdefault(tags[int(index, 16)], []).append(form)
    return out


def inflect(lemma: int, **want: str) -> list[str]:
    """The lemma's forms whose tag has every feature asked for (`g="m", n="s", d="f"`)."""
    out: list[str] = []
    for tag, found in forms(lemma).items():
        features = parse_tag(tag)
        if all(features.get(k) == v for k, v in want.items()):
            out += [f for f in found if f not in out]
    return out
