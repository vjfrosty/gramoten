"""Modern Bulgarian words the 2017 bg_BG dictionary lacks, and word counts to rank suggestions.

    uv run --no-project --python 3.13 --with marisa-trie==1.4.1 python -I \
        tools/build_modern_words.py DOWNLOADS

DOWNLOADS holds, unpacked or not:
* `bul_news_2020_1M.tar.gz`, `bul_wikipedia_2021_1M.tar.gz`: Leipzig Corpora
  Collection, CC BY (https://wortschatz.uni-leipzig.de/en/usage; © 2025
  Universität Leipzig / Sächsische Akademie der Wissenschaften / InfAI). Each
  has a `*-words.txt` of `id<TAB>word<TAB>count`.
* `macocu_bg_counts.txt`: word counts from the start of the MaCoCu-bg web corpus,
  CC0 (http://hdl.handle.net/11356/1800), `word count` per line, made by
  `build_web_counts.py`.

Modern words the 2017 dictionary lacks, such as ползватели and
киберсигурност. A word is accepted only when it is

1. written in lowercase Cyrillic, 3-30 letters, no hyphen, never
   three equal letters in a row, and never seen capitalised only (a name);
2. unknown to the dictionary and the project words;
3. in at least two of the three sources (news and Wikipedia at least 3 times,
   web text at least 5), or at least 40 times in news and Wikipedia together;
4. not a likely typo: no dictionary word one edit away is 20 times as frequent
   in news and Wikipedia (`използавне` beside `използване`; an added or dropped
   ending is no typo: `интернета` beside `интернет`), and none two edits
   away is 50 times as frequent and seen 300 times while the word itself is
   seen at most 15 times (`матерял` beside `материал`);
5. not a colloquial form of a standard word (`кво`, `крадяли`, `щото`).

A second, stricter tier takes long specialised words seen only a few times
(`наказателноправни`, `менестрели`): 9 letters or more, at least 3 times in news
or Wikipedia, no dictionary word at all one edit away nor a frequent one two
edits away, no word in the corpora one edit away that is 5 times as frequent
(`вирусулогът` beside `вирусологът`), and not the cut-off start of a more
frequent word (`коронавиру`). A long word's typo nearly always has its right
spelling close by.

A third tier takes words of 5 letters or more used 20 times in web text in more
than one form (`емболизация`). Web text repeats its typos, so this tier has two
more guards: no slip of a spelling used as often (`slip_ratio`), and not the
cut-off start of a word 500 times as frequent (`възмо`).

Also writes `gramoten/data/names.marisa`: words written with a capital at
least 20 times and at most once in twenty lowercase (`обама`, `хамас`), so a
name that starts a sentence is not taken for a typo.

Writes `gramoten/data/modern_words.marisa` (the accepted forms; `build_inflections.py`
then adds their other forms to it), a copy of it as DOWNLOADS/modern_words_base.marisa
(the input of `build_inflections.py`), and
`gramoten/data/bg_frequency.marisa` (news + Wikipedia counts of every known
form, to rank suggestions), and prints a sample of accepted and refused words
for a person to read.
"""

from __future__ import annotations

import collections
import os
import random
import re
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # build_chitanka

import marisa_trie  # noqa: E402

from gramoten import spelling  # noqa: E402

DATA = ROOT / "src" / "gramoten" / "data"
#: No hyphen: a hyphenated word is checked part by part anyway, and as one unknown
#: string `най-голямия` (for `най-големия`) would slip past the typo guard.
WORD = re.compile(r"[а-яѝ]{3,30}")
LEIPZIG = ("bul_news_2020_1M", "bul_wikipedia_2021_1M")
#: Spoken forms with a standard spelling; frequent in quotes and subtitles, wrong in writing.
COLLOQUIAL = set(
    """кво що щото нема некой ний вий айде абе бе ма бате кът йо ся тва тоа тия
крадяли видяли ядяли ще-да мерси ок окей добре-де""".split()
)


def deletes(word: str, depth: int) -> set[str]:
    """`word` with up to `depth` letters left out (the symmetric-delete index of SymSpell)."""
    found, edge = {word}, {word}
    for _ in range(depth):
        edge = {w[:i] + w[i + 1 :] for w in edge for i in range(len(w))}
        found |= edge
    return found


def leipzig_counts(downloads: Path, name: str) -> tuple[collections.Counter, collections.Counter]:
    """(lowercase counts, counts of the capitalised spelling) from a Leipzig `*-words.txt`."""
    lower: collections.Counter = collections.Counter()
    upper: collections.Counter = collections.Counter()
    with tarfile.open(downloads / f"{name}.tar.gz") as archive:
        member = next(m for m in archive if m.name.endswith("-words.txt"))  # stops there
        for raw in archive.extractfile(member):
            parts = raw.decode("utf-8", "replace").rstrip("\n").split("\t")
            if len(parts) < 3 or not parts[2].isdigit():
                continue
            word, count = parts[1], int(parts[2])
            if word.islower():
                lower[word] += count
            elif word[:1].isupper() and word[1:].islower():
                upper[word.lower()] += count
    return lower, upper


def web_counts(downloads: Path) -> collections.Counter:
    """Lowercase word counts of the MaCoCu-bg web text (`build_web_counts.py`)."""
    counts: collections.Counter = collections.Counter()
    for line in (downloads / "macocu_bg_counts.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        word, _, count = line.rpartition(" ")
        if count.isdigit() and word.islower():
            counts[word] += int(count)
    return counts


#: Typo shapes for the web tier, with how many times as frequent the other spelling must be.
#: These shapes are typos (`одеалото`, `кетеринг`, `калдаръмени`, `пустощта`); `е`/`и`,
#: `г`/`к`, `д`/`т` and an added letter are as often two real words (`придадем` beside
#: `предадем`, `пелетен` beside `плетен`), so they are left out.
VOWEL_SLIPS = {
    frozenset("яа"): 1.0,
    frozenset("оу"): 1.0,
    frozenset("иъ"): 1.0,
    frozenset("аъ"): 2.0,
    frozenset("еъ"): 5.0,
    frozenset("ао"): 10.0,
}
CONSONANT_SLIPS = {frozenset("зс"), frozenset("цс"), frozenset("шщ")}
#: A letter left out, when the word it was left out of is this many times as frequent.
MISSING_LETTER = 10.0


def slip_ratio(word: str, other: str) -> float | None:
    """How many times as frequent `other` must be for `word` to be taken as a slip of it,
    or None when the two differ as real words do. An edit at the first letter or in the
    last two is another word or another ending (`вкуси`/`овкуси`, `-но`/`-на`)."""
    if len(word) == len(other):
        diff = [i for i in range(len(word)) if word[i] != other[i]]
        if len(diff) != 1 or diff[0] == 0 or diff[0] >= len(word) - 2:
            return None
        pair = frozenset((word[diff[0]], other[diff[0]]))
        return VOWEL_SLIPS.get(pair, 1.0 if pair in CONSONANT_SLIPS else None)
    if len(word) == len(other) + 1:  # a letter too many: only a doubled one, and not
        # `нн`, which adjectives have (`лавинните` from `лавинен`, beside `лавините`)
        i = next((i for i in range(len(other)) if word[i] != other[i]), len(other))
        return 1.0 if 0 < i < len(other) - 2 and word[i] == word[i - 1] != "н" else None
    if len(other) == len(word) + 1:  # a letter left out
        i = next((i for i in range(len(word)) if word[i] != other[i]), len(word))
        if i == 0 or i >= len(word) - 2:
            return None
        if other[i] == "й" or other[i] in (other[i - 1], other[i + 1]):
            return 1.0  # `тийнеджъри`, `вакумиране`, `сексимвол`
        return MISSING_LETTER  # `екслузивен`, `кликане`
    return None


def ending_partners(min_lemmas: int = 200) -> dict[str, set[str]]:
    """For each word ending of up to 4 letters, the endings other forms of the same word
    take, in at least `min_lemmas` lemmas of the morphology (`-` and `а`, `а` and `ата`,
    `ен` and `на`): the inflections Bulgarian words actually show."""
    from gramoten import morphology

    trie, _, _ = morphology._data()
    by_lemma: dict[str, set[str]] = collections.defaultdict(set)
    for key in trie:
        form, _, rest = key.partition("")
        by_lemma[rest.partition("")[0]].add(form)
    pairs: collections.Counter = collections.Counter()
    for forms in by_lemma.values():
        if not 2 <= len(forms) <= 60:
            continue
        stem = os.path.commonprefix(sorted(forms))
        endings = {f[len(stem) :] for f in forms if len(f) - len(stem) <= 4}
        pairs.update((a, b) for a in endings for b in endings if a != b)
    partners: dict[str, set[str]] = collections.defaultdict(set)
    for (a, b), n in pairs.items():
        if n >= min_lemmas:
            partners[a].add(b)
    return partners


def glued_ne(word: str) -> bool:
    """`не` glued to a finite verb form (`незнаеше`, `неможеха`; BERON §62): written apart.
    A participle or an adjective takes it together (`неработещ`, `нелюбим`)."""
    from build_chitanka import finite_only, is_verb

    return (
        word.startswith("не")
        and not word.startswith("недо")
        and not word.endswith(("им", "ем"))
        and finite_only(word[2:])
        and not is_verb(word)
    )


def settlement_names(downloads: Path) -> set[str]:
    """Every word of the names of Bulgaria's settlements, lowercased (`кочево`, `доброславци`),
    from the National Statistical Institute's register EKATTE: `ekatte_excel.zip` in
    DOWNLOADS, from https://www.nsi.bg/nrnm/ekatte/index ("Свали архив в Excel"). An
    official classifier of a state body, so not under copyright (ЗАПСП, чл. 4). The names go
    into `names.marisa`: accepted only capitalised, so `кочево` in lowercase stays flagged."""
    import io
    import xml.etree.ElementTree as ET
    import zipfile

    path = downloads / "ekatte_excel.zip"
    if not path.exists():
        return set()
    book = zipfile.ZipFile(io.BytesIO(zipfile.ZipFile(path).read("ek_atte.xlsx")))
    m = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    shared = [
        "".join(t.text or "" for t in si.iter(m + "t"))
        for si in ET.fromstring(book.read("xl/sharedStrings.xml")).iter(m + "si")
    ]
    words = set()
    for row in ET.fromstring(book.read("xl/worksheets/sheet1.xml")).iter(m + "row"):
        cells = row.findall(m + "c")
        if len(cells) > 2 and cells[2].get("t") == "s":
            name = shared[int(cells[2].find(m + "v").text)]
            words |= {w for w in re.findall(r"[а-яѝ]+", name.lower()) if len(w) >= 3}
    return words


def main() -> None:
    downloads = Path(sys.argv[1])
    (news, news_up), (wiki, wiki_up) = (leipzig_counts(downloads, name) for name in LEIPZIG)
    web = web_counts(downloads)
    edited = news + wiki
    capitalised = news_up + wiki_up

    def votes(word: str) -> int:
        return (news[word] >= 3) + (wiki[word] >= 3) + (web[word] >= 5)

    # Frequent dictionary words, by every form with up to two letters left out.
    frequent: dict[str, list[str]] = collections.defaultdict(list)
    for w, c in edited.items():
        if c >= 300 and spelling.in_dictionary(w):
            for key in deletes(w, 2):
                frequent[key].append(w)

    corpus_words = marisa_trie.Trie(w for w in edited if WORD.fullmatch(w))
    web_words = marisa_trie.Trie(w for w, c in web.items() if c >= 5 and WORD.fullmatch(w))
    partners = ending_partners()

    def inflected_too(word: str) -> bool:
        """Another form of the word, by an ending pair Bulgarian words show, is used too:
        a real word appears in several forms (ламинат, ламината, ламинати), a typo rarely."""
        for k in range(0, 5):
            stem, ending = word[: len(word) - k], word[len(word) - k :]
            for other in partners.get(ending, ()):
                form = stem + other
                if form != word and (web[form] + edited[form] >= 3 or spelling.in_dictionary(form)):
                    return True
        return False

    def web_word(word: str) -> bool:
        """The web tier: a word of 5+ letters used 20 times in web text, in more than one form."""
        return len(word) >= 5 and web[word] >= 20 and inflected_too(word)

    web_tier: list[str] = []
    accepted, refused = [], collections.Counter()
    near_typos = []
    long_tier: list[str] = []
    for word in set(edited) | set(web):
        if not WORD.fullmatch(word) or re.search(r"(.)\1\1", word):
            continue
        if spelling.in_dictionary(word) or word in spelling.project_words():
            continue  # the base dictionary only: never the list this script writes
        if word in COLLOQUIAL or glued_ne(word):
            refused["colloquial"] += 1
            continue
        # A known misspelling: forbidden already, or one people looked up on Chitanka
        # whose correction is at least 5 times as common (`безмислено`).
        correction = spelling._misspellings().get(word)
        if word in spelling.forbidden_words() or (
            correction and edited[correction[0].decode("utf-8")] >= 5 * max(edited[word], 1)
        ):
            refused["a known misspelling"] += 1
            continue
        long_rare = len(word) >= 9 and edited[word] >= 3
        if votes(word) < 2 and edited[word] < 40 and not long_rare and not web_word(word):
            continue
        if capitalised[word] > 5 * (edited[word] + 1):
            refused["a name"] += 1
            continue
        # A form that is its neighbour plus or minus an ending is an inflection, not a
        # typo: `интернета` beside `интернет`.
        neighbours = [
            w
            for w in spelling._edits(word)
            if spelling.in_dictionary(w) and not (word.startswith(w) or w.startswith(word))
        ]
        # Edited text and web text each on its own: added together they let in typos common
        # on the web (`израстнали`, `наглоста`). Some real words a frequent neighbour shades
        # are lost (`ламинат`: `заминат`).
        if any(edited[w] >= 20 * max(edited[word], 1) or web[w] >= 20 * max(web[word], 1) for w in neighbours):
            refused["a typo of a frequent word"] += 1
            continue
        close = {w for key in deletes(word, 1) for w in frequent.get(key, ())}
        if edited[word] <= 15 and any(edited[w] >= 50 * max(edited[word], 1) for w in close):
            refused["two edits from a frequent word"] += 1
            near_typos.append(f"{word}→{max(close, key=lambda w: edited[w])}")
            continue
        # The cut-off start of a word 500 times as frequent (`коронавиру`, `възмо`): a line
        # break or a truncated snippet.
        if sum(web[w] for w in web_words.keys(word) if len(w) >= len(word) + 2) >= 500 * max(web[word], 1):
            refused["a cut-off word"] += 1
            continue
        if votes(word) < 2 and edited[word] < 40 and not long_rare:
            # In by web_word alone, so one more guard: a slip of a spelling used as often or
            # more, also one the dictionary lacks (`тийнеджъри` beside `тийнейджъри`).
            if any(
                r is not None and web[w] >= r * web[word] and (spelling.in_dictionary(w) or web[w] >= 20)
                for w in spelling._edits(word)
                for r in (slip_ratio(word, w),)
            ):
                refused["a slip in web text"] += 1
                continue
            web_tier.append(word)
        elif votes(word) < 2 and edited[word] < 40:
            # The long, rare tier: nothing in the dictionary close to it.
            nearby = spelling._edits(word)
            if (
                any(spelling.in_dictionary(w) or edited[w] >= 5 * edited[word] for w in nearby)
                or close
                or any(edited[w] >= 5 * edited[word] for w in corpus_words.keys(word) if w != word)
            ):
                refused["long and rare, near a word"] += 1
                continue
            long_tier.append(word)
        accepted.append(word)

    marisa_trie.Trie(sorted(accepted)).save(str(DATA / "modern_words.marisa"))
    marisa_trie.Trie(sorted(accepted)).save(str(downloads / "modern_words_base.marisa"))
    accepted_set = set(accepted)
    known = {w: c for w, c in edited.items() if c >= 2 and (spelling.in_dictionary(w) or w in accepted_set)}
    marisa_trie.RecordTrie("<I", ((w, (c,)) for w, c in known.items())).save(str(DATA / "bg_frequency.marisa"))

    names = sorted(
        w
        for w, c in capitalised.items()
        if c >= 20 and edited[w] * 20 <= c and re.fullmatch(r"[а-яѝ]{2,30}", w) and not spelling.in_dictionary(w)
    )
    settlements = settlement_names(downloads)
    names = sorted(set(names) | {w for w in settlements if not spelling.in_dictionary(w)})
    print(f"{len(settlements)} words of settlement names (EKATTE)")
    marisa_trie.Trie(names).save(str(DATA / "names.marisa"))
    print(f"{len(names)} names, e.g. {' '.join(random.Random(3).sample(names, 30))}")

    rng = random.Random(7)
    print(f"web tier: {len(web_tier)}:", " ".join(rng.sample(web_tier, min(150, len(web_tier)))))
    print(f"long rare tier: {len(long_tier)}:", " ".join(rng.sample(long_tier, min(100, len(long_tier)))))
    print("refused as two edits away:", " ".join(rng.sample(near_typos, min(80, len(near_typos)))))
    print(f"accepted {len(accepted)} modern forms; refused {dict(refused)}; {len(known)} forms ranked")
    print("sample accepted:", " ".join(f"{w}:{edited[w]}/{web[w]}" for w in rng.sample(sorted(accepted), 80)))
    print(
        "most frequent accepted:", " ".join(f"{w}:{edited[w]}" for w in sorted(accepted, key=lambda w: -edited[w])[:60])
    )
    for probe in ("ползватели", "киберсигурност", "правоприлагане", "смартфон", "имейл", "използавне"):
        print(probe, "accepted" if probe in accepted_set else "not accepted", edited[probe], web[probe])


if __name__ == "__main__":
    main()
