"""Forms of address (звателни форми) the dictionary lacks: мамо, сине, попе, клиенте.

    uv run --no-project --python 3.13 --with marisa-trie==1.4.1 python -I \
        tools/build_vocatives.py DOWNLOADS

DOWNLOADS is the folder of `build_modern_words.py` (Leipzig news and Wikipedia,
MaCoCu-bg web counts). bgOffice gives the vocative of some nouns (господине,
приятелю, бабо) but not of many others, and its tables do not say which nouns
name people. So every noun gets the vocative the standard rules give, and a
candidate is kept only when the corpora use it:

* feminine in -ица → -ице (госпожице), other feminine in -а → -о (мамо, сестро);
* masculine in -ар, -яр, -ач, -тел → -ю (другарю, учителю);
* masculine in -ец → -че (старче, отче);
* masculine ending in a hard consonant → -е (сине, попе, клиенте);
* masculine in -а → -о, like a feminine noun (слуго).

Kept when the noun names a person (a person ending such as -тел, -ник, -ист,
-ка, -ица, or a kinship word; a base of 5 letters or more; a -ка form used 10
times) and web text uses the form at least 3 times or news and Wikipedia
twice: forums and comments are where people address each other in writing.
This keeps out things (`минуто`, `годино`, `затворе`, `банко`).

Web text rarely addresses anyone, so a second path needs no use
at all: a noun that names a person by the language itself (`lexical_persons`).
Bulgarian counts only people with `двама`, `трима`, `няколцина`, so a noun the
Leipzig sentences count that way names a person; so does a noun with a person
ending and a feminine pair in the dictionary (`учител`/`учителка`), and that
pair (`кралице`, `грешнице`, `пилоте`). Writes
`gramoten/data/vocative_words.txt`, read by `spelling.project_words`.
"""

from __future__ import annotations

import collections
import re
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_modern_words import LEIPZIG, leipzig_counts, web_counts  # noqa: E402

from gramoten import morphology, spelling  # noqa: E402
from gramoten.grammar import PERSONS  # noqa: E402

OUT = ROOT / "src" / "gramoten" / "data" / "vocative_words.txt"
HARD = set("бвгдзклмнпрстфхцчшщ")
#: Endings of nouns that name people. The lexicon does not say which nouns do,
#: and without this things get in: `минуто`, `годино`, `карто`.
MASCULINE_PERSON = (
    "тел",
    "ник",
    "ач",
    "яч",
    "ист",
    "ант",
    "ент",
    "лог",
    "ар",
    "яр",
    "ер",
    "ор",
    "ец",
    "ин",
    "чия",
    "джия",
    "ьор",
    "ак",
    "ик",
    "ент",
    "ат",
    "ит",
    "ов",
)
FEMININE_PERSON = ("ка", "ица", "иня", "киня")
#: Things whose ending looks like a person's, which web text (with some Serbian pages
#: in the crawl) lifts over the thresholds: `говоре`, `палче`, `улице`, `покупко`.
NOT_PERSONS = set(
    """говор простор палец ланец молец улица страница покупка китчица фаворит бронх каска клинец
фреска паричка просека фантастика бронхит конница затвор""".split()
)
KIN = set(
    """мама баба леля тетка кака сестра дъщеря щерка снаха жена госпожа булка балдъза етърва
зълва майка мащеха кръстница стрина вуйна""".split()
)
#: Short nouns and -ка nouns name things as often as people (`спор`, `банка`):
#: a person ending is believed only on a base this long, and a -ка vocative
#: only when dialogue uses it this often.
MIN_BASE = 5
#: The web thresholds below are per 600 MB of MaCoCu-bg; the counts come from 3 GB, so
#: they are scaled by this so a form needs the same share of use.
WEB_SCALE = 5
KA_MIN_USES = 10
#: Masculine endings shared with things (`затвор`, `север`, `банкомат`): 10 uses.
LOOSE_MASCULINE = ("ер", "ор", "ат", "ит", "ик", "ов")
LOOSE_MIN_USES = 10
#: -ица names things too (`улица`, `седмица`): 5 uses.
ICA_MIN_USES = 5


def gender_m_irregular(base: str, tag: dict) -> bool:
    """A masculine noun in -к, -г, -х, whose vocative is not the -е of the rule."""
    return tag.get("g") == "m" and base.endswith(("к", "г", "х"))


def vocative(base: str, gender: str) -> str | None:
    if gender == "f":
        if base.endswith("ица"):
            return base[:-1] + "е"
        if base.endswith("а"):
            return base[:-1] + "о"
        return None
    if gender == "m":
        if base.endswith("а"):
            return base[:-1] + "о"  # слуга → слуго, like a feminine noun
        if base.endswith(("ар", "яр", "ач", "тел")):
            return base + "ю"
        if base.endswith("ец") and len(base) > 3:
            return base[:-2] + "че"
        if base[-1:] in HARD:
            return base + "е"
    return None


#: Counting words Bulgarian keeps for people: `двама учители`, never `двама стола`.
COUNTED = re.compile(
    r"\b(?:двама|трима|четирима|петима|шестима|седмина|осмина|деветима|десетима|няколцина|неколцина)"
    r"\s+([а-я]+)"
)
#: Person endings a masculine noun with a feminine pair must have (`учител`/`учителка`).
PAIR_ENDINGS = ("тел", "ник", "ист", "ец", "ент", "ант", "ар", "яр", "ьор", "джия", "чия", "лог")


def counted_persons(downloads: Path, lemmas) -> set[str]:
    """Nouns the Leipzig sentences count with `двама`, `трима`, `няколцина`... twice
    or more: those forms are for people only, so the noun names a person."""
    counts: collections.Counter = collections.Counter()
    for name in LEIPZIG:
        with tarfile.open(downloads / f"{name}.tar.gz") as archive:
            member = next(m for m in archive.getmembers() if m.name.endswith("-sentences.txt"))
            for raw in archive.extractfile(member):
                for word in COUNTED.findall(raw.decode("utf-8", "replace").lower()):
                    for r in morphology.analyse(word):
                        if r.tag.get("pos") == "N" and r.tag.get("n") == "p":
                            counts[lemmas[r.lemma][0]] += 1
    return {base for base, n in counts.items() if n >= 2 and len(base) >= MIN_BASE}


def lexical_persons(nouns: dict[str, str], counted: set[str]) -> tuple[set[str], set[str]]:
    """Nouns that name people, by the language itself rather than by how often their vocative
    is used: a masculine noun counted with `двама` (above), or one with a person ending and a
    feminine pair in the dictionary (`учител`/`учителка`, `грешник`/`грешница`), and that
    feminine pair. Left out, since the rule's form would be wrong or unsure: nouns in -к, -г,
    -х (`човек` → `човече`, `юнак` → `юнако`, not -е), in -ин (`селянин`, `арабин`), in -ец after
    a vowel (`боец` → `бойче`), and in -ач/-яч unless counted (a device as often: `брояч`).

    Returns (sure, if_used). The feminine pair of an uncounted noun in -к is only as good as its
    use: -ник/-ница pairs name things as often as people (`кошница`, `солница`, `бойница`)."""

    def feminine(m: str) -> str | None:
        options = [m + "ка", m + "ица", m + "иня", m + "ня", m + "еса"]
        if m.endswith("ник"):
            options.append(m[:-1] + "ца")
        if m.endswith("ец"):
            options.append(m[:-2] + "ка")
        if m.endswith("тор"):
            options.append(m[:-2] + "рка")
        return next((f for f in options if nouns.get(f) == "f"), None)

    if_used: set[str] = set()
    found = {f for f in (feminine(p) for p in PERSONS) if f}  # `кралица`: `крал` is a verb form too
    found |= {b for b in counted if nouns.get(b) == "f"}  # `колега`, a noun of either sex
    for m, gender in nouns.items():
        if gender != "m" or m in NOT_PERSONS:
            continue
        if m.endswith("ец") and m[-3:-2] in "аеиоуъюяй":
            continue
        if m in counted or m in PERSONS:
            person = True
        else:
            person = (
                not m.endswith(("ач", "яч"))
                and len(m) >= MIN_BASE
                and m.endswith(PAIR_ENDINGS)
                and feminine(m) is not None
            )
        if person:
            if not m.endswith(("к", "г", "х", "ин")):
                found.add(m)
            if feminine(m):
                sure = m in counted or m in PERSONS or not m.endswith(("к", "г", "х"))
                (found if sure else if_used).add(feminine(m))
    return found - NOT_PERSONS, if_used - NOT_PERSONS - found


def main() -> None:
    downloads = Path(sys.argv[1])
    (news, _), (wiki, _) = (leipzig_counts(downloads, name) for name in LEIPZIG)
    web = web_counts(downloads)
    edited = news + wiki
    _, _, lemmas = morphology._data()
    genders: dict[str, str] = {}
    for index, (base, pos, _stem) in enumerate(lemmas):
        if pos == "N":
            tag = next(
                (
                    r.tag
                    for r in morphology.analyse(base)
                    if r.lemma == index and r.tag.get("d") == "i" and r.tag.get("n") == "s"
                ),
                {},
            )
            if tag.get("g") in ("m", "f"):
                genders.setdefault(base, tag["g"])
    by_rule, by_rule_if_used = lexical_persons(genders, counted_persons(downloads, lemmas))
    # Judge against the other added lists only: this script's own last output is part of
    # project_words, and a list must not grade itself (a re-run would keep nothing old).
    others = spelling.project_words() - spelling._read_words("vocative_words.txt")
    kept = set()
    for index, (base, pos, _stem) in enumerate(lemmas):
        if pos != "N":
            continue
        tag = next(
            (
                r.tag
                for r in morphology.analyse(base)
                if r.lemma == index and r.tag.get("d") == "i" and r.tag.get("n") == "s"
            ),
            {"pos": "N"},
        )
        form = vocative(base, tag.get("g", ""))
        if not form or spelling.in_dictionary(form) or form in others:
            continue
        if base in NOT_PERSONS:
            continue
        if base in KIN or base in PERSONS:
            person = True  # `сине`, `попе`, `куме`: short, and people
        elif len(base) < MIN_BASE:
            person = False
        elif tag.get("g") == "m":
            person = base.endswith(MASCULINE_PERSON) and (
                not base.endswith(LOOSE_MASCULINE) or web[form] >= LOOSE_MIN_USES * WEB_SCALE
            )
        elif base.endswith("ка"):
            person = web[form] >= KA_MIN_USES * WEB_SCALE
        elif base.endswith("ица"):
            person = web[form] >= ICA_MIN_USES * WEB_SCALE
        else:
            person = base.endswith(FEMININE_PERSON)
        if gender_m_irregular(base, tag):
            continue  # `човек` → `човече`, `юнак` → `юнако`: the -е rule is wrong
        if person and (web[form] >= 3 * WEB_SCALE or edited[form] >= 2):
            kept.add(form)
        elif base in by_rule and not form.endswith(("ачю", "ячю")):
            kept.add(form)  # a person by the language itself: its vocative needs no corpus use
        elif base in by_rule_if_used and web[form] + edited[form] >= 1:
            kept.add(form)  # `грешнице`: a -ница noun, and used as one
    OUT.write_text(
        "# Forms of address the dictionary lacks: built by tools/build_vocatives.py\n" + "\n".join(sorted(kept)) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(kept)} forms of address -> {OUT.name}")
    probes = ["мамо", "сине", "попе", "клиенте", "старче", "учителю", "сестро", "госпожице", "колего", "лельо"]
    print(" ".join(f"{p}:{'yes' if p in kept or spelling.in_dictionary(p) else 'no'}" for p in probes))


if __name__ == "__main__":
    main()
