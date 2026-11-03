"""Every form of the words the dictionary lacks, by the paradigm of a dictionary word.

    uv run --no-project --python 3.13 --with marisa-trie==1.4.1 python -I tools/build_inflections.py DOWNLOADS

The added word lists hold the forms their sources happened to use: `ламинат` and
`ламината`, but not `ламинатът`; `интериорен` but not `интериорна`. Hunspell
spells a word's other forms with affix rules; this does the same with the
dictionary's own paradigms. For each added word it tries the dictionary forms that
share an ending of 3 letters or more with it, and takes the word whose paradigm
gives the added word the most forms real text uses; every form of it that keeps
the start before the ending is made: `ламинат` like `кандидат` gives
`ламинатът`, `ламинати`, `ламинатите`.

Forms are made only from nouns, adjectives and verbs, never from a form the
lists forbid, and never one the dictionary already has. A shared ending is often
chance (`бронзетите` and the verb `взетите`), and the forms it makes are then
nonsense (`бронземелия`). So a made form is kept only when real text uses it at
least twice: the Leipzig news and Wikipedia or the MaCoCu-bg web text in
DOWNLOADS (the folder of `build_modern_words.py`). Nonsense is never used;
`ламинатът` is. Common typos are used too (`разрастна`, `компроментираните`), so a
made form is also dropped when a known word one edit away, other than in its
last two letters, is used 3 times as often (`разрасна`, `служещи`), and when it is
the start of words used 100 times as often (`манипулаци`: a cut-off word).

The modern words are read from DOWNLOADS/modern_words_base.marisa, written by
`build_modern_words.py`; `gramoten/data/modern_words.marisa` is rewritten as those
words and the forms made here, one list, so the checker loads one file. Run this after
`build_modern_words.py`. The paradigms come from the bgOffice dictionary, so that file
is under MPL-1.1 like it (NOTICE).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import marisa_trie  # noqa: E402

from gramoten import morphology, spelling  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_modern_words import COLLOQUIAL, LEIPZIG, glued_ne, leipzig_counts, web_counts  # noqa: E402

OUT = ROOT / "src" / "gramoten" / "data" / "modern_words.marisa"
BASE = "modern_words_base.marisa"
OPEN = ("N", "A", "V")
#: How often real text must use a made form.
MIN_USES = 2
#: A known word one edit away and this many times as used makes a form a likely typo.
TYPO_RATIO = 3
#: A form that begins this many times as many uses of longer words is a cut-off word.
CUT_OFF_RATIO = 100
#: Models tried per shared ending, the most frequent first.
MODELS_PER_ENDING = 12
#: The shortest ending a model must share, and the longest worth trying.
MIN_ENDING, MAX_ENDING = 3, 8
WORD = set("абвгдежзийклмнопрстуфхцчшщъьюяѝ")


def sources(modern: marisa_trie.Trie) -> list[str]:
    """The added words: modern words and the hand-read project words (not abbreviations)."""
    words = set(modern.keys()) | {w for w in spelling._read_words("project_words.txt") if len(w) >= 4}
    return sorted(w for w in words if set(w) <= WORD)


def main() -> None:
    downloads = Path(sys.argv[1])
    # The spelling check reads OUT; only the modern words, not the last run's forms, count as known.
    base = marisa_trie.Trie()
    base.load(str(downloads / BASE))
    base.save(str(OUT))
    spelling._modern.cache_clear()
    (news, _), (wiki, _) = (leipzig_counts(downloads, name) for name in LEIPZIG)
    used = news + wiki + web_counts(downloads)
    trie, _, _ = morphology._data()
    open_forms = {}
    for key in trie:
        form = key[: key.index("\x01")]
        if form not in open_forms and set(form) <= WORD:
            open_forms[form] = any(r.tag["pos"] in OPEN for r in morphology.analyse(form))
    reversed_forms = marisa_trie.Trie(f[::-1] for f, ok in open_forms.items() if ok)
    forbidden = spelling.forbidden_words()

    def paradigm(word: str, model: str, k: int) -> set[str]:
        reading = next(r for r in morphology.analyse(model) if r.tag["pos"] in OPEN)
        start, new_start = model[:-k], word[:-k]
        return {
            new_start + form[len(start) :]
            for found in morphology.forms(reading.lemma).values()
            for form in found
            if form.startswith(start)
        }

    made: set[str] = set()
    for word in sources(base):
        # Every model sharing an ending of 3+ letters is tried, the most frequent first; the
        # one whose forms real text uses most wins (a longer ending on a tie). `ламинат`
        # takes a noun, whose `ламинатът`, `ламинатите` are used, not the verb `преминат`.
        best, best_score = set(), 0
        for k in range(min(MAX_ENDING, len(word) - 2), MIN_ENDING - 1, -1):
            models = [m[::-1] for m in reversed_forms.keys(word[-k:][::-1]) if m[::-1] != word]
            for model in sorted(models, key=lambda m: -spelling._count(m))[:MODELS_PER_ENDING]:
                forms = paradigm(word, model, k)
                score = sum(1 for f in forms if f != word and used[f] >= MIN_USES)
                if score > best_score:
                    best, best_score = forms, score
        made |= {f for f in best if used[f] >= MIN_USES}
    made = {
        f
        for f in made
        if f not in forbidden
        and f not in COLLOQUIAL
        and not glued_ne(f)
        and not spelling.in_dictionary(f)
        and not spelling.is_correct(f)
    }

    def a_typo(form: str) -> bool:
        """A known word one edit away inside the stem (not in the last 2 letters, where endings
        differ: `интериорна`, `интериора`) and 3 times as used (`служащи`, `служещи`)."""
        for w in spelling._edits(form):
            i = next((i for i in range(min(len(w), len(form))) if w[i] != form[i]), min(len(w), len(form)))
            if i < min(len(w), len(form)) - 2 and used[w] >= TYPO_RATIO * used[form] and spelling.is_correct(w):
                return True
        return False

    made = {f for f in made if not a_typo(f)}

    # The cut-off start of a much more used word is no form (`манипулаци`, `компози`):
    # a line break or a truncated snippet, used by chance.
    starts = marisa_trie.Trie(w for w, c in used.items() if c >= 5 and set(w) <= WORD)
    made = {f for f in made if sum(used[w] for w in starts.keys(f) if len(w) > len(f)) < CUT_OFF_RATIO * used[f]}
    marisa_trie.Trie(sorted(set(base.keys()) | made)).save(str(OUT))
    print(f"{len(made):,} forms of {len(sources(base)):,} added words, with the modern words -> {OUT.name}")


if __name__ == "__main__":
    main()
