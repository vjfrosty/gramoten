"""Telecommunications terms, with every inflected form, for the spelling check.

    python -I tools/build_telecom_words.py

The terms are the words missing from the dictionary in real telecom Bulgarian:
- the Electronic Communications Act (lex.bg);
- the CRC glossary;
- telecom operators' public pages;
- bg.wikipedia articles (5G, LTE, optical fibre, router, roaming, Wi-Fi, …);
- news and Wikipedia text read for telecom context.

Each term declines like a model word of the bgOffice lexicon with the same
ending (`гигабит` like `бюджет`, `полудуплексен` like `безплатен`): the
model's forms, with its ending swapped for the term's. A model that is not in
the lexicon stops the build.

Writes `gramoten/data/telecom_words.txt`, one form per line, which
`spelling.project_words` reads with `project_words.txt`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gramoten import morphology, spelling  # noqa: E402

OUT = ROOT / "src" / "gramoten" / "data" / "telecom_words.txt"

#: model lemma -> terms that decline like it.
TERMS: dict[str, list[str]] = {
    # masculine nouns ending in a consonant
    "бюджет": [
        "гигабит",
        "килобит",
        "терабит",
        "петабит",
        "мегабит",
        "хотспот",
        "репитер",
        "аплинк",
        "даунлинк",
        "суич",
        "пинг",
        "спам",
        "транспондер",
        "мултиплексор",
        "демултиплексор",
        "фидер",
        "телеком",
        "вълновод",
        "сплитер",
        "бекъп",
        "хостинг",
        "сървър",
        "мегабайт",
        "гигабайт",
        "терабайт",
        "килобайт",
        "петабайт",
        "декодер",
        "модул",
        "конектор",
        # common modern words, with every form
        "рутер",
        "смартфон",
        "таблет",
        "смартчасовник",
        "имейл",
        "промокод",
        "уебсайт",
        "ваучер",
        "линк",
        "чатбот",
        "стрийминг",
        "подкаст",
        "тракер",
        "брифинг",
        "гейминг",
        "уикенд",
        "сингъл",
        "лаптоп",
    ],
    # feminine nouns
    "карта": ["симкарта", "фонокарта"],
    "жилетка": ["оплетка", "развивка", "приставка"],
    "технология": ["топология", "телеметрия"],
    "служба": ["радиослужба"],
    "оперативност": ["междуоперативност", "свързаност", "пропускливост", "преносимост"],
    # adjectives in -ен (the е drops: полудуплексна)
    "безплатен": [
        "полудуплексен",
        "дуплексен",
        "радиотелефонен",
        "далекосъобщителен",
        "двуфакторен",
        "трафичен",
        "безлимитен",
        "следплатен",
        "предплатен",
        "радиочестотен",
        "антенен",
        "оптоелектронен",
        "абонатен",
        "абонаментен",
        "комутационен",
    ],
    "линеен": ["радиорелеен"],
    # adjectives in -ов
    "розов": [
        "едномодов",
        "многомодов",
        "гигабитов",
        "мегабитов",
        "дециметров",
        "милиметров",
        "сантиметров",
        "роумингов",
        "широколентов",
    ],
    # adjectives in -ем
    "адресируем": ["комутируем", "конфигурируем", "мащабируем"],
}


def model_lemma(word: str) -> int:
    for reading in morphology.analyse(word):
        if reading.base == word:
            return reading.lemma
    raise SystemExit(f"model {word!r} is not a lemma in the lexicon")


def forms_like(term: str, model: str) -> set[str]:
    """`model`'s forms with `model`'s ending swapped for `term`'s."""
    found = {f for fs in morphology.forms(model_lemma(model)).values() for f in fs}
    keep = len(min(found, key=len))
    stem = model[:keep]
    while not all(f.startswith(stem) for f in found):
        keep -= 1
        stem = model[:keep]
    tail = model[keep:]
    if not term.endswith(tail):
        raise SystemExit(f"{term!r} does not end like its model {model!r} ({tail!r})")
    new_stem = term[: len(term) - len(tail)] if tail else term
    return {new_stem + f[keep:] for f in found}


def main() -> None:
    out: set[str] = set()
    for model, terms in TERMS.items():
        for term in terms:
            out |= forms_like(term, model)
    new = sorted(f for f in out if not spelling.in_dictionary(f))
    OUT.write_text(
        "# Telecommunications terms, every form: built by tools/build_telecom_words.py\n" + "\n".join(new) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(out)} forms of {sum(map(len, TERMS.values()))} terms; {len(new)} new -> {OUT.name}")


if __name__ == "__main__":
    main()
