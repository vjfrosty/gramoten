"""Bulgarian agreement, by rule, with the morphology of `morphology.py`.

| Code | Rule |
|---|---|
| `double_article` | the article goes on the first word of the phrase only: `Вашите данните` → `данни` |
| `article_after_copula` | after е/са/остава/става a masculine modifier takes the full article: `е най-добрия` → `най-добрият` |
| `count_form` | after a number a masculine noun that is no person takes the count form: `24 месеци` → `месеца` |
| `count_form_person` | after a number a masculine noun that names only people takes the plural: `5 служителя` → `служители` (a closed list of such nouns) |
| `plural_after_dvama` | after двама/трима the plural, not the count form: `трима сина` → `синове` |
| `vie_agreement` | `Вие` with a verb that has no 2nd person plural (може/трябва excepted); `Вие сте казал` → `казали` (an л-participle; adjectives and passive participles keep the addressee's sex: `Вие сте поканен`) |

A rule fires only when every reading of the words involved supports the
error: one innocent reading keeps it quiet. Unknown words never trigger one.
Left out as unreliable: adjective-noun agreement (the lexicon's genders
err), един/една, `по добре`, pronoun-verb agreement, който-
agreement, noun-verb agreement by adjacency.

Norms: ОПР 2012 via ИБЕ („Пълен или кратък член“; „Няколко студенти или
няколко студента“: persons may keep the plural after a numeral), and
kaksepishe.com on the count form.
"""

from __future__ import annotations

import bisect
import re
from functools import lru_cache

from . import morphology
from .lexical import Hit
from .punctuation import normalise
from .tokenize import before

WORD = re.compile(r"[А-Яа-яЍѝ]+(?:-[А-Яа-яЍѝ]+)*")
MODIFIER_POS = {"A", "Pposs", "Pdemo", "Mo"}
#: Only the passive participle works as an attribute; л- and -щ participles take objects.
ATTRIBUTE_PARTICIPLES = ("ptc_pass",)
#: Nouns of one declension used for both sexes.
EPICENE = {
    "глава",
    "съдия",
    "колега",
    "слуга",
    "юноша",
    "будала",
    "пинтия",
    "владика",
    "войвода",
    "паша",
    "ага",
    "кадия",
    "дядо",
    "чичо",
    "вуйчо",
    "батко",
    "тате",
    "сираче",
    "пияница",
    "убиец",
    "левичар",
    "роднина",
}

Token = tuple[str, int, int]


@lru_cache(maxsize=1)
def _gender_extra() -> dict[str, set[str]]:
    """`data/gender_extra.tsv`: nouns whose bgOffice gender edited text contradicts, and the
    ~160 feminine -ия nouns filed under a masculine type. They get the extra gender."""
    out: dict[str, set[str]] = {}
    for line in (morphology.DATA / "gender_extra.tsv").read_text(encoding="utf-8").splitlines():
        if line.strip():
            base, genders_ = line.split("\t")
            out[base] = set(genders_)
    return out


def _genders(reading) -> set[str]:
    found = {reading.tag.get("g")} | _gender_extra().get(reading.base, set())
    if reading.base in EPICENE or reading.base.endswith("ица"):
        found |= {"m", "f"}
    return found


def _readings(word: str):
    return morphology.analyse(re.sub(r"^(?:най|по)-", "", word.lower()))


def _is_modifier(reading) -> bool:
    tag = reading.tag
    return tag["pos"] in MODIFIER_POS or (tag["pos"] == "V" and tag.get("v") in ATTRIBUTE_PARTICIPLES and "n" in tag)


def _all_modifiers(readings) -> bool:
    return bool(readings) and all(_is_modifier(r) for r in readings)


def _all_nouns(readings, drop=()):
    """(every remaining reading is a common noun, those readings): names and vocatives dropped."""
    kept = [r for r in readings if "voc" not in r.tag and r.tag["pos"] != "Np" and not any(f(r) for f in drop)]
    return bool(kept) and all(r.tag["pos"] == "N" for r in kept), kept


def _number(reading) -> str | None:
    n = reading.tag.get("n")
    return "p" if n == "c" else n


def _agree(modifier, noun) -> bool:
    if _number(modifier) != _number(noun):
        return False
    return _number(modifier) == "p" or modifier.tag.get("g") in _genders(noun)


def _case(fix: str, like: str) -> str:
    return fix[:1].upper() + fix[1:] if like[:1].isupper() else fix


def _keep_prefix(word: str, fix: str) -> str:
    m = re.match(r"^((?:най|по)-)", word, flags=re.I)
    return m.group(1) + fix if m else fix


def _sentence_start(text: str, start: int) -> bool:
    return re.search(r"(^|[.!?…:;]\s*|[„\"«(]\s*|\n\s*)$", before(text, start)) is not None


def _name(text: str, word: str, start: int) -> bool:
    """A capital that does not start a sentence: a name or a title word."""
    return word[:1].isupper() and not _sentence_start(text, start) and not re.match(r"(?:Ваш|Вие|Вас|Ви)", word)


def _attributive(text: str, tokens: list[Token], i: int) -> bool:
    """The word at `i` is followed by a noun or a Latin word: it may be attributive (`бизнес решения`)."""
    end = tokens[i][2]
    if text[end : end + 1] in ("/", "-") or re.match(r" [A-Za-z0-9◊]", text[end : end + 2]):
        return True
    if i + 1 >= len(tokens) or text[end : tokens[i + 1][1]] != " ":
        return False
    following = _readings(tokens[i + 1][0])
    return not following or any(
        r.tag["pos"] in ("N", "A") or (_is_modifier(r) and "clitic" not in r.tag) for r in following
    )


# -- the double article -------------------------------------------------------


#: Base forms the morphology reads as having the full article, because the dictionary
#: gives the word no other singular: `кръстопът` (its article form is `кръстопътят`).
#: Of all lemmas only this one and `светът` have that shape, and `светът` is articled.
UNARTICLED_BASES = frozenset({"кръстопът"})


def _double_article(text: str, tokens: list[Token]) -> list[Hit]:
    hits = []
    for (w1, s1, e1), (w2, s2, e2) in zip(tokens, tokens[1:], strict=False):
        if text[e1:s2] != " " or w2[0].isupper() or _name(text, w1, s1):
            continue
        if w1.lower() in ("противното", "другото"):
            continue  # `до доказване на противното`, `наред с другото`: nominalised
        if w2.lower() in UNARTICLED_BASES:
            continue  # `международния кръстопът`: a base form the dictionary tags as articled
        first = _readings(w1)
        is_noun, second = _all_nouns(_readings(w2))
        if not (_all_modifiers(first) and is_noun):
            continue
        if not all(r.tag.get("d") in ("h", "f", "d") for r in (*first, *second)):
            continue
        if not any(_agree(a, b) for a in first for b in second):
            continue  # two phrases, not one: `на първата времето`
        fixes = set()
        for b in second:
            fixes.update(
                morphology.inflect(b.lemma, n=b.tag["n"], d="i")
                if b.tag["n"] != "s" or b.tag.get("g") != "m"
                else morphology.inflect(b.lemma, n="s", d="i")
            )
        hits.append(
            Hit(
                "double_article",
                s2,
                e2,
                "Only the first word of the phrase takes the article",
                fixes.pop() if len(fixes) == 1 else None,
            )
        )
    return hits


# -- the full article after a copula ------------------------------------------------

COPULA = {"е", "са", "беше", "бяха", "бъде", "бъдат", "остава", "става", "стана", "изглежда"}
TIME_WORDS = set(
    """понеделник вторник сряда четвъртък петък събота неделя ден месец час сезон уикенд
януари февруари март април май юни юли август септември октомври ноември декември""".split()
)


def _article_after_copula(text: str, tokens: list[Token]) -> list[Hit]:
    hits = []
    for i in range(len(tokens) - 1):
        (w1, s1, e1), (w2, s2, e2) = tokens[i], tokens[i + 1]
        if w1.lower() not in COPULA or text[e1:s2] != " " or _name(text, w2, s2):
            continue
        if (
            i
            and text[tokens[i - 1][2] : s1] == " "
            and any(r.tag.get("v") in ("ptc_aor", "ptc_impf") for r in _readings(tokens[i - 1][0]))
        ):
            continue  # `Размътили са целия поток`: an auxiliary, the phrase is an object
        if i + 2 < len(tokens) and tokens[i + 2][0].lower() in TIME_WORDS:
            continue  # `е идния четвъртък`: when, not what
        readings = _readings(w2)
        if not readings or not all(
            r.tag.get("d") == "h" and r.tag.get("g") == "m" and r.tag.get("n") == "s" and _is_modifier(r)
            for r in readings
        ):
            continue
        fixes = set()
        for r in readings:
            fixes.update(
                morphology.inflect(r.lemma, g="m", n="s", d="f", **({"v": r.tag["v"]} if "v" in r.tag else {}))
            )
        hits.append(
            Hit(
                "article_after_copula",
                s2,
                e2,
                "After „е“ the masculine word takes the full article (-ят/-ът)",
                _keep_prefix(w2, fixes.pop()) if len(fixes) == 1 else None,
            )
        )
    return hits


# -- the count form after a number ---------------------------------------------------

NUMBER_WORDS = set(
    """два три четири пет шест седем осем девет десет единадесет дванадесет тринадесет четиринадесет
петнадесет шестнадесет седемнадесет осемнадесет деветнадесет двадесет тридесет четиридесет петдесет
шестдесет седемдесет осемдесет деветдесет сто двеста триста няколко колко толкова""".split()
)
PERSON_SUFFIX = (
    "тел",
    "ник",
    "ач",
    "яч",
    "ист",
    "ант",
    "ент",
    "лог",
    "чия",
    "джия",
    "ьор",
    "ар",
    "яр",
    "ер",
    "ор",
    "ик",
    "ак",
    "як",
    "ок",
    "ец",
    "ин",
    "ан",
    "ян",
    "ич",
    "ит",
    "ат",
    "ед",
    "ен",
    "ах",
    "ех",
)
PERSONS = set(
    """кмет атлет член депутат министър гост пилот герой съсед грък чех фен монах цар крал принц граф бог
мъж син брат внук роб войн шеф експерт лидер човек юнак момък старец пророк апостол дякон поп свещеник лекар
доктор адвокат съдия прокурор инженер техник офицер генерал полковник капитан сержант редник воин рицар""".split()
)
NOT_PERSONS = {"месец", "танец", "конец", "палец", "образец", "резервоар", "долар", "сантиметър", "километър"}


def _person(reading) -> bool:
    """May this masculine noun be a person? Then the plural is right after a numeral."""
    base = reading.base
    if base in PERSONS:
        return True
    if base in NOT_PERSONS:
        return False
    if any("voc=1" in tag for tag in morphology.forms(reading.lemma)):
        return True
    return base.endswith(PERSON_SUFFIX)


#: The count form by the plural written, where the dictionary joins two nouns in one
#: entry: `път` (road) has the plural `пътища` and the count form `пътя`; its `пъти`
#: is the count form of `път` (time): `три пъти`. So `12 063 третокласни пътя`.
COUNT_OF_PLURAL = {"пътища": ["пътя"]}


def _count_after(text: str, end: int, following: list[Token]) -> list[Hit]:
    previous = end
    for word, start, stop in following:
        if text[previous:start] not in (" ", " ") or word[0].isupper():
            return []
        readings = _readings(word)
        if _all_modifiers(readings) and all(r.tag.get("n") == "p" and r.tag.get("d") == "i" for r in readings):
            previous = stop
            continue  # `три нови телефони`: past the adjectives
        is_noun, nouns = _all_nouns(readings)
        if not is_noun or not all(
            r.tag.get("g") == "m" and r.tag.get("n") == "p" and r.tag.get("d") == "i" for r in nouns
        ):
            return []
        if any(_person(r) for r in nouns):
            return []
        counts = COUNT_OF_PLURAL.get(word.lower()) or sorted(
            {f for r in nouns for f in morphology.inflect(r.lemma, n="c")}
        )
        if not counts or word.lower() in counts:
            return []
        return [
            Hit(
                "count_form",
                start,
                stop,
                "After a number a masculine noun takes the count form",
                counts[0] if len(counts) == 1 else None,
            )
        ]
    return []


def _count_form(text: str, tokens: list[Token]) -> list[Hit]:
    hits = []
    starts = [t[1] for t in tokens]
    for m in re.finditer(r"(?<![\w.,/-])(\d+)(?=[  ][А-Яа-я])", text):
        number = m.group(1)
        if number.endswith("1") and not number.endswith("11"):
            continue  # `21 месец`: one takes the singular
        previous = re.search(r"(\S+)\s+$", before(text, m.start()))
        if previous and (
            previous.group(1).endswith((".", "№", "/"))
            or re.fullmatch(r"[A-Za-z][\w-]*", previous.group(1))
            or (_readings(previous.group(1)) and all(r.tag["pos"] in ("N", "Nm") for r in _readings(previous.group(1))))
        ):
            continue  # `член 68 органите`, `NUTS 2`: a reference, not a count
        if re.search(r"\d\s*(?:,|и|или)\s*$", before(text, m.start())):
            continue  # `параграфи 1, 2 и 3`: a list of references
        following = bisect.bisect_right(starts, m.end())  # the tokens after the number
        hits += _count_after(text, m.end(), tokens[following : following + 3])
    for i, (word, _start, stop) in enumerate(tokens):
        if word.lower() in NUMBER_WORDS:
            hits += _count_after(text, stop, tokens[i + 1 : i + 4])
    return hits


# -- двама/трима + the plural ---------------------------------------------------------

PERSONAL_NUMERALS = {"двама", "трима", "четирима", "петима", "шестима", "седмина", "осмина", "деветима", "десетима"}


def _plural_after_dvama(text: str, tokens: list[Token]) -> list[Hit]:
    hits = []
    for i in range(len(tokens) - 1):
        (w1, _s1, e1), (w2, s2, e2) = tokens[i], tokens[i + 1]
        numeral = w1.lower()
        if numeral not in PERSONAL_NUMERALS or text[e1:s2] != " " or w2[0].isupper():
            continue
        is_noun, nouns = _all_nouns(_readings(w2), drop=(lambda r: r.tag["pos"] == "V" and r.tag.get("n") == "s",))
        if not is_noun or _attributive(text, tokens, i + 1) or w2.lower() == "човека":
            continue
        if all(
            r.tag.get("g") == "m" and (r.tag.get("n") == "c" or (r.tag.get("n") == "s" and r.tag.get("d") == "h"))
            for r in nouns
        ) and any(r.tag.get("n") == "c" for r in nouns):
            plurals = sorted({f for r in nouns for f in morphology.inflect(r.lemma, n="p", d="i")})
            hits.append(
                Hit(
                    "plural_after_dvama",
                    s2,
                    e2,
                    f"After „{numeral}“ use the plural, not the count form",
                    plurals[0] if len(plurals) == 1 else None,
                )
            )
    return hits


# -- a number + a noun naming people -----------------------------------------------------

#: Masculine nouns that name only people, so after a number they take the plural:
#: `5 служители`, not `5 служителя` (ОПР 2012; ИБЕ „Няколко студенти или няколко
#: студента“). A closed list: nouns that may also name a firm or a thing stay out
#: (`оператор`, `доставчик`, `производител`, `член`, `спътник`, `приемник`; `кандидат`
#: for a vaccine), and so does
#: `човек`, whose `пет човека` the norm allows.
PERSON_NOUNS = frozenset(
    """служител ученик студент учител преподавател лекар клиент потребител ползвател абонат
работник специалист експерт консултант гост пасажер депутат кмет министър войник
полицай пациент жител посетител зрител читател слушател турист спортист играч състезател
треньор сътрудник колега приятел съученик съсед гражданин стажант докторант първокласник
абсолвент възпитаник победител финалист доброволец дарител инвеститор акционер собственик
наемател купувач продавач търговец шофьор пилот моряк офицер генерал журналист адвокат
прокурор съдия инженер програмист мениджър директор чиновник представител наблюдател делегат
избирател привърженик поддръжник пенсионер футболист баскетболист волейболист тенисист
боксьор атлет шампион медалист лауреат автор писател художник музикант артист актьор певец
танцьор фотограф хирург фармацевт стоматолог медик санитар болногледач брокер счетоводител
юрист икономист библиотекар готвач сервитьор барман фермер строител монтьор механик шивач
фризьор пощальон куриер охранител пазач затворник бежанец мигрант емигрант имигрант арестант
извършител крадец убиец свидетел заложник младеж мъж син брат внук братовчед племенник
съпруг годеник""".split()
)
#: The numerals whose noun this rule may change: a digit reads as `двама`/`петима`, but
#: `два`/`три`/`четири` before a person need the numeral changed too, so they stay out.
PERSON_COUNTERS = NUMBER_WORDS - {"два", "три", "четири"}


def _person_count(text: str, end: int, following: list[Token]) -> list[Hit]:
    previous = end
    for word, start, stop in following:
        if text[previous:start] not in (" ", " ") or word[0].isupper():
            return []
        readings = _readings(word)
        if _all_modifiers(readings) and all(r.tag.get("n") == "p" and r.tag.get("d") == "i" for r in readings):
            previous = stop
            continue  # `5 нови служителя`: past the adjectives
        is_noun, nouns = _all_nouns(readings)
        if not is_noun or not all(
            r.base in PERSON_NOUNS
            and r.tag.get("g") == "m"
            and (r.tag.get("n") == "c" or (r.tag.get("n") == "s" and r.tag.get("d") == "h"))
            for r in nouns
        ):
            return []
        plurals = sorted({f for r in nouns for f in morphology.inflect(r.lemma, n="p", d="i")})
        if not plurals:
            return []
        return [
            Hit(
                "count_form_person",
                start,
                stop,
                "After a number a noun naming people takes the plural",
                plurals[0] if len(plurals) == 1 else None,
            )
        ]
    return []


def _count_form_person(text: str, tokens: list[Token]) -> list[Hit]:
    hits = []
    starts = [t[1] for t in tokens]
    for m in re.finditer(r"(?<![\w.,/:-])(\d+)(?=[  ][а-я])", text):
        number = m.group(1)
        if number.endswith("1") and not number.endswith("11"):
            continue  # `21 служител`: one takes the singular
        if re.search(r"(?:[.№/:-]|[A-Za-z][\w-]*|\d\s*(?:,|и|или))\s*$", before(text, m.start())):
            continue  # `чл. 5`, `NUTS 2`, `1, 2 и 3`: a reference or a list
        if re.fullmatch(r"(?:19|20)\d\d", number) and re.search(
            r"(?<![\w-])(?:от|през|в|до|след|преди)\s+$", before(text, m.start()).lower()
        ):
            continue  # `от 2006 депутата издигат…`: a year
        previous = re.search(r"(\S+)\s+$", before(text, m.start()))
        previous_readings = _readings(previous.group(1)) if previous else []
        if previous_readings and all(r.tag["pos"] in ("N", "Nm") for r in previous_readings):
            continue  # `стая 5 служителя`: a reference, not a count
        following = bisect.bisect_right(starts, m.end())
        hits += _person_count(text, m.end(), tokens[following : following + 3])
    for i, (word, _start, stop) in enumerate(tokens):
        if word.lower() in PERSON_COUNTERS:
            hits += _person_count(text, stop, tokens[i + 1 : i + 4])
    return hits


# -- Вие + verb ------------------------------------------------------------------------

IMPERSONAL = {
    "трябва",
    "може",
    "има",
    "няма",
    "струва",
    "следва",
    "предстои",
    "важи",
    "личи",
    "стига",
    "ще",
    "би",
    "бих",
    "бихме",
    "бихте",
    "биха",
    "е",
}


def _vie_agreement(text: str, tokens: list[Token]) -> list[Hit]:
    hits = []
    for i in range(len(tokens) - 1):
        (w1, s1, e1), (w2, s2, e2) = tokens[i], tokens[i + 1]
        if w1.lower() != "вие" or text[e1:s2] != " ":
            continue
        readings = _readings(w2)
        if (
            w2.lower() in IMPERSONAL
            or not readings
            or not all(
                r.tag["pos"] == "V" and r.tag.get("v") in ("pres", "aor", "impf") and "p" in r.tag for r in readings
            )
        ):
            continue
        if re.search(r"(?:\bи|,)\s+$", before(text, s1)):
            continue  # `трима другари и вие`: a coordinated subject
        if any(r.tag["p"] == "2" and r.tag["n"] == "p" for r in readings):
            continue
        fix = None
        for tense in ("pres", "aor", "impf"):
            fixes = {
                f for r in readings if r.tag["v"] == tense for f in morphology.inflect(r.lemma, v=tense, p="2", n="p")
            }
            if fixes:
                fix = _case(fixes.pop(), w2) if len(fixes) == 1 else None
                break
        hits.append(Hit("vie_agreement", s2, e2, "The verb agrees with „Вие“: 2nd person plural", fix))
    return hits


#: The auxiliary after `Вие` and the short words that may stand between it and the participle.
VIE_AUXILIARIES = {"сте", "бяхте", "бихте"}
CLITICS = {"се", "си", "ми", "ти", "му", "ѝ", "й", "ни", "ви", "им", "го", "я", "ги"}


def _vie_participle(text: str, tokens: list[Token]) -> list[Hit]:
    """`Вие сте казал` → `казали`: with `Вие` the л-participle is plural, also in polite address.
    Adjectives and passive participles keep the addressee's sex (`Вие сте поканен`, `доволна`)."""
    hits = []
    for i in range(len(tokens) - 2):
        (w1, s1, e1), (aux, sa, ea) = tokens[i], tokens[i + 1]
        if w1.lower() != "вие" or text[e1:sa] != " ":
            continue
        if re.search(r"(?:\bи|,)\s+$", before(text, s1)):
            continue  # `Иван и вие сте казал`: a coordinated subject
        j = i + 1
        if aux.lower() == "не" and j + 1 < len(tokens) and text[ea : tokens[j + 1][1]] == " ":
            j += 1
        if tokens[j][0].lower() not in VIE_AUXILIARIES:
            continue
        j += 1
        while j < len(tokens) and tokens[j][0].lower() in CLITICS and text[tokens[j - 1][2] : tokens[j][1]] == " ":
            j += 1
        if j >= len(tokens) or text[tokens[j - 1][2] : tokens[j][1]] != " ":
            continue
        word, start, stop = tokens[j]
        readings = _readings(word)
        if not readings or not all(
            r.tag["pos"] == "V" and r.tag.get("v") in ("ptc_aor", "ptc_impf") and r.tag.get("n") == "s"
            for r in readings
        ):
            continue
        plurals = sorted({f for r in readings for f in morphology.inflect(r.lemma, v=r.tag["v"], n="p", d="i")})
        hits.append(
            Hit(
                "vie_agreement",
                start,
                stop,
                "With „Вие“ the participle is plural",
                _case(plurals[0], word) if len(plurals) == 1 else None,
            )
        )
    return hits


DETECTORS = (
    _double_article,
    _article_after_copula,
    _count_form,
    _count_form_person,
    _plural_after_dvama,
    _vie_agreement,
    _vie_participle,
)


def check(text: str) -> list[Hit]:
    """The agreement rules of one text; offsets are into `text`."""
    normal = normalise(text)
    tokens = [(m.group(0), m.start(), m.end()) for m in WORD.finditer(normal)]
    hits = {hit for detector in DETECTORS for hit in detector(normal, tokens) if "◊" not in normal[hit.start : hit.end]}
    hits = {
        h
        if h.fix is None or normal[h.start : h.end] == text[h.start : h.end]
        else Hit(h.code, h.start, h.end, h.message, None)
        for h in hits
    }
    return sorted(hits, key=lambda h: (h.start, h.end, h.code))
