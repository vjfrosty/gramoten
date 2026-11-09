"""Bulgarian grammar and usage, by rule: the forms a spellchecker cannot see.

Every word here is spelt right, and still wrong in its place: `на сайтът`, `с
запазени`, `до сега`, `и и`.

| Code | Rule |
|---|---|
| `article_after_preposition` | after a preposition a masculine word takes the short article: `от сумарният` → `от сумарния` (ОПР 2012, т. 17.6) |
| `v_vav`, `s_sas` | `във` before в/ф, `със` before с/з, and only there: `с запазени` → `със запазени` |
| `repeated_word` | a function word twice: `и и`, `на на` (`си си` is right) |
| `written_together` | `до сега` → `досега`, `в къщи` → `вкъщи`, `в предвид` → `предвид`, `тъмно зелен` → `тъмнозелен`; with a hyphen: `току що` → `току-що`, `министър председател` → `министър-председател` |
| `superlative_hyphen` | `най много` → `най-много` |
| `number_range` | `10-12 юли` → `10–12 юли` |

Left out as unreliable: `ви` where the text writes `Ви` elsewhere, a full
article on a subject or after `е`, the object after an imperative, a capital
after a full stop, `, щото`, and the comma before `включително`.

Words written with a capital mid-sentence are names and are skipped (product
names such as `в Моят Профил`), except the polite `Вашият`. All-capital
and digit tokens (СС, SEO, S10) are read letter by letter, so `с SEO` is not
an error. Every fix is a form the dictionary knows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import morphology, spelling
from .punctuation import normalise

W = r"[А-Яа-яЍѝ]"
B = r"(?<![\w-])"
E = r"(?![\w-])"

PREPS = """в във на с със за от до при чрез без към по през под над пред срещу според след
преди между сред заради около покрай извън измежду поради съгласно спрямо относно посредством
вследствие у върху зад край из въз подир отвъд""".split()


@dataclass(frozen=True)
class Hit:
    code: str
    start: int
    end: int
    message: str
    #: The replacement; `""` deletes the span.
    fix: str | None


def _known(word: str) -> bool:
    return all(not re.search(r"[а-я]", part) or spelling.in_dictionary(part) for part in word.lower().split("-"))


def _case(fix: str, like: str) -> str:
    return fix[0].upper() + fix[1:] if like[:1].isupper() else fix


# -- the short article after a preposition ------------------------------------


def _short_of_full(word: str) -> str | None:
    """`сайтът` → `сайта`, `новият` → `новия`; None unless it is a masculine full article."""
    low = word.lower()
    if not spelling.in_dictionary(low) or any(spelling.in_dictionary(low + end) for end in "аяи"):
        return None  # `лакът`, `нокът`, `свят`: the -ът/-ят belongs to the word
    readings = morphology.analyse(low)
    if readings and not any(r.tag.get("d") == "f" for r in readings):
        return None  # a verb such as `говорят`: no full article
    if low.endswith("ът"):
        base, short = low[:-2], low[:-2] + "а"
        if len(base) >= 2 and spelling.in_dictionary(base) and spelling.in_dictionary(short):
            return _case(short, word)
    elif low.endswith("ят"):
        short = low[:-1]
        bases = (low[:-2], low[:-2] + "й", low[:-3] if low.endswith("ият") else "")
        if spelling.in_dictionary(short) and any(b and len(b) >= 2 and spelling.in_dictionary(b) for b in bases):
            return _case(short, word)
    return None


def _article_after_preposition(text: str) -> list[Hit]:
    hits = []
    pattern = B + r"(%s) ((?:най-|по-)?%s+(?:ът|ят))%s" % ("|".join(PREPS + [p.capitalize() for p in PREPS]), W, E)
    for m in re.finditer(pattern, text):
        word = m.group(2)
        core = re.sub(r"^(?:най-|по-)", "", word)
        if core[:1].isupper() and core.lower() != "вашият":
            continue  # a name or a title: `на Денят на…`
        short = _short_of_full(core)
        if not short:
            continue
        after = re.split(r"[,.;:!?–—()]", text[m.end() : m.end() + 120])[0]
        if m.group(1).lower() in ("преди", "след", "докато", "без", "вместо") and re.search(
            r"(?<![\w-])да(?![\w-])", after
        ):
            continue  # `преди изпълнителят да…`: the subject of a да-clause
        hits.append(
            Hit(
                "article_after_preposition",
                m.start(2),
                m.end(2),
                "After a preposition the word takes the short article (-а/-я)",
                word[: len(word) - len(core)] + short,
            )
        )
    return hits


# -- в/във, с/със --------------------------------------------------------------

_ROMAN = re.compile(r"[IVXLCM]+")


def _first_sound(word: str) -> str | None:
    """The next word's first sound, or None when it is read letter by letter or unsure."""
    if _ROMAN.fullmatch(word):
        return None
    head = re.match(r"[^\W\d_]+", word)
    if head is None or re.search(r"\d", word) or head.group(0).isupper():
        return None  # СС, SEO, S10, `В-2`
    first = word[0].lower()
    if re.match(r"[а-я]", first):
        return first
    return {"f": "ф", "v": "в", "s": "с", "z": "з"}.get(first)


def _v_s(text: str) -> list[Hit]:
    hits = []
    for m in re.finditer(r"(?<![\w-])(в|във|В|Във|с|със|С|Със)( [„\"«(]?)([\w][\w-]*)", text):
        prep, following = m.group(1), m.group(3)
        if text[m.start(1) - 1 : m.start(1)] == "." or text[m.end(1) : m.end(1) + 1] != " ":
            continue
        if following.lower() in ("в", "във", "с", "със"):
            continue  # `влиза в в парламента`: a doubled preposition (`repeated_word`), not в/във
        sound = _first_sound(following)
        if sound is None:
            continue
        low = prep.lower()
        stressed = following.lower() in ("и", "или", "извън", "без", "вън")  # `със или без`
        if low == "в" and sound in "вф":
            hits.append(Hit("v_vav", m.start(1), m.end(1), "Before в or ф write „във“", _case("във", prep)))
        elif low == "във" and sound not in "вф" and not stressed:
            hits.append(Hit("v_vav", m.start(1), m.end(1), "„във“ goes only before в or ф; here „в“", _case("в", prep)))
        elif low == "с" and sound in "сз":
            if text[m.start(1) - 2 : m.start(1)].strip().endswith(tuple("0123456789")):
                continue  # `5 с`: a unit
            hits.append(Hit("s_sas", m.start(1), m.end(1), "Before с or з write „със“", _case("със", prep)))
        elif low == "със" and sound not in "сз" and not stressed:
            hits.append(Hit("s_sas", m.start(1), m.end(1), "„със“ goes only before с or з; here „с“", _case("с", prep)))
    return hits


# -- най- ------------------------------------------------------------------------

_NOT_AFTER_NAI = {"и", "да", "не", "ми", "ти", "му", "ѝ", "й", "ни", "ви", "им", "се", "си", "е"}


def _superlative(text: str) -> list[Hit]:
    hits = []
    for m in re.finditer(B + r"([Нн]ай)(?: +| *- +| +- *)(%s+)%s" % (W, E), text):
        word = m.group(2)
        if _known(word) and word.lower() not in _NOT_AFTER_NAI:
            hits.append(
                Hit(
                    "superlative_hyphen",
                    m.start(),
                    m.end(),
                    "„най-“ is written with a hyphen and no space",
                    m.group(1) + "-" + word,
                )
            )
    for m in re.finditer(B + r"([Нн]ай)(%s{3,})%s" % (W, E), text):
        whole, tail = m.group(0), m.group(2)
        if not _known(whole) and _known(tail) and not whole[0].isupper():
            hits.append(
                Hit(
                    "superlative_hyphen", m.start(), m.end(), "„най-“ is written with a hyphen", m.group(1) + "-" + tail
                )
            )
    return hits


# -- written together ---------------------------------------------------------------

#: (wrong, right), from ОПР 2012 via kaksepishe.com and ИБЕ „Пиши правилно“.
TOGETHER = [
    ("в същност", "всъщност"),
    ("из общо", "изобщо"),
    ("из веднъж", "изведнъж"),
    ("в последствие", "впоследствие"),
    ("в следствие", "вследствие"),
    ("в къщи", "вкъщи"),
    ("на всякъде", "навсякъде"),
    ("на пример", "например"),
    ("за винаги", "завинаги"),
    ("на последък", "напоследък"),
    ("из цяло", "изцяло"),
    ("по някога", "понякога"),
    ("в предвид", "предвид"),
    ("впредвид", "предвид"),
    ("пред вид", "предвид"),
    ("до сега", "досега"),
    ("до тогава", "дотогава"),
    ("на скоро", "наскоро"),
    ("за напред", "занапред"),
    ("на вън", "навън"),
    ("от вън", "отвън"),
    ("от вътре", "отвътре"),
    ("в ляво", "вляво"),
    ("в дясно", "вдясно"),
    ("на ляво", "наляво"),
    ("на дясно", "надясно"),
    ("на горе", "нагоре"),
    ("на долу", "надолу"),
    ("до кога", "докога"),
    ("до когато", "докогато"),
    ("до тук", "дотук"),
    ("до там", "дотам"),
    ("до преди", "допреди"),
    ("до къде", "докъде"),
    ("до където", "докъдето"),
    ("до някъде", "донякъде"),
    ("до колко", "доколко"),
    ("до колкото", "доколкото"),
    ("от тук", "оттук"),
    ("от там", "оттам"),
    ("от кога", "откога"),
    ("по настоящем", "понастоящем"),
    ("на вред", "навред"),
    ("по-вече", "повече"),
    ("по-не", "поне"),
    ("от части", "отчасти"),
    ("от колкото", "отколкото"),
    ("до като", "докато"),
    ("по ради", "поради"),
    ("из между", "измежду"),
    ("току що", "току-що"),
    ("ноу хау", "ноу-хау"),
    ("министър председател", "министър-председател"),
]
#: All of them in one search: no entry can run into another, since each starts with a
#: preposition and none ends with one, so the hits are the same as one search each.
_TOGETHER = re.compile(
    B
    + "(?:%s)"
    % "|".join(re.escape(wrong).replace(r"\ ", " +") for wrong, _ in sorted(TOGETHER, key=lambda p: -len(p[0])))
    + E,
    re.I,
)
_TOGETHER_BY = {wrong: right for wrong, right in TOGETHER}


#: An adverb and an adjective written as one word (ОПР): a shade of a colour
#: (`тъмнозелен`, `светлокафяв`, `бледорозов`), `научноизследователски`,
#: `световноизвестен`. Flagged only when the joined word is in the dictionary and the
#: second word can only be an adjective. A hyphen is joined too, except where it is
#: right: `научно-технически` (two equal parts).
_JOINED_ADJECTIVE = re.compile(
    B
    + r"((?:[Тт]ъмно|[Сс]ветло|[Бб]ледо|[Яя]рко)(?: +|-)([а-я]+)"
    + r"|[Нн]аучно(?: +|-)(изследователск[а-я]*)"
    + r"|[Сс]ветовно +(известн[а-я]*))"
    + E
)


#: A prefix cut off from its word by a hyphen and a space: `пра- внучката`.
_SPLIT_PREFIX = re.compile(B + r"([Пп]ра|[Пп]ре|[Пп]ри|[Пп]ро)- +([а-я]+)" + E)


def _split_prefixes(text: str) -> list[Hit]:
    hits = []
    for m in _SPLIT_PREFIX.finditer(text):
        joined = m.group(1) + m.group(2)
        if spelling.is_correct(joined):
            hits.append(Hit("written_together", m.start(), m.end(), f"Written together: „{joined}“", joined))
    return hits


def _joined_adjectives(text: str) -> list[Hit]:
    hits = []
    for m in _JOINED_ADJECTIVE.finditer(text):
        first = re.match(r"[А-Яа-я]+", m.group(1)).group(0)  # type: ignore[union-attr]
        second = m.group(2) or m.group(3) or m.group(4)
        joined = first + second
        readings = morphology.analyse(second)
        if not readings or not all(r.tag["pos"] == "A" for r in readings):
            continue
        if not spelling.is_correct(joined):
            continue
        hits.append(Hit("written_together", m.start(), m.end(), f"Written together: „{joined}“", joined))
    return hits


#: Words after `доколко` that cannot be what `колко` counts: verbs' little helpers,
#: short pronouns and particles (`Доколко е важно`, `доколкото ми е известно`).
_AFTER_DOKOLKO = frozenset(
    "е са съм си сме сте бил била било били би ще да се ли не ми ти му ѝ й им ни ви го я ги".split()
)
#: Verb forms that are also a counted plural the dictionary lists only as a verb.
_COUNTED_VERB_FORMS = frozenset({"души"})


def _not_counted(after: str) -> bool:
    """Whether `колко` before `after` means "to what extent": the next word is a
    punctuation mark or the end, a small helper word, or a verb with no noun or
    adjective reading. A noun, adjective, number or unknown word may be counted
    (`до колко часа`, `до колко души`), so the words stay apart."""
    m = re.match(r"\s*(\w+)", after)
    if not m:
        return True
    word = m.group(1).lower()
    if word in _AFTER_DOKOLKO:
        return True
    readings = morphology.analyse(word)
    return bool(readings) and all(r.tag["pos"] == "V" for r in readings) and word not in _COUNTED_VERB_FORMS


def _together(text: str) -> list[Hit]:
    hits = []
    for m in _TOGETHER.finditer(text):
        wrong = re.sub(" +", " ", m.group(0).lower())
        right = _TOGETHER_BY[wrong]
        before = text[max(0, m.start() - 20) : m.start()]
        after = text[m.end() : m.end() + 30]
        if wrong in ("до сега", "до тогава") and re.search(r"[Оо]т \S+ $", before):
            continue  # `от тогава до сега`
        if wrong == "от части" and re.match(r" (на|от)\b", after):
            continue  # `от части на двигателя`
        if wrong == "на пример" and re.search(r"(дава|даде|дадат|дадем|посочва|посочи|служи|послужи)\w* *$", before):
            continue
        if wrong in ("в ляво", "в дясно", "на ляво", "на дясно") and re.match(r" \w+(та|то|те|ия|ият)\b", after):
            continue
        if wrong == "от колкото" and not re.search(
            r"(?:повече|по-|(?<![\w-])по [а-я]|различн|друг|предпоч|вместо)[^.!?]*$",
            text[max(0, m.start() - 80) : m.start()].lower(),
        ):
            continue  # `интерес от колкото може повече дела`: no comparison, so no `отколкото`
        if wrong in ("до колко", "до колкото") and not _not_counted(after):
            continue  # `до колко часа`: колко counts a noun, so it stays apart
        message = f"Written with a hyphen: „{right}“" if "-" in right else f"Written together: „{right}“"
        hits.append(Hit("written_together", m.start(), m.end(), message, _case(right, m.group(0))))
    return hits


# -- a repeated function word ---------------------------------------------------------

_FUNCTION = set(
    """и а но или да не ще се за на в във с със от до по при към без през че ако като
който която което които това този тази тези е са""".split()
)


def _repeated(text: str) -> list[Hit]:
    hits = []
    for m in re.finditer(B + r"(%s+) +(\1)%s" % (W, E), text, flags=re.I):
        word = m.group(1).lower()
        if text[m.end(2) : m.end(2) + 1] == ")":
            continue  # `букви з) и и)`: a list letter, not a word
        if word in _FUNCTION and word == m.group(2).lower():
            hits.append(Hit("repeated_word", m.start(2) - 1, m.end(2), f"„{word}“ twice", ""))
    return hits


# -- a number range -----------------------------------------------------------------


def _range(text: str) -> list[Hit]:
    hits = []
    for m in re.finditer(r"(?<![\w.,/:+-])(\d{1,4}) ?- ?(\d{1,4})(?![\w.,/:+-]|-)(?= ?(?:[а-яА-Я%€]|$))", text):
        if int(m.group(2)) > int(m.group(1)):
            hits.append(
                Hit(
                    "number_range",
                    m.start(),
                    m.end(),
                    "A range of numbers takes an en dash, no spaces",
                    f"{m.group(1)}–{m.group(2)}",
                )
            )
    return hits


DETECTORS = (
    _article_after_preposition,
    _v_s,
    _superlative,
    _together,
    _joined_adjectives,
    _split_prefixes,
    _repeated,
    _range,
)


def check(text: str) -> list[Hit]:
    """The rules of one text; offsets are into `text` (normalising keeps its length)."""
    normal = normalise(text)
    hits = [hit for detector in DETECTORS for hit in detector(normal)]
    hits = [
        h
        if h.fix is None or normal[h.start : h.end] == text[h.start : h.end]
        else Hit(h.code, h.start, h.end, h.message, None)
        for h in hits
    ]
    return sorted(hits, key=lambda h: (h.start, h.end, h.code))
