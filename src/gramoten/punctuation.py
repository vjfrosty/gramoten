"""Bulgarian commas and punctuation, by rule, with no model.

Checked: a comma before a conjunction (че, когато, ако, защото, за да, както
и, отколкото, след като) or a който-word, before `но` and the second `нито`,
around a vocative; a split compound conjunction (`въпреки, че`), doubled marks,
unbalanced brackets and unclosed quotes.

Left out on purpose: a comma before the preposition of `в която`,
`Например,` (correct by ОПР 81.2, but house style), a fronted `Ако…` clause, a
missing final full stop, plain `да`, `или … или`, `ала`, and anything needing
grammar (`и` in lists, `като`, `обаче`, colon and semicolon).

Rules: ОПР 2012 (Официален правописен речник), via the Institute for Bulgarian
Language's answers, kaksepishe.com and the EU translators' Bulgarian style guide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import spelling
from .tokenize import before

NAME_PH = r"(?:\{P:(?i:first_?name|name|ime)\}|%%=?[^%]{0,30}(?i:first_?name|ime)[^%]{0,20}%%)"
_LAT2CYR = str.maketrans(dict(zip("aeopcxyAEOPCXYBKMHT", "аеорсхуАЕОРСХУВКМНТ", strict=True)))
_CYR = re.compile(r"[А-Яа-яЁёЍѝЪъ]")
_WORD = re.compile(r"[A-Za-zА-Яа-яЁёЍѝЪъ]+")


def normalise(text: str) -> str:
    """Same length as `text`: lookalike letters made Cyrillic, other placeholders masked."""

    def fix(m: re.Match) -> str:
        w = m.group(0)
        return w.translate(_LAT2CYR) if _CYR.search(w) and re.search(r"[A-Za-z]", w) else w

    t = _WORD.sub(fix, text)
    t = re.sub(r"(?<=[а-я] )a(?= [а-я])", "а", t)
    t = re.sub(
        r"%%\[.*?\]%%|%%=.*?=%%|%%[^%\s]{1,60}%%|\{P:[^{}]{1,60}\}",
        lambda m: m.group(0) if re.fullmatch(NAME_PH, m.group(0)) else "◊" * len(m.group(0)),
        t,
        flags=re.S,
    )
    t = re.sub(r"\b(?:https?://|www\.)\S+", lambda m: "◊" * len(m.group(0)), t)
    return t.replace("\xa0", " ")


# -- word lists --------------------------------------------------------------

#: After these a following conjunction takes no comma (ОПР 2012: no comma
#: between two conjunctions, nor after a particle such as само, дори, именно).
NO_COMMA_PREV = set(
    """
и а но или ни нито че да не пък та па ами ала
само дори даже именно особено едва тъкмо точно чак поне още също просто включително
може би сигурно вероятно навярно освен и още
който която което които чийто чиято чието чиито когато където защото ако докато отколкото
понеже като щом макар въпреки преди след за без
понякога обикновено често винаги главно предимно най-вече единствено отчасти почти най-малко
например всъщност впрочем наистина следователно обаче действително навярно сякаш както
по-специално веднага ама май добре
""".split()
)
PREPS = set(
    """в във на с със за от до при чрез без към по през под над пред срещу според след
преди между сред заради около въпреки покрай извън освен измежду поради съгласно спрямо
относно посредством вследствие благодарение у върху зад край из въз вместо подир отвъд""".split()
)
REL = r"(?:който|която|което|които|чийто|чиято|чието|чиито|когото)"
#: Conjunction -> previous words it legitimately joins (compound conjunctions).
CONJ: dict[str, set[str]] = {
    "че": {
        "въпреки",
        "макар",
        "така",
        "освен",
        "само",
        "като",
        "все",
        "случай",
        "положение",
        "условие",
        "затова",
        "дето",
        "нали",
        "ето",
        "щом",
        "тъй",
        "независимо",
    },
    "защото": set(),
    "понеже": set(),
    "когато": {"от", "до", "тогава"},
    "където": {"от", "до", "там"},
    "ако": {"освен", "като"},
    "докато": {"до"},
    "отколкото": set(),
    # `10 минути след като`: how long after, no comma.
    "след като": {
        "секунди",
        "секунда",
        "минути",
        "минута",
        "часа",
        "час",
        "дни",
        "ден",
        "седмици",
        "седмица",
        "месеца",
        "месец",
        "години",
        "година",
    },
    "тъй като": set(),
    "въпреки че": set(),
    "макар че": set(),
    "за да": set(),
    "без да": set(),
    "както и": set(),
}
GREETINGS = r"(?:Здравей|Здравейте|Добър ден|Добро утро|Добър вечер|Привет|Здрасти)"
GREET_NOT_VOC = set("отново пак и на от за днес още всички".split())
SPLIT_COMPOUNDS = (
    "въпреки, че",
    "макар, че",
    "след, като",
    "тъй, като",
    "без, да",
    "в случай, че",
    "при положение, че",
    "при условие, че",
    "освен, ако",
    "като, че ли",
)


@dataclass(frozen=True)
class Hit:
    code: str
    start: int
    end: int
    message: str
    fix: str | None = None


def _prev_word(text: str, idx: int) -> tuple[str | None, int | None]:
    window = before(text, idx)
    m = re.search(r"([\w\-}%»“”\")]+)(\s+)$", window)
    return (m.group(1), idx - len(window) + m.start(1)) if m else (None, None)


def _ok_prev(word: str) -> bool:
    """A token that can end a clause; a placeholder or a short unknown token keeps the rule quiet."""
    if "◊" in word:
        return False
    if not re.fullmatch(r"[\w\-]*[\wА-Яа-я][%“”\")]*|[\w\-]*%|[0-9][\w.,]*", word):
        return False
    bare = re.sub(r"[%“”\")]+$", "", word)
    return len(word) > 4 or not _CYR.search(bare) or spelling.in_dictionary(bare.lower())


def _comma_before(text: str, prev_start: int, prev: str, start: int, end: int) -> tuple[int, str]:
    """The span from the previous word's end to the conjunction's end, and that span with the comma."""
    gap_start = prev_start + len(prev)
    return gap_start, "," + text[gap_start:end]


# -- detectors -------------------------------------------------------------


def _conjunctions(text: str) -> list[Hit]:
    hits = []
    for conj, glue in CONJ.items():
        for m in re.finditer(r"(?<![\w-])" + conj.replace(" ", r"\s+") + r"(?![\w-])", text):
            s = m.start()
            if s == 0 or text[s - 1] != " ":
                continue
            prev, prev_start = _prev_word(text, s)
            if not prev or prev_start is None or not _ok_prev(prev):
                continue
            low = prev.lower()
            if low in NO_COMMA_PREV or low in glue or low in PREPS:
                continue
            if re.search(r"(може би|като че ли|дори и|само и|още повече|преди всичко)\s+$", before(text, s).lower()):
                continue
            gap, fixed = _comma_before(text, prev_start, prev, s, m.end())
            hits.append(Hit("comma_before_conjunction", gap, m.end(), f"Comma before „{conj}“", fixed))
    return hits


def _relatives(text: str) -> list[Hit]:
    """A който-word straight after a word; with a preposition between, the rule is too unreliable, so it is left out."""
    hits = []
    for m in re.finditer(r"(?<![\w-])%s(?![\w-])" % REL, text):
        s = m.start()
        if s == 0 or text[s - 1] != " ":
            continue
        prev, prev_start = _prev_word(text, s)
        if not prev or prev_start is None or not _ok_prev(prev):
            continue
        if prev.lower() in NO_COMMA_PREV or prev.lower() in PREPS:
            continue
        if re.compile(
            r"\s*(и да е|и да|иска|искаш|искате|желаеш|желаете|предпочиташ|предпочитате|"
            r"харесаш|харесате|ти харесва|Ви харесва|ви харесва)(?![\w-])"
        ).match(text, m.end()):
            continue  # free relative: "вземи която искаш" takes no comma
        gap, fixed = _comma_before(text, prev_start, prev, s, m.end())
        hits.append(Hit("comma_before_relative", gap, m.end(), f"Comma before „{m.group(0)}“", fixed))
    return hits


def _adversative(text: str) -> list[Hit]:
    hits = []
    for m in re.finditer(r"(?<![\w-])но(?![\w-])", text):
        s = m.start()
        if s == 0 or text[s - 1] != " " or not re.match(r" [а-яА-Я0-9{%„\"]", text[m.end() : m.end() + 2]):
            continue
        prev, prev_start = _prev_word(text, s)
        if (
            not prev
            or prev_start is None
            or not _ok_prev(prev)
            or prev.lower() in NO_COMMA_PREV
            or prev.lower() in PREPS
        ):
            continue
        gap, fixed = _comma_before(text, prev_start, prev, s, m.end())
        hits.append(Hit("comma_before_conjunction", gap, m.end(), "Comma before „но“", fixed))
    return hits


def _repeated(text: str) -> list[Hit]:
    hits = []
    for m in re.finditer(r"(?:^|(?<=[,:;.!?] ))(нито|Нито) ([^,.;:!?]{1,60}?) (нито)(?![\w-])", text):
        start = m.start(3) - 1
        hits.append(Hit("comma_repeated_conjunction", start, m.end(3), "Comma before the second „нито“", ", нито"))
    return hits


def _vocative(text: str) -> list[Hit]:
    hits = []
    for m in re.finditer(
        r"(?<![\w-])(%s)( +)(%s|[А-ЯA-Z][а-яa-z]+|приятели|приятелю|клиенти)" % (GREETINGS, NAME_PH), text
    ):
        if m.group(3).lower() in GREET_NOT_VOC:
            continue
        hits.append(
            Hit(
                "comma_vocative",
                m.start(),
                m.end(),
                "Comma after the greeting, before the name",
                f"{m.group(1)}, {m.group(3)}",
            )
        )
    for m in re.finditer(NAME_PH, text):
        prev, _ = _prev_word(text, m.start())
        bad_after = re.match(r" [а-яА-Яa-zA-Z]", text[m.end() : m.end() + 2])
        bad_before = (
            prev is not None
            and re.match(r"^[а-яА-Я]", prev)
            and prev.lower() not in PREPS
            and not re.fullmatch(GREETINGS, prev)
        )
        if bad_after or bad_before:
            hits.append(Hit("comma_vocative", m.start(), m.end(), "Set the name off with commas"))
    return hits


def _split_compounds(text: str) -> list[Hit]:
    hits = []
    for pattern in SPLIT_COMPOUNDS:
        for m in re.finditer(r"(?<![\w-])" + re.escape(pattern) + r"(?![\w-])", text, flags=re.I):
            whole = m.group(0).replace(",", "")
            hits.append(
                Hit(
                    "comma_inside_compound",
                    m.start(),
                    m.end(),
                    f"„{whole}“ is one conjunction; the comma goes before it",
                    whole,
                )
            )
    for m in re.finditer(
        r"(?<![\w-])(в|във|на|с|със|за|от|до|при|чрез|без|към|по|през|под|над|пред|у|"
        r"върху|зад|из), (%s)(?![\w-])" % REL,
        text,
    ):
        hits.append(
            Hit(
                "comma_inside_compound",
                m.start(),
                m.end(),
                f"The comma goes before the preposition: „…, {m.group(1)} {m.group(2)}“",
            )
        )
    return hits


def _marks(text: str) -> list[Hit]:
    hits = []
    # `,,Хенри Форд”`: two commas typed for the opening quote.
    for m in re.finditer(r"(?<![,\w]),,(?=[„\"“]?[^\W\d_])", text):
        hits.append(Hit("comma_comma_quote", m.start(), m.end(), "Two commas typed for the opening quote „", "„"))
    for m in re.finditer(r"([,;:]) ?([,;:])|([,;]) ?(\.)(?!\.)", text):
        if (
            text[m.start() : m.end()] == ",,"
            and re.compile(r"[„\"“]?[^\W\d_]").match(text, m.end())
            and not re.match(r"[,\w]", text[m.start() - 1 : m.start()] if m.start() else "")
        ):
            continue  # reported above as `comma_comma_quote`
        if re.search(r"\(\s*$", before(text, m.start())) or re.compile(r"[,;:. ]*\)").match(text, m.end()):
            continue  # "(, , )": an emptied placeholder list
        if re.search(GREETINGS + r"$", before(text, m.start())):
            continue  # "Здравейте, !": an empty name in a rendered preview
        hits.append(Hit("double_punctuation", m.start(), m.end(), "Two punctuation marks in a row"))
    return hits


def _balance(text: str) -> list[Hit]:
    hits = []
    stack: list[int] = []
    for m in re.finditer(r"[()]", text):
        i = m.start()
        if text[i] == "(":
            stack.append(i)
        elif stack:
            stack.pop()
        elif not re.search(
            r"(?:^|\s|\()(?:[0-9а-яa-zА-ЯA-Z]{1,2}|[ivxlcIVXLC]{1,6})$|[:;]-?$", before(text, i)
        ):  # "1)", "а)", "iii)", ":)"
            hits.append(Hit("unbalanced_bracket", i, i + 1, "A bracket with no partner"))
    hits += [Hit("unbalanced_bracket", i, i + 1, "A bracket with no partner") for i in stack]
    opened: list[int] = []
    for m in re.finditer(r"[„“”\"]", text):
        if m.group(0) == "„":
            opened.append(m.start())
        elif opened:
            opened.pop()
    hits += [Hit("unbalanced_quote", i, i + 1, "„ is never closed") for i in opened]
    return hits


DETECTORS = (_conjunctions, _relatives, _adversative, _repeated, _vocative, _split_compounds, _marks, _balance)


def check(text: str) -> list[Hit]:
    """Every hit, ordered by position; offsets are into `text` (normalising keeps its length)."""
    normal = normalise(text)
    hits = [hit for detector in DETECTORS for hit in detector(normal)]
    # A fix is written from the normalised text; where that differs (a lookalike
    # letter in the span) the mixed-script fix comes first and this one waits.
    hits = [
        h
        if h.fix is None or normal[h.start : h.end] == text[h.start : h.end]
        else Hit(h.code, h.start, h.end, h.message)
        for h in hits
    ]
    return sorted(hits, key=lambda h: (h.start, h.end, h.code))
