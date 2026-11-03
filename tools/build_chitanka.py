"""Chitanka's dictionary (Речко): known misspellings, and forbidden forms.

    uv run --no-project --python 3.13 --with marisa-trie==1.4.1 python -I \
        tools/build_chitanka.py CHITANKA DOWNLOADS

CHITANKA holds `words.csv` and `incorrect_forms.csv`
from https://huggingface.co/datasets/vislupus/bulgarian-dictionary-raw-data,
a copy of rechnik.chitanka.info, under the MIT licence (dataset card;
Chitanka's code is MIT too). DOWNLOADS is `build_modern_words.py`'s
folder (Leipzig news and Wikipedia), which supplies attestation.

Chitanka's word forms are not used: Речко generated them from bgOffice data
(rechnik.chitanka.info/about).

Writes to `gramoten/data/`:
* `misspellings.marisa`: `wrong → right` from Chitanka's misspelling table,
  for the entries people searched for. A spelling suggestion puts the
  known correction first (`очудване` → `учудване`).
* `forbidden_words.txt`: forms the added lists (modern, telecom, EU, project
  words) wrongly accept:
  - Chitanka misspellings whose right form is at least 5 times as common in
    news and Wikipedia (`безмислено`, `фармацефт`); the table is user-made, so
    a valid word it lists (`кампус` → `кампос`) is kept by that comparison;
  - не glued to a finite verb or gerund (`незнам`, `неможе`, `незнаейки`: BERON §62);
    participles are left alone, since joined they are adjectives (`неработещ`);
  - colloquial 1st-person plurals in -ме (`ходиме` for `ходим`).
  bgOffice always wins: a form the dictionary knows is never forbidden.
"""

from __future__ import annotations

import collections
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import marisa_trie  # noqa: E402
from build_modern_words import LEIPZIG, leipzig_counts  # noqa: E402

from gramoten import morphology, spelling  # noqa: E402

DATA = ROOT / "src" / "gramoten" / "data"
csv.field_size_limit(10**9)


def rows(path: Path):
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, skipinitialspace=True):
            if not (row.get("deleted_at") or "").strip():
                yield row


FINITE = {"pres", "aor", "impf", "imp", "ger"}
#: Loanwords Chitanka maps to a near native word (`хаус` → `хаос`): right as they are.
LOANWORDS = {"хаус", "реднек"}


def is_verb(word: str) -> bool:
    return any(r.tag["pos"] == "V" for r in morphology.analyse(word))


def finite_only(word: str) -> bool:
    """Every reading is a finite verb form or a gerund. A participle takes не
    together as an adjective (`неработещ`), and so does a word that can be an
    adjective (`нелюбим`: `любим` is a verb form and an adjective)."""
    readings = morphology.analyse(word)
    return bool(readings) and all(r.tag["pos"] == "V" and r.tag.get("v") in FINITE for r in readings)


#: The classic glued forms, whose verb also has another reading (`знам`, a banner).
KNOWN_GLUED = set(
    """незнам незнаеш незнае незнаем незнаете незнаят неискам неискаш неиска неискаме неискате
неискат неможем неможете немогат немога неща нещеш нещат""".split()
)


def main() -> None:
    chitanka, downloads = Path(sys.argv[1]), Path(sys.argv[2])
    # Judge against everything but this script's own forbidden list, or a second
    # run would find nothing new (a word list must not grade itself).
    spelling.forbidden_words = lambda: frozenset()  # type: ignore[assignment]
    spelling.clear_suggestions()
    (news, _), (wiki, _) = (leipzig_counts(downloads, name) for name in LEIPZIG)
    edited = news + wiki

    lemmas = {row["id"]: row["name"].strip().lower() for row in rows(chitanka / "words.csv")}
    misspelt: dict[str, tuple[str, int]] = {}
    for row in rows(chitanka / "incorrect_forms.csv"):
        wrong, right = row["name"].strip().lower(), lemmas.get(row["correct_word_id"], "")
        count = int(row["search_count"] or 0)
        if right and " " not in wrong and wrong != right and count >= misspelt.get(wrong, ("", -1))[1]:
            misspelt[wrong] = (right, count)

    pairs = {w: r for w, (r, c) in misspelt.items() if c >= 1 and not spelling.in_dictionary(w)}
    marisa_trie.BytesTrie((w, r.encode("utf-8")) for w, r in pairs.items()).save(str(DATA / "misspellings.marisa"))

    forbidden = collections.Counter()
    added_lists = set(spelling._modern().keys()) | spelling.project_words()
    vocatives = spelling._read_words("vocative_words.txt")  # forms of address: right by their own build
    for word in added_lists:
        if spelling.in_dictionary(word):
            continue
        if word in LOANWORDS or word in vocatives:
            continue
        if word in misspelt:
            right, count = misspelt[word]
            if edited[right] >= 5 * max(edited[word], 1):
                forbidden[word] = "chitanka"
        elif (
            word in KNOWN_GLUED
            or (
                word.startswith("не")
                and not word.startswith("недо")
                and not word.endswith(("им", "ем"))  # `неизтребим`: an adjective
                and finite_only(word[2:])
                and not is_verb(word)
            )
        ):
            forbidden[word] = "не + verb"
        elif (
            word.endswith(("еме", "име"))
            and is_verb(word[:-1])
            and any(r.tag.get("p") == "1" and r.tag.get("n") == "p" for r in morphology.analyse(word[:-1]))
        ):
            forbidden[word] = "-ме"
    (DATA / "forbidden_words.txt").write_text(
        "# Forms the added word lists wrongly accept: built by tools/build_chitanka.py\n"
        + "\n".join(sorted(forbidden))
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(
        f"{len(lemmas)} lemmas, {len(misspelt)} misspellings ({len(pairs)} searched); "
        f"{len(forbidden)} forbidden {dict(collections.Counter(forbidden.values()))}"
    )
    print("forbidden:", " ".join(sorted(forbidden)))


if __name__ == "__main__":
    main()
