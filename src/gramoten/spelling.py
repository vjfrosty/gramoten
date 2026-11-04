"""Bulgarian spelling against every word form of the bg_BG dictionary.

The lowercased forms live in `data/bg_forms.marisa`, built by
`tools/build_bg_forms.py` from bgOffice's Hunspell dictionary (taken under
MPL-1.1; tools/bg_BG/SOURCE.md). No Hunspell engine runs: the trie is far smaller
and faster with the same suggestions.

`data/project_words.txt` adds reviewed modern words (смартфон, рутер, имейл, лв).

Advice only: nothing here changes text or stops an export.
"""

from __future__ import annotations

import math
import threading
from collections import OrderedDict
from functools import lru_cache

import marisa_trie

from ._data import DATA

ALPHABET = "абвгдежзийклмнопрстуфхцчшщъьюя"

#: Words two edits away are added when fewer than this many are one edit away.
FILL_TO = 5
#: A safety limit for the two-edit search, in word starts looked up: a word needs
#: 10,000-16,000 (15-30 ms). A count, not a time, so the result never depends on
#: how fast the machine is.
SECOND_EDIT_STEPS = 100_000

#: Spellings that sound alike, or nearly, in Bulgarian, each way round: reduced
#: unstressed vowels (`а/ъ`, `о/у`, `е/и`), the `я/е` alternation, voiced and voiceless
#: consonants (`д/т`, `з/с`), `я`, `ю` and `щ` spelt out by sound (`йа`, `йу`, `шт`),
#: `ия` heard as `еъ`, `иа` as `я` (`милярд`), a `т` or `д` lost between consonants
#: (`честно` as `чесно`, `площта` as `площа`, `чувствам` as `чуствам`), and clusters
#: that sound as one consonant: `дс`/`тс` as `ц` (`адски` as `ацки`), `жт` as `щ`
#: (`вижте` as `вище`), `хв` as `ф` (`хвърлям`), `ст` as `з` before a voiced consonant
#: (`гозба`), `вз` as `з` (`взема`).
SOUND_ALIKE = (
    ("а", "ъ"), ("о", "у"), ("е", "и"), ("е", "я"), ("я", "ъ"), ("я", "а"), ("ю", "у"),
    ("б", "п"), ("в", "ф"), ("г", "к"), ("д", "т"), ("ж", "ш"), ("з", "с"), ("и", "й"),
    ("я", "йа"), ("я", "йъ"), ("ю", "йу"), ("щ", "шт"), ("ьо", "йо"),
    ("ия", "еъ"), ("ия", "иъ"), ("ия", "ийъ"), ("ия", "еа"), ("иа", "я"), ("еи", "ей"),
    ("стн", "сн"), ("здн", "зн"), ("ст", "с"), ("щт", "щ"), ("вств", "ств"), ("вств", "св"),
    ("дс", "ц"), ("тс", "ц"), ("жт", "щ"), ("хв", "ф"), ("ст", "з"), ("вз", "з"), ("стч", "шч"),
)  # fmt: skip
#: What a sound-alike spelling becomes, by what is written: the pairs above both ways,
#: and every letter doubled or undoubled (`мисъл`/`ммисъл`, `оттам`/`отам`).
_SOUND_REWRITES: dict[str, tuple[str, ...]] = {}
for _a, _b in SOUND_ALIKE:
    _SOUND_REWRITES[_a] = (*_SOUND_REWRITES.get(_a, ()), _b)
    _SOUND_REWRITES[_b] = (*_SOUND_REWRITES.get(_b, ()), _a)
for _c in ALPHABET:
    _SOUND_REWRITES[_c + _c] = (*_SOUND_REWRITES.get(_c + _c, ()), _c)
    _SOUND_REWRITES[_c] = (*_SOUND_REWRITES.get(_c, ()), _c + _c)
_SOUND_LONGEST = max(map(len, _SOUND_REWRITES))
#: At most this many sound-alike changes in one word.
SOUND_CHANGES_MAX = 8

#: A sound-alike change costs this much of an ordinary edit (a letter added, dropped,
#: replaced or two swapped). A suggestion's cost is its edits plus its sound changes.
SOUND_COST = 0.5
#: Ranking: cost minus this times log10 of how often the word is used, so a common word
#: may come before a closer rare one. Both weights were set on half of the Chitanka
#: misspellings and on random typos of common words (`tools/dl/eval/scripts/phonetic.py`).
FREQUENCY_WEIGHT = 0.3

#: Standard abbreviations (ОПР 2012), accepted when a full stop follows: `ул.`,
#: `проф.`, `св.`, `стр.`.
ABBREVIATIONS = frozenset(
    """г гр ул бул пл жк кв бл вх ет ап обл общ напр вкл др проф доц инж арх акад
ген полк зам св хр пр сл стр бр лв млн млрд хил тел факс жп сп изд прев ред ок прибл англ лат гр рус
нем фр ит исп мин сек ч т н сл ср вж срв гл чл ал т.е т.нар т.н пр.хр сл.хр
яну ян фев мар апр авг сеп сеп окт ное дек пон вт чет пет съб нед""".split()
)
#: Units, accepted with or without a full stop: `5 км`, `10 кг`.
UNITS = frozenset("км м см мм кг г мг л мл дка ха кв.м мб гб кб мвт квт вт".split())

#: First parts of hyphenated compounds that are no word of their own:
#: `австро-унгарски`, `англо-саксонски`, `франко-германски`, `гръко-римски`, `медиа-групата`.
COMBINING_FORMS = frozenset(
    "австро англо франко германо гръко индо афро испано италиано българо славяно юдео греко медиа".split()
)

#: All-capital words this short are acronyms (ДДС, ЕАД, УЕФА); they are not spelt.
ACRONYM_MAX = 5


@lru_cache(maxsize=1)
def _forms() -> marisa_trie.Trie:
    trie = marisa_trie.Trie()
    trie.load(str(DATA / "bg_forms.marisa"))
    return trie


def _read_words(name: str) -> frozenset[str]:
    path = DATA / name
    if not path.exists():
        return frozenset()
    lines = (line.split("#", 1)[0].strip().lower() for line in path.read_text(encoding="utf-8").splitlines())
    return frozenset(line for line in lines if line)


@lru_cache(maxsize=1)
def project_words() -> frozenset[str]:
    """The reviewed project words, and the lists built by `tools/`:
    telecom terms with every form (`build_telecom_words.py`), forms of address
    (`build_vocatives.py`) and EU legal words (`build_eu_words.py`)."""
    return frozenset().union(
        *(
            _read_words(name)
            for name in ("project_words.txt", "telecom_words.txt", "vocative_words.txt", "eu_words.txt")
        )
    )


@lru_cache(maxsize=1)
def _frequency() -> marisa_trie.RecordTrie:
    """How often each known form occurs in 2M sentences of Bulgarian news (2020) and
    Wikipedia (2021), Leipzig Corpora Collection (CC BY): it ranks suggestions."""
    trie = marisa_trie.RecordTrie("<I")
    trie.load(str(DATA / "bg_frequency.marisa"))
    return trie


def _count(word: str) -> int:
    found = _frequency().get(word)
    return found[0][0] if found else 0


@lru_cache(maxsize=1)
def _modern() -> marisa_trie.Trie:
    """Modern forms the dictionary lacks (`ползватели`, `коронавирус`, `брифинг`), from
    2020-2021 news, Wikipedia and web text by `tools/build_modern_words.py`: in two
    sources, never only capitalised, no colloquial form, and no likely typo of a frequent
    word.

    With them, their other forms, made by the paradigm of a dictionary word and kept
    only when real text uses them (`tools/build_inflections.py`)."""
    trie = marisa_trie.Trie()
    trie.load(str(DATA / "modern_words.marisa"))
    return trie


def in_dictionary(lower: str) -> bool:
    return lower in _forms()


@lru_cache(maxsize=1)
def _misspellings() -> marisa_trie.BytesTrie:
    """`wrong → right` that people searched Chitanka for (`очудване` → `учудване`)."""
    trie = marisa_trie.BytesTrie()
    trie.load(str(DATA / "misspellings.marisa"))
    return trie


#: Loanwords a misspelling list maps to a near native word (`хаус` → `хаос`, `скраб`):
#: right as they are, whatever the lists say.
LOANWORDS = frozenset({"хаус", "реднек", "скраб", "друид"})


@lru_cache(maxsize=1)
def _corrections() -> dict[str, str]:
    """`wrong → right` written for gramoten (`data/corrections.tsv`): misspellings the
    added word lists would otherwise accept (`надежност`, `верно`, `мошенник`)."""
    out = {}
    for line in (DATA / "corrections.tsv").read_text(encoding="utf-8").splitlines():
        wrong, _, right = line.split("#", 1)[0].strip().partition("	")
        if right:
            out[wrong] = right
    return out


@lru_cache(maxsize=1)
def forbidden_words() -> frozenset[str]:
    """Forms the added lists wrongly accept (`незнам`, `ходиме`, `фармацефт`) and the
    misspellings in `corrections.tsv`: a known error is never correct. The bgOffice
    dictionary wins over the generated list, but not over `corrections.tsv`, which also
    lists the dictionary's few errors (`подтискане`)."""
    return (_read_words("forbidden_words.txt") | frozenset(_corrections())) - LOANWORDS


def known_correction(word: str) -> str | None:
    """The correction for this misspelling, if one is known: gramoten's own list, what
    people looked up on Chitanka, or a feminine noun in -ост/-ст missing its second т
    (`радоста` → `радостта`). The own list comes first, as it was read word by word
    (`гешеф` → `гешефт`, where Chitanka has `гешев`)."""
    lower = word.lower()
    if lower in _corrections():
        return _corrections()[lower]
    found = _misspellings().get(lower)
    if found:
        return found[0].decode("utf-8")
    if lower.endswith("ста") and in_dictionary(lower[:-1] + "та"):
        return lower[:-1] + "та"
    return None


@lru_cache(maxsize=1)
def _names() -> marisa_trie.Trie:
    """Words Bulgarian news and Wikipedia write with a capital at least 20 times and
    almost never lowercase (`обама`, `хамас`): a name, even at a sentence start."""
    trie = marisa_trie.Trie()
    trie.load(str(DATA / "names.marisa"))
    return trie


def is_name(word: str) -> bool:
    """A capitalised word the corpora know as a name."""
    return word[:1].isupper() and word.lower() in _names()


def _known(lower: str, extra: frozenset[str]) -> bool:
    if lower in extra or lower in LOANWORDS:
        return True
    if lower in _corrections():
        return False  # gramoten's own list also overrides the dictionary's few errors (`подтискане`)
    if lower in _forms():
        return True
    if lower in forbidden_words():
        return False
    return lower in _modern() or lower in project_words()


def is_correct(word: str, extra: frozenset[str] = frozenset()) -> bool:
    """True when every hyphen part is a known form, in any capitalisation."""
    if word.isupper() and len(word) <= ACRONYM_MAX:
        return True
    lower = word.lower()
    if _known(lower, extra):
        return True
    parts = lower.split("-")
    return (
        len(parts) > 1
        and all(len(p) <= 1 or _known(p, extra) or p in COMBINING_FORMS for p in parts[:-1])
        and (len(parts[-1]) <= 1 or _known(parts[-1], extra))
    )


def _edits(word: str, upto: int | None = None) -> set[str]:
    """Every string one edit away, the edit at position `upto` or before."""
    splits = [(word[:i], word[i:]) for i in range(min(len(word), len(word) if upto is None else upto) + 1)]
    return (
        {a + b[1:] for a, b in splits if b}
        | {a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1}
        | {a + c + b[1:] for a, b in splits if b for c in ALPHABET if c != b[0]}
        | {a + c + b for a, b in splits for c in ALPHABET}
    )


def _shape(suggestion: str, like: str) -> str:
    """Give a suggestion the capitalisation of the word it replaces."""
    if like.isupper() and len(like) > 1:
        return suggestion.upper()
    if like[:1].isupper():
        return suggestion[:1].upper() + suggestion[1:]
    return suggestion


def suggest(word: str, limit: int = 5, extra: frozenset[str] = frozenset(), deep: bool = True) -> list[str]:
    """Known words one edit away or spelt the way `word` sounds; when fewer than
    `FILL_TO` cost one edit or less and `deep`, words two edits away too. Ranked by
    cost (`SOUND_COST` a sound-alike change) and how often each word is used
    (`FREQUENCY_WEIGHT`).

    `deep` lets a host limit how many words of a text get the two-edit search
    (`gramoten.DEEP_SUGGESTIONS_PER_CALL`): one-edit suggestions, which cover most
    typos, are always made.
    """
    ranked = list(_ranked(word.lower(), extra, deep))
    correction = known_correction(word)
    # A correction of two words comes only from gramoten's own list (`не може`); the
    # misspelling table's corrections are single words.
    if correction and (" " not in correction or word.lower() in _corrections()):
        ranked = [correction] + [w for w in ranked if w != correction]
    return [_shape(w, word) for w in ranked[:limit]]


@lru_cache(maxsize=8)
def _prefixes(extra: frozenset[str]) -> marisa_trie.Trie:
    """The project words and added words as a trie, so their starts are a prefix search:
    the word lists that are not tries. A set of every start took 16 ms and 3 MB."""
    return marisa_trie.Trie(project_words() | extra)


@lru_cache(maxsize=1)
def _word_starts() -> marisa_trie.Trie:
    """Every start of every form in `bg_forms.marisa` and `modern_words.marisa`
    (`tools/build_word_starts.py`): whether a known word begins with some letters is one
    exact lookup, 3 times as fast as a prefix search in each list."""
    trie = marisa_trie.Trie()
    trie.load(str(DATA / "word_starts.marisa"))
    return trie


def _starts_of(words: frozenset[str]) -> frozenset[str]:
    return frozenset(w[:i] for w in words for i in range(1, len(w) + 1))


@lru_cache(maxsize=1)
def _project_starts() -> frozenset[str]:
    """Every start of the project words, made once: the text lists are not in
    `word_starts.marisa`, so a word added to them needs no rebuild."""
    return _starts_of(project_words())


@lru_cache(maxsize=64)
def _added_starts(extra: frozenset[str]) -> frozenset[str]:
    return _starts_of(extra)


#: Suggestions already made, by (word, added words, deep), least recently used first.
#: Only a search that finished within `SECOND_EDIT_STEPS` is kept.
_RANKED: OrderedDict[tuple[str, frozenset[str], bool], tuple[str, ...]] = OrderedDict()
_RANKED_MAX = 20_000
_RANKED_LOCK = threading.Lock()


def _ranked(lower: str, extra: frozenset[str], deep: bool) -> tuple[str, ...]:
    key = (lower, extra, deep)
    with _RANKED_LOCK:
        if key in _RANKED:
            _RANKED.move_to_end(key)
            return _RANKED[key]
    found, finished = _search(lower, extra, deep)
    if finished:
        with _RANKED_LOCK:
            _RANKED[key] = found
            while len(_RANKED) > _RANKED_MAX:
                _RANKED.popitem(last=False)
    return found


def clear_suggestions() -> None:
    """Forget every suggestion made, after the word lists change."""
    with _RANKED_LOCK:
        _RANKED.clear()


def _search(lower: str, extra: frozenset[str], deep: bool) -> tuple[tuple[str, ...], bool]:
    """Known words one edit from `lower`, else two if `deep`, most used first; and
    whether the search finished within `SECOND_EDIT_STEPS`."""
    forms, project, forbidden = _forms(), project_words(), forbidden_words()
    modern = _modern()
    starts, project_starts, added_starts = _word_starts(), _project_starts(), _added_starts(extra)

    corrections = _corrections()

    def known(w: str) -> bool:
        if w in extra:
            return True
        if w in forms:
            return w not in corrections
        return (w in modern or w in project) and w not in forbidden

    def opens(prefix: str) -> bool:
        """Whether a known word begins with `prefix` (every word begins with "")."""
        return not prefix or prefix in starts or prefix in project_starts or prefix in added_starts

    def reach(w: str) -> int:
        """The longest start of `w` some known word begins with. An edit after it cannot
        reach a known word, since the start before an edit stays as it was."""
        low, high = 0, len(w)
        while low < high:
            middle = (low + high + 1) // 2
            if opens(w[:middle]):
                low = middle
            else:
                high = middle - 1
        return low

    cost = {w: 1.0 for w in _edits(lower, reach(lower)) if known(w)}
    sounds, finished = _sound_alikes(lower, opens, known, SECOND_EDIT_STEPS)
    for w, changes in sounds.items():
        cost[w] = min(cost.get(w, math.inf), SOUND_COST * changes)
    cost.pop(lower, None)
    if deep and sum(c <= 1 for c in cost.values()) < FILL_TO:
        # Fewer than FILL_TO words within one edit: words two edits away join them.
        two, finished = _within_two(lower, opens, known, SECOND_EDIT_STEPS)
        for w in two - {lower}:
            cost.setdefault(w, 2.0)

    def rank(w: str) -> tuple[float, int, str]:
        used = _count(w)
        return cost[w] - FREQUENCY_WEIGHT * math.log10(used + 1), -used, w

    return tuple(sorted(cost, key=rank)), finished


def _sound_alikes(word: str, opens, known, steps: float) -> tuple[dict[str, int], bool]:
    """Every known word `word` becomes by sound-alike changes only (`_SOUND_REWRITES`),
    with the fewest changes each needs, and whether the search finished within `steps`
    lookups. It walks the word lists like `_within_two`, so a change is tried only where
    a known word begins with the letters built so far."""
    found: dict[str, int] = {}
    fewest: dict[tuple[int, str], int] = {}
    starts: dict[str, bool] = {}

    def begins(prefix: str) -> bool:
        if prefix not in starts:
            starts[prefix] = opens(prefix)
        return starts[prefix]

    stack = [(0, "", 0)]
    while stack:
        if len(starts) > steps:
            return found, False
        i, built, changes = stack.pop()
        if fewest.get((i, built), SOUND_CHANGES_MAX + 1) <= changes:
            continue
        fewest[i, built] = changes
        if i == len(word):
            if changes and known(built) and changes < found.get(built, SOUND_CHANGES_MAX + 1):
                found[built] = changes
            continue
        if begins(built + word[i]):
            stack.append((i + 1, built + word[i], changes))
        if changes == SOUND_CHANGES_MAX:
            continue
        for n in range(1, min(_SOUND_LONGEST, len(word) - i) + 1):
            for written in _SOUND_REWRITES.get(word[i : i + n], ()):
                if begins(built + written):
                    stack.append((i + n, built + written, changes + 1))
    return found, True


def _within_two(word: str, opens, known, steps: float) -> tuple[set[str], bool]:
    """Every known word at most two edits (substitute, insert, delete, swap two
    neighbours) from `word`, and whether the search finished within `steps` lookups.

    It walks the word lists letter by letter and drops a branch as soon as no known
    word begins with the letters built so far, so it finds the same words as editing
    every one-edit string again, 5 to 40 times faster, and the same ones every time."""
    found: set[str] = set()
    seen: set[tuple[int, str, int]] = set()
    starts: dict[str, bool] = {}

    def begins(prefix: str) -> bool:
        known_start = starts.get(prefix)
        if known_start is None:
            known_start = starts[prefix] = opens(prefix)
        return known_start

    n = len(word)
    stack = [(0, "", 2)]
    push, pop = stack.append, stack.pop
    while stack:
        if len(starts) > steps:
            return found, False
        state = pop()
        if state in seen:
            continue
        seen.add(state)
        i, built, left = state
        if i < n:
            here = word[i]
            if begins(built + here):
                push((i + 1, built + here, left))
        elif known(built):
            found.add(built)
        if not left:
            continue
        down = left - 1
        # The letters some known word has after `built`: each serves a replace and an insert.
        alive = [c for c in ALPHABET if begins(built + c)]
        if i < n:
            push((i + 1, built, down))  # delete
            for c in alive:
                if c != here:
                    push((i + 1, built + c, down))  # replace
            if i + 1 < n and here != word[i + 1] and begins(built + word[i + 1] + here):
                push((i + 2, built + word[i + 1] + here, down))  # swap
        for c in alive:
            push((i, built + c, down))  # insert
    return found, True
