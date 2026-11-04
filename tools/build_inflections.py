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

The articled plural follows from the plural, so it is kept even when text never
used it (`антивируси` -> `антивирусите`, `събития` -> `събитията`): when the plural
is used 5 times or listed, or when a masculine noun's -и plural and -ът article are
both listed (`брандинги`, `брандингът`). A misspelt listed word belongs in
`corrections.tsv`, which keeps it and so its articled plural out.

The added words are the modern words and the project, telecom and EU lists. The
models for each ending are worked out once for all the words that share it, so the
whole build takes about a minute and a half.

The modern words are read from DOWNLOADS/modern_words_base.marisa, written by
`build_modern_words.py`; `gramoten/data/modern_words.marisa` is rewritten as those
words and the forms made here, one list, so the checker loads one file. Run this after
`build_modern_words.py`. The paradigms come from the bgOffice dictionary, so that file
is under MPL-1.1 like it (NOTICE).
"""

from __future__ import annotations

import heapq
import sys
import time
from functools import cache
from pathlib import Path

STARTED = time.perf_counter()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import marisa_trie  # noqa: E402

from gramoten import morphology, spelling  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_modern_words import COLLOQUIAL, LEIPZIG, glued_ne, leipzig_counts, web_counts  # noqa: E402

OUT = ROOT / "src" / "gramoten" / "data" / "modern_words.marisa"
BASE = "modern_words_base.marisa"
OPEN = ("N", "A", "V")
#: Made forms that are no forms, though text uses them: a vocative a thing never takes
#: (`кардо`, `колцо`), a cut-off word (`уебсайте`), dialect pronouns (`ниедните`, `тогазите`).
NOT_FORMS = frozenset({"кардо", "колцо", "уебсайте", "ниедните", "ньедните", "неквите", "тогазите"})
#: How often text must use a made plural for its articled form to be added unused.
ATTESTED_PLURAL = 5
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
    """The added words: modern words and the hand-made lists: project, telecom and EU
    words (not abbreviations)."""
    words = set(modern.keys()) | {
        w
        for name in ("project_words.txt", "telecom_words.txt", "eu_words.txt")
        for w in spelling._read_words(name)
        if len(w) >= 4
    }
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
    print(f"counts read in {time.perf_counter() - STARTED:.0f} s")
    trie, tags, _ = morphology._data()
    # Whether a form has a noun, adjective or verb reading, read off the trie keys
    # (`form \x01 lemma \x02 tag`) instead of analysing each of the 864,000 forms again.
    open_tag = [tag.split("|", 1)[0] in OPEN for tag in tags]
    open_forms: dict[str, bool] = {}
    for key in trie:
        form, _, rest = key.partition("\x01")
        if set(form) <= WORD:
            open_forms[form] = open_forms.get(form, False) or open_tag[int(rest.partition("\x02")[2], 16)]
    reversed_forms = marisa_trie.Trie(f[::-1] for f, ok in open_forms.items() if ok)
    forbidden = spelling.forbidden_words()

    @cache
    def models_ending(ending: str) -> list[str]:
        """The most frequent known forms with this ending, worked out once for all the words
        that share it. `nsmallest` is `sorted(...)[:n]`, ties in the same order; one more
        than needed, so a word that is a model itself can be left out."""
        found = [m[::-1] for m in reversed_forms.keys(ending[::-1])]
        return heapq.nsmallest(MODELS_PER_ENDING + 1, found, key=lambda m: -spelling._count(m))

    @cache
    def model_forms(model: str) -> tuple[str, ...]:
        reading = next(r for r in morphology.analyse(model) if r.tag["pos"] in OPEN)
        return tuple(form for found in morphology.forms(reading.lemma).values() for form in found)

    def paradigm(word: str, model: str, k: int) -> set[str]:
        start, new_start = model[:-k], word[:-k]
        return {new_start + form[len(start) :] for form in model_forms(model) if form.startswith(start)}

    @cache
    def model_plurals(model: str) -> tuple[tuple[str, str], ...]:
        """(plural, articled plural) of a noun or adjective model: `кандидати`, `кандидатите`."""
        reading = next(r for r in morphology.analyse(model) if r.tag["pos"] in OPEN)
        forms = morphology.forms(reading.lemma)
        return tuple(
            (plain, articled)
            for tag, found in forms.items()
            if tag.split("|", 1)[0] in ("N", "A") and "n=p" in tag.split("|") and "d=i" in tag.split("|")
            for plain in found
            for articled in forms.get(tag.replace("d=i", "d=d"), ())
        )

    def plurals(word: str, model: str, k: int) -> list[tuple[str, str]]:
        """The word's (plural, articled plural) by the model. A plural in -а/-я takes -та only
        after a neuter singular (`събитие`, `звено`, `шоу`): a feminine word on a neuter
        model would give its own singular (`анонимизирана`, `-ната`)."""
        start, new_start = model[:-k], word[:-k]
        out = []
        for plain, articled in model_plurals(model):
            if not (plain.startswith(start) and articled.startswith(start)):
                continue
            plain, articled = new_start + plain[len(start) :], new_start + articled[len(start) :]
            masculine_or_feminine = plain[-1] in "ие" and articled == plain + "те"
            neuter = plain[-1] in "ая" and articled == plain + "та" and word[-1] in "оеюуи"
            if masculine_or_feminine or neuter:
                out.append((plain, articled))
        return out

    made: set[str] = set()
    plural_pairs: list[tuple[str, str]] = []
    for word in sources(base):
        # Every model sharing an ending of 3+ letters is tried, the most frequent first; the
        # one whose forms real text uses most wins (a longer ending on a tie). `ламинат`
        # takes a noun, whose `ламинатът`, `ламинатите` are used, not the verb `преминат`.
        best, best_score, best_model = set(), 0, None
        for k in range(min(MAX_ENDING, len(word) - 2), MIN_ENDING - 1, -1):
            models = [m for m in models_ending(word[-k:]) if m != word][:MODELS_PER_ENDING]
            for model in models:
                forms = paradigm(word, model, k)
                score = sum(1 for f in forms if f != word and used[f] >= MIN_USES)
                if score > best_score:
                    best, best_score, best_model = forms, score, (model, k)
        made |= {f for f in best if used[f] >= MIN_USES and f not in NOT_FORMS}
        if best_model:
            plural_pairs += plurals(word, *best_model)
    print(f"paradigms done in {time.perf_counter() - STARTED:.0f} s")
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

    # The articled plural follows from the plural (`антивируси` -> `антивирусите`), so it is
    # kept when the plural is, though text never used it: a rare noun's articled plural
    # seldom turns up. The typo and cut-off guards weigh how often text uses a form, so they
    # are not applied: the plural passed them or is a listed word. A misspelt listed word
    # belongs in corrections.tsv, which keeps out its plural and so its articled plural.
    # A masculine noun whose -и plural and -ът article are both listed takes -ите, whatever
    # model its forms came from (`брандинги`, `брандингът` -> `брандингите`): the two forms
    # are the evidence, so the plural need not be used 5 times.
    listed = set(base.keys()) | made | spelling.project_words()
    by_article = {
        (f, f + "те")
        for f in listed
        if f.endswith("и")
        and f[-2] not in "аеиоуъюя"
        and (f[:-1] + "ът" in listed or spelling.in_dictionary(f[:-1] + "ът"))
    }
    articled = {
        a
        for p, a in plural_pairs + sorted(by_article)
        if ((p in made and used[p] >= ATTESTED_PLURAL) or spelling.is_correct(p) or (p, a) in by_article)
        and a not in made
        and a not in NOT_FORMS
        and a not in forbidden
        and a not in COLLOQUIAL
        and not glued_ne(a)
        and not spelling.in_dictionary(a)
        and not spelling.is_correct(a)
    }
    # A neuter plural in -а whose stem also takes -и is an adjective's feminine form, made on
    # a noun model (`анонимизирано` like `пиано`: `анонимизираната` is no plural).
    articled = {
        a for a in articled if not (a.endswith("ата") and (a[:-3] + "и" in made or spelling.is_correct(a[:-3] + "и")))
    }
    made |= articled
    print(f"{len(articled):,} articled plurals added by rule")
    marisa_trie.Trie(sorted(set(base.keys()) | made)).save(str(OUT))
    print(f"{len(made):,} forms of {len(sources(base)):,} added words, with the modern words -> {OUT.name}")


if __name__ == "__main__":
    main()
