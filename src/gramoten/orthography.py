"""Bulgarian orthography of numbers, abbreviations and ѝ, by rule.

Norms: the IBL rules ("Принципи и правила на правописа и пунктуацията"), BERON
and the EU DGT Bulgarian style guide (2021).

| Code | Rule | Fix |
|---|---|---|
| `pronoun_i` | the pronoun is `ѝ` since the 2012 dictionary; a standalone `й` is never a word | `ѝ` |
| `ordinal_suffix` | after digits: 1 `-ви`, 2 `-ри`, 3 and 4 `-ти`, every other ending one letter: `5-и`, `7-и`, `12-и`, `20-и`; `5-ти`, `7-ми`, `7-ма`, `20-ти` are wrong; the article follows the и: `14-ият`, `21-вият` | the right suffix |
| `ordinal_date` | a day before a month takes no suffix: `5-ти май` → `5 май` | the number |
| `ordinal_roman` | a Roman numeral takes no suffix: `XXI-ви век` → `XXI век` | the numeral |
| `number_adjective` | a number and an adjective in -годишен, -месечен, -дневен… are one word: `5 годишен` → `5-годишен`, `пет-годишен` → `петгодишен` | joined |
| `percent_adjective` | `10%-на` → `10-процентна` (DGT: the %-form is not acceptable) | spelled out |
| `title_period` | `г-н`, `г-жа`, `г-ца`, `д-р` take no full stop (BERON 75.2) | without it |
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import morphology


@dataclass(frozen=True)
class Hit:
    code: str
    start: int
    end: int
    message: str
    fix: str | None


MONTHS = (
    "януари",
    "февруари",
    "март",
    "април",
    "май",
    "юни",
    "юли",
    "август",
    "септември",
    "октомври",
    "ноември",
    "декември",
)
#: Adjective stems a number joins: `5-годишен`, `3-месечна`, `10-дневни`.
NUMBER_ADJECTIVE = (
    "годишн",
    "годишен",
    "месечн",
    "месечен",
    "дневн",
    "дневен",
    "седмичн",
    "седмичен",
    "часов",
    "минутн",
    "минутен",
    "секундн",
    "секунден",
    "метров",
    "километров",
    "етажн",
    "етажен",
    "звезд",
    "стаен",
    "стайн",
    "литров",
    "кратн",
    "кратен",
    "степенн",
    "степенен",
    "членн",
    "членен",
    "томн",
    "томен",
    "инчов",
    "ядрен",
    "процентн",
    "процентен",
    "сантиметров",
    "килограмов",
    "гигабайтов",
)
#: Left out: `вековни`, `местни` (`95 вековни дървета`, `11 местни депутати` count), a time
#: (`14:00 местно време`) and a reference (`параграф 6 годишни доклади`).
REFERENCE = re.compile(r"(?:параграф|член|чл\.|точка|т\.|алинея|ал\.|буква|раздел|глава|приложение)\s*$", re.I)
NUMBER_WORDS = (
    "едно",
    "дву",
    "три",
    "четири",
    "пет",
    "шест",
    "седем",
    "осем",
    "девет",
    "десет",
    "двадесет",
    "тридесет",
    "сто",
    "хиляд",
)
VOWELS = set("аеиоуъюяѝ")
#: Not ordinal endings: `80-те години`, `27-те страни` (the plural article of a
#: number, осемдесетте) and `5-ма души` (петима).
NOT_ORDINAL = {"те", "ма", "мата", "мина", "на", "ина", "ки", "ица"}  # and `100-на`, `10-ки`: approximate


#: An ordinal ending: an optional `в`/`р`/`м`/`т` and a vowel ending (`-ви`, `-ра`, `-тата`,
#: `-о`). Anything else after the hyphen is no ordinal: a word cut off (`30-годи`).
ORDINAL_ENDING = re.compile(r"[врмт]?(?:ият|ия|ата|ото|ите|ят|и|а|о|я)")


def _expected_head(number: str) -> str:
    """The consonant an ordinal suffix starts with after these digits: `в`, `р`, `т`, or none."""
    if 11 <= int(number[-2:] if len(number) > 1 else number) % 100 <= 19:
        return ""
    return {"1": "в", "2": "р", "3": "т", "4": "т"}.get(number[-1], "")


def _pronoun(text: str) -> list[Hit]:
    return [
        Hit("pronoun_i", m.start(), m.end(), "The pronoun is written „ѝ“", "ѝ")
        for m in re.finditer(r"(?<![\w-])й(?![\w-])", text)
    ]


def _singular_next(after: str) -> bool:
    """Whether the next word is a singular noun or adjective, so a `-ма` before it is an
    ordinal (`7-ма степен`) and not a count of people (`7-ма души`)."""
    m = re.match(r"([а-яА-Я]+)", after)
    readings = morphology.analyse(m.group(1)) if m else ()
    return bool(readings) and all(r.tag.get("n") == "s" and r.tag["pos"] in ("N", "A") for r in readings)


def _ordinals(text: str) -> list[Hit]:
    hits = []
    for m in re.finditer(r"(?<![\w.,/-])(\d{1,4})-([а-я]{1,4})(?![\w-])", text):
        number, suffix = m.group(1), m.group(2)
        after = text[m.end() : m.end() + 12].lstrip()
        if after.lower().startswith(MONTHS):
            hits.append(Hit("ordinal_date", m.start(), m.end(), "A day before the month takes no suffix", number))
            continue
        head = _expected_head(number)
        if suffix in ("ма", "мата") and number[-1] in "78" and _singular_next(after):
            # `7-ма степен` (седма), `8-мата година`; `7-ма души` (седмина) is a count
            ending = suffix[1:]
            hits.append(
                Hit(
                    "ordinal_suffix",
                    m.start(),
                    m.end(),
                    f"After {number} the ordinal takes one letter: {number}-{ending}",
                    f"{number}-{ending}",
                )
            )
            continue
        if suffix in NOT_ORDINAL or not ORDINAL_ENDING.fullmatch(suffix):
            continue
        if suffix in ("ят", "я") or suffix in (head + "ят", head + "я") and head:
            # `14-ят` -> `14-ият`, `21-вят` -> `21-вият`: the article after the ordinal's и
            right = f"{head}и{suffix[len(head) :] if head and suffix.startswith(head) else suffix}"
            hits.append(
                Hit(
                    "ordinal_suffix",
                    m.start(),
                    m.end(),
                    f"The ordinal's article: {number}-{right}",
                    f"{number}-{right}",
                )
            )
            continue
        if not head and suffix[0] not in VOWELS and len(suffix) > 1 and suffix[1] in VOWELS:
            hits.append(
                Hit(
                    "ordinal_suffix",
                    m.start(),
                    m.end(),
                    f"After {number} the ordinal takes one letter: {number}-{suffix[1:]}",
                    f"{number}-{suffix[1:]}",
                )
            )
        elif head and suffix[0] in VOWELS:
            hits.append(
                Hit(
                    "ordinal_suffix",
                    m.start(),
                    m.end(),
                    f"After {number} the ordinal takes „{head}“: {number}-{head}{suffix}",
                    f"{number}-{head}{suffix}",
                )
            )
    for m in re.finditer(r"(?<![\w-])([IVXLC]{1,8})-(ви|ри|ти|ми|и|ия|ият|та|ата|то)(?![\w-])", text):
        hits.append(Hit("ordinal_roman", m.start(), m.end(), "A Roman numeral takes no suffix", m.group(1)))
    return hits


def _number_adjectives(text: str) -> list[Hit]:
    hits = []
    stems = "|".join(sorted(set(NUMBER_ADJECTIVE), key=len, reverse=True))
    for m in re.finditer(r"(?<![\w.,:-])(\d{1,4}) ((?:%s)[а-я]*)(?![\w-])" % stems, text):
        if REFERENCE.search(text[max(0, m.start() - 20) : m.start()]):
            continue
        noun = re.match(r"\s+([а-яА-Я]+)", text[m.end() : m.end() + 40])
        if noun and any(r.tag.get("n") == "c" for r in morphology.analyse(noun.group(1))):
            continue  # the number counts the noun: `10 процентни пункта`, `3 часови пояса`
        hits.append(
            Hit(
                "number_adjective",
                m.start(),
                m.end(),
                "A number and this adjective are joined by a hyphen",
                f"{m.group(1)}-{m.group(2)}",
            )
        )
    numbers = "|".join(NUMBER_WORDS)
    for m in re.finditer(r"(?<![\w-])((?:%s)[а-я]*)-((?:%s)[а-я]*)(?![\w-])" % (numbers, stems), text, flags=re.I):
        if not m.group(1).lower().startswith(NUMBER_WORDS):
            continue
        hits.append(Hit("number_adjective", m.start(), m.end(), "Written as one word", m.group(1) + m.group(2)))
    return hits


PERCENT_ENDINGS = {
    "на": "процентна",
    "ен": "процентен",
    "но": "процентно",
    "ни": "процентни",
    "ната": "процентната",
    "ния": "процентния",
    "ният": "процентният",
    "ното": "процентното",
    "ните": "процентните",
}


def _percent(text: str) -> list[Hit]:
    return [
        Hit(
            "percent_adjective",
            m.start(),
            m.end(),
            "Write the percentage adjective out",
            f"{m.group(1)}-{PERCENT_ENDINGS[m.group(2)]}",
        )
        for m in re.finditer(
            r"(?<![\w.,])(\d{1,4}(?:,\d+)?) ?%-("
            + "|".join(sorted(PERCENT_ENDINGS, key=len, reverse=True))
            + r")(?![\w-])",
            text,
        )
    ]


def _titles(text: str) -> list[Hit]:
    return [
        Hit("title_period", m.start(), m.end(), f"„{m.group(1)}“ takes no full stop", m.group(1))
        for m in re.finditer(r"(?<![\w-])([Гг]-н|[Гг]-жа|[Гг]-ца|[Дд]-р)\.(?= [А-ЯA-Z])", text)
    ]


DETECTORS = (_pronoun, _ordinals, _number_adjectives, _percent, _titles)


def check(text: str) -> list[Hit]:
    hits = [hit for detector in DETECTORS for hit in detector(text)]
    return sorted(hits, key=lambda h: (h.start, h.end, h.code))
