"""Build the morphology from the MPL bg_BG Hunspell dictionary and our own word classes.

    uv run --no-project --python 3.13 --with marisa-trie==1.4.1 python -I tools/morphology/hunspell_morph.py

Inputs:
* `tools/bg_BG/bg_BG.dic`, `bg_BG.aff`: bgOffice's spell-check package, under
  GPL/LGPL/MPL; gramoten takes it under MPL-1.1 (`tools/bg_BG/SOURCE.md`).
* `closed_words.tsv` (beside this script): pronouns, numerals, month names,
  prepositions, conjunctions and particles, written for gramoten.

The Hunspell file says only which endings a word takes, not what they mean. The
tags are worked out here from how a word's forms relate to each other, the same
way for every affix class, from Bulgarian grammar:
* a verb's entry is its 1st person singular present; `-ш` marks the 2nd person,
  which without `ш` is the 3rd; a stem with `-ше` and `-х` is the imperfect, a stem
  with `-х` and `-хме` the aorist; `-л`, `-ла`, `-лия`... a participle, and so on;
* a noun's gender comes from its article (`-ът`/`-ят` masculine, `-та` feminine,
  `-то` neuter), its plural from the form that takes `-те`/`-та`;
* an adjective is a word with `-ият`, `-ата`, `-ото` and `-ите` forms.
No tag is copied from another lexicon. Words listed without endings (irregular
forms, adverbs) get no reading unless `closed_words.tsv` has them.

Output (`src/gramoten/data/`):
* `bg_morph.marisa`: a marisa Trie of the keys `form \\x01 lemma \\x02 tag` (lemma and
  tag index in hex): a form's readings are one prefix search.
* `bg_morph.json`: {"tags": [tag...]}.
* `bg_morph_lemmas.marisa`: a marisa Trie of the keys `index  base  pos  stem`
  (index in hex), one per lemma. `stem` is the start all the lemma's forms share, so
  its forms are one prefix search too; where they share less than 2 letters (човек:
  хора) it is `` and the forms joined by ``.
"""

from __future__ import annotations

import collections
import json
import os
import re
import sys
import time
from pathlib import Path

import marisa_trie

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DIC = ROOT / "tools" / "bg_BG" / "bg_BG.dic"
AFF = ROOT / "tools" / "bg_BG" / "bg_BG.aff"
CLOSED = HERE / "closed_words.tsv"
OUT = ROOT / "src" / "gramoten" / "data"

#: Nouns in -а/-я/-о that are masculine (the article alone would say feminine or neuter).
MASCULINE_IN_VOWEL = {
    "баща",
    "слуга",
    "владика",
    "войвода",
    "съдия",
    "паша",
    "ага",
    "калфа",
    "чорбаджия",
    "дядо",
    "чичо",
    "вуйчо",
    "татко",
    "тате",
    "кумчо",
    "свако",
    "батко",
    "бате",
}
#: Adjective-like words that are ordinal numerals (pos Mo).
ORDINALS = {
    "пръв",
    "първи",
    "втори",
    "трети",
    "четвърти",
    "пети",
    "шести",
    "седми",
    "осми",
    "девети",
    "десети",
    "единадесети",
    "единайсти",
    "дванадесети",
    "дванайсти",
    "тринадесети",
    "тринайсти",
    "четиринадесети",
    "четиринайсти",
    "петнадесети",
    "петнайсти",
    "шестнадесети",
    "шестнайсти",
    "седемнадесети",
    "седемнайсти",
    "осемнадесети",
    "осемнайсти",
    "деветнадесети",
    "деветнайсти",
    "двадесети",
    "двайсти",
    "тридесети",
    "трийсти",
    "четиридесети",
    "четирийсти",
    "петдесети",
    "шестдесети",
    "седемдесети",
    "осемдесети",
    "деветдесети",
    "стотен",
    "хиляден",
    "милионен",
}


# -- Hunspell ------------------------------------------------------------------------------


def load_aff() -> dict[str, list[tuple[str, str, re.Pattern]]]:
    classes: dict[str, list] = {}
    for line in AFF.read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 4 and p[0] == "SFX":
            if len(p) == 4 and p[2] in "YN":
                classes[p[1]] = []
            else:
                strip = "" if p[2] == "0" else p[2]
                add = "" if p[3] == "0" else p[3]
                cond = p[4] if len(p) > 4 else "."
                classes[p[1]].append((strip, add, re.compile("(?:" + cond + ")$")))
    return classes


def load_dic() -> list[tuple[str, str]]:
    out = []
    for line in DIC.read_text(encoding="utf-8").split("\n")[1:]:
        line = line.strip()
        if line:
            word, _, flags = line.partition("/")
            out.append((word, flags))
    return out


def expand(word: str, flags: str, classes) -> set[str]:
    forms = {word}
    for flag in flags:
        for strip, add, cond in classes[flag]:
            if cond.search(word) and word.endswith(strip):
                forms.add(word[: len(word) - len(strip)] + add)
    return forms


# -- the labeller ----------------------------------------------------------------------------


def _tag(pos: str, **features: str) -> str:
    return "|".join([pos] + [f"{k}={v}" for k, v in sorted(features.items())])


def label_adjective(base: str, forms: set[str], pos: str = "A") -> list[tuple[str, str]] | None:
    full = [f for f in forms if f.endswith("ият")]
    fem = [f for f in forms if f.endswith("ата")]
    neu = [f for f in forms if f.endswith(("ото", "ето"))]  # новото; soft: висшето
    plu = [f for f in forms if f.endswith("ите")]
    if not (full and fem and neu and plu):
        return None
    out = [(base, _tag(pos, d="i", g="m", n="s"))]
    for f in full:
        out += [(f, _tag(pos, d="f", g="m", n="s")), (f[:-1], _tag(pos, d="h", g="m", n="s"))]
    for f in fem:
        out += [(f, _tag(pos, d="d", g="f", n="s")), (f[:-2], _tag(pos, d="i", g="f", n="s"))]
    for f in neu:
        out += [(f, _tag(pos, d="d", g="n", n="s")), (f[:-2], _tag(pos, d="i", g="n", n="s"))]
    for f in plu:
        out += [(f, _tag(pos, d="d", n="p")), (f[:-2], _tag(pos, d="i", n="p"))]
    return [(f, t) for f, t in out if f in forms]


def label_noun(base: str, forms: set[str]) -> list[tuple[str, str]] | None:
    masc_full = [f for f in forms if f != base and (f.endswith("ът") or f.endswith("ят"))]
    personal_o = base.endswith("о") and any(f.endswith("овци") for f in forms)  # прадядо: прадядовци
    if base in MASCULINE_IN_VOWEL or masc_full or personal_o or base.endswith(("джия", "чия", "ьо")):
        gender = "m"
    elif base[-1:] in "ая":
        gender = "f"
    elif base[-1:] in "оеиую":  # теме: темето; its plural темета is not a feminine article
        gender = "n"
    elif base + "та" in forms:  # младост: младостта
        gender = "f"
    else:
        return None
    out = [(base, _tag("N", d="i", g=gender, n="s"))]
    plural = []
    if gender == "n":
        out += [(base + "то", _tag("N", d="d", g="n", n="s"))]
        # the plural takes -та (места), or -те when the noun was an adjective (прилагателни)
        plural = [(f, f + a) for f in forms if f not in (base, base + "то") for a in ("та", "те") if f + a in forms]
        for p, definite in plural:
            out += [(p, _tag("N", d="i", g="n", n="p")), (definite, _tag("N", d="d", g="n", n="p"))]
    else:
        plural = [f for f in forms if f + "те" in forms]
        for p in plural:
            out += [(p, _tag("N", d="i", g=gender, n="p")), (p + "те", _tag("N", d="d", g=gender, n="p"))]
        if gender == "f" or (gender == "m" and base[-1:] in "ая"):
            out += [(base + "та", _tag("N", d="d", g=gender, n="s"))]
        if gender == "m" and base[-1:] in "оеи":  # дядо: дядото
            out += [(base + "то", _tag("N", d="d", g="m", n="s"))]
        personal = any(f.endswith("ю") for f in forms if f != base)
        for f in masc_full:
            short = f[:-2] + ("а" if f.endswith("ът") else "я")
            out += [(f, _tag("N", d="f", g="m", n="s")), (short, _tag("N", d="h", g="m", n="s"))]
            if plural and not personal:
                out += [(short, _tag("N", d="i", g="m", n="c"))]
    known = {f for f, _ in out}
    # What is left over in -е/-о/-ю is a vocative (будителю, ковачо, жено, приятелю).
    for f in forms - known:
        if f[-1:] in "еою" and len(f) >= len(base) - 1:
            out.append((f, _tag("N", d="i", g=gender, voc="1")))
    return [(f, t) for f, t in out if f in forms]


def _declined(stem_forms: dict[str, str], forms: set[str], v: str) -> list[tuple[str, str]]:
    """A participle's nine forms from its masculine (`m`) and other (`o`) stems."""
    m, o = stem_forms["m"], stem_forms["o"]
    pairs = [
        (m, dict(d="i", g="m", n="s")),
        (o + "ия", dict(d="h", g="m", n="s")),
        (o + "ият", dict(d="f", g="m", n="s")),
        (o + "а", dict(d="i", g="f", n="s")),
        (o + "ата", dict(d="d", g="f", n="s")),
        (o + "о", dict(d="i", g="n", n="s")),
        (o + "ото", dict(d="d", g="n", n="s")),
        (o + "и", dict(d="i", n="p")),
        (o + "ите", dict(d="d", n="p")),
    ]
    return [(f, _tag("V", v=v, **feat)) for f, feat in pairs if f in forms]


def label_verb(base: str, forms: set[str]) -> list[tuple[str, str]] | None:
    if not any(f.endswith("хме") for f in forms):
        return None
    out = [(base, _tag("V", n="s", p="1", v="pres"))]
    # present tense
    for s2 in [f for f in forms if f.endswith("ш") and f[:-1] in forms and not f.endswith("еше")]:
        s3 = s2[:-1]
        out += [(s2, _tag("V", n="s", p="2", v="pres")), (s3, _tag("V", n="s", p="3", v="pres"))]
        for p1 in (s3 + "м", s3 + "ме"):
            if p1 in forms and p1 != base:
                out.append((p1, _tag("V", n="p", p="1", v="pres")))
        out.append((s3 + "те", _tag("V", n="p", p="2", v="pres")))
        for p3 in (base + "т", s3 + "т"):
            if p3 in forms:
                out.append((p3, _tag("V", n="p", p="3", v="pres")))
    # imperfect: X+ше, and X+х -- or, where an е before ше is я elsewhere (четеше:
    # четях, гореше: горях), Xя+х. `impf` holds the stems the -х forms are built on.
    impf = set()
    for f in forms:
        if f.endswith("ше"):
            x = f[:-2]
            stem = x if x + "х" in forms else (x[:-1] + "я" if x.endswith("е") and x[:-1] + "ях" in forms else None)
            if stem is None:
                continue
            impf.add(stem)
            out += [(f, _tag("V", n="s", p="2", v="impf")), (f, _tag("V", n="s", p="3", v="impf"))]
            out += [
                (stem + e, _tag("V", n=n, p=p, v="impf"))
                for e, n, p in (("х", "s", "1"), ("хме", "p", "1"), ("хте", "p", "2"), ("ха", "p", "3"))
            ]
    # aorist: a stem Y with Y+х and Y+хме whose 2nd/3rd person (Y, or четох: чете) is a form,
    # and which is not the imperfect's -- except in the 3rd conjugation (питам: питах is both),
    # or where the imperfect's я stem is the only one (горя: горях is both).
    candidates = {}
    for f in forms:
        if f.endswith("х") and f[:-1] + "хме" in forms:
            y = f[:-1]
            third = y if y in forms else None
            if third is None and y.endswith("о"):  # четох: чете; пекох: пече; могох: може
                for e in (y[:-1] + "е", y[:-2] + {"к": "ч", "г": "ж", "х": "ш"}.get(y[-2:-1], y[-2:-1]) + "е"):
                    if e in forms:
                        third = e
                        break
            if third is not None:
                candidates[y] = third
    others = [y for y in candidates if y not in impf]
    aor = set()
    for y, third in candidates.items():
        if y in impf and not (base.endswith("м") or (y.endswith("я") and y + "ше" not in forms and not others)):
            continue
        aor.add(y)
        out += [
            (y + "х", _tag("V", n="s", p="1", v="aor")),
            (third, _tag("V", n="s", p="2", v="aor")),
            (third, _tag("V", n="s", p="3", v="aor")),
            (y + "хме", _tag("V", n="p", p="1", v="aor")),
            (y + "хте", _tag("V", n="p", p="2", v="aor")),
            (y + "ха", _tag("V", n="p", p="3", v="aor")),
        ]
    # participles in -л: the masculine ends in л, the rest add -а/-о/-и/-ия... to a stem
    # that is the same (писал: писала) or drops a ъ (пекъл: пекла) or turns я into е (видял: видели).
    for m in [f for f in forms if f.endswith("л")]:
        stems = {m}
        if m.endswith("ъл"):
            stems.add(m[:-2] + "л")
        if m.endswith("ял"):
            stems.add(m[:-2] + "ел")
        for o in stems:
            if o + "а" not in forms and o + "и" not in forms:
                continue
            s = m[:-1]
            if s in impf:
                out += _declined({"m": m, "o": o}, forms, "ptc_impf")
            if s in aor or s not in impf:  # питал, горял: both participles
                out += _declined({"m": m, "o": o}, forms, "ptc_aor")
    # present active participle (-щ)
    for m in [f for f in forms if f.endswith("щ")]:
        out += _declined({"m": m, "o": m}, forms, "ptc_pres")
    # passive participle in -н/-т; after я the plural has е (родян, родяна: родени; повят: повети)
    for m in [f for f in forms if f[-1:] in "нт" and f + "а" in forms]:
        alt = m[:-2] + "е" + m[-1] if m[-2:-1] == "я" else m
        if m + "и" in forms or alt + "и" in forms:
            out += _declined({"m": m, "o": m}, forms, "ptc_pass")
            if alt != m:
                out += _declined({"m": m, "o": alt}, forms, "ptc_pass")
    out += [(f, _tag("V", v="ger")) for f in forms if f.endswith("йки")]  # gerund
    # imperative: the plural in -йте (питайте: питай) or -ете (четете: чети)
    for f in forms:
        if f.endswith("йте"):
            out += [(f, _tag("V", n="p", v="imp")), (f[:-2], _tag("V", n="s", v="imp"))]
        elif f.endswith("ете") and f[:-3] + "и" in forms:
            out += [(f, _tag("V", n="p", v="imp")), (f[:-3] + "и", _tag("V", n="s", v="imp"))]
    return [(f, t) for f, t in out if f in forms]


def label(base: str, forms: set[str]) -> tuple[str, list[tuple[str, str]]] | None:
    if base[:1].isupper():
        return "Np", [(f, "Np") for f in forms]
    if len(forms) == 1:
        return None
    verb = label_verb(base, forms)
    if verb:
        return "V", verb
    adjective = label_adjective(base, forms, "Mo" if base in ORDINALS else "A")
    if adjective:
        return ("Mo" if base in ORDINALS else "A"), adjective
    noun = label_noun(base, forms)
    if noun:
        return "N", noun
    return None


# -- forms listed without endings -------------------------------------------------------------

OPEN_POS = ("N", "A", "V")


def closed_forms() -> set[str]:
    return {
        line.split("\t")[0]
        for line in CLOSED.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def flagless_groups(entries: list[tuple[str, str]], skip: set[str]) -> list[list[str]]:
    """Runs of lowercase entries without flags, in dictionary order, that share their
    first word's stem: all of it but the last 4 letters, and at least 4 letters."""
    groups: list[list[str]] = []
    current: list[str] = []
    need = 0
    for word, flags in entries:
        if flags:
            continue  # a flagged entry in between does not end a run
        if word[:1].isupper() or word in skip or "-" in word:
            continue
        if current:
            first = current[0]
            common = len(
                next((first[:i] for i in range(min(len(first), len(word)), 0, -1) if word.startswith(first[:i])), "")
            )
            if common >= need:
                current.append(word)
                continue
            if len(current) > 1:
                groups.append(current)
        current = [word]
        need = max(min(4, len(word)), len(word) - 4)
    if len(current) > 1:
        groups.append(current)
    return groups


def suffix_model(readings, lemmas) -> dict[str, collections.Counter]:
    """For each word ending of 2-6 letters, how often the labelled words with it carry each
    set of tags (a form's tags within one lemma)."""
    model: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for form, rs in readings.items():
        by_lemma = collections.defaultdict(set)
        for lemma, tag in rs:
            if lemmas[lemma][1] in OPEN_POS:
                by_lemma[lemma].add(tag)
        for tags in by_lemma.values():
            key = frozenset(tags)
            for k in range(2, 7):
                if len(form) > k + 1:
                    model[form[-k:]][key] += 1
    return model


def predict(form: str, model, pos: str | None = None) -> frozenset[str] | None:
    """The tag set the longest well-attested ending agrees on (>= 20 words, >= 85%)."""
    for k in range(min(6, len(form) - 2), 1, -1):
        counts = model.get(form[-k:])
        if not counts:
            continue
        if pos:
            counts = collections.Counter({t: c for t, c in counts.items() if next(iter(t)).split("|")[0] == pos})
        total = sum(counts.values())
        if total < 20:
            continue
        tags, count = counts.most_common(1)[0]
        if count / total >= 0.85:
            return tags
        # No one set of tags dominates (държи: present, imperative, sometimes aorist):
        # keep the tags that at least 85% of these words carry.
        each = collections.Counter(t for tag_set, c in counts.items() for t in tag_set for _ in range(c))
        common = frozenset(t for t, c in each.items() if c / total >= 0.85)
        return common or None
    return None


def tag_by_analogy(group: list[str], model) -> tuple[str, str, list[tuple[str, str]]] | None:
    # A group the structural rules explain on their own, with its shortest form as the
    # base (песен, песента, песни, песните; висш, висша, висшия...), needs no analogy.
    forms = set(group)
    shortest = min(group, key=len)
    for pos, labelled in (
        ("V", label_verb("", forms)),
        ("A", label_adjective(shortest, forms)),
        ("N", label_noun(shortest, forms)),
    ):
        if labelled and len({f for f, _ in labelled}) >= 0.8 * len(forms):
            return (
                pos,
                shortest if pos != "V" else next((f for f, t in labelled if t == "V|n=s|p=1|v=pres"), shortest),
                labelled,
            )
    votes = collections.Counter()
    for form in group:
        tags = predict(form, model)
        if tags:
            votes[next(iter(tags)).split("|")[0]] += 1
    if not votes:
        return None
    pos, count = votes.most_common(1)[0]
    if count < max(2, len(group) // 2):
        return None
    # The structural rules first, on the group's own forms (държиш: държи is the 3rd
    # person); analogy only for the forms they leave untagged.
    forms = set(group)
    structural = []
    if pos == "V":
        structural = label_verb("", forms) or []
    elif pos == "A":
        base = next((f for f in group if f + "ия" in forms or f + "а" in forms), None)
        structural = (label_adjective(base, forms) or []) if base else []
    covered = {f for f, _ in structural}
    pairs = list(structural)
    for form in group:
        if form in covered:
            continue
        tags = predict(form, model, pos)
        if tags:
            pairs += [(form, t) for t in tags]
    if not pairs:
        return None
    wanted = {"V": "V|n=s|p=1|v=pres", "N": None, "A": "A|d=i|g=m|n=s"}[pos]
    base = (
        next((f for f, t in pairs if t == wanted), None)
        or next((f for f, t in pairs if pos == "N" and "d=i" in t and "n=s" in t), None)
        or min(group, key=len)
    )
    return pos, base, pairs


# -- build -----------------------------------------------------------------------------------


def build() -> dict:
    started = time.perf_counter()
    classes = load_aff()
    lemmas: list[list[str]] = []
    readings: dict[str, set[tuple[int, str]]] = collections.defaultdict(set)
    stats = collections.Counter()
    untagged = collections.Counter()

    for word, flags in load_dic():
        forms = expand(word, flags, classes)
        found = label(word, forms)
        if found is None:
            stats["no reading" if not flags else "unlabelled"] += 1
            if flags:
                untagged[flags] += 1
            continue
        pos, pairs = found
        words = [(pos, pairs)]
        missing = forms - {f for f, _ in pairs}
        if missing and len(flags) > 1:  # гол/AD: the adjective, and the noun голът, голове
            for flag in flags:
                part = expand(word, flag, classes)
                if part & missing:
                    other = label(word, part)
                    if other and other[0] != pos:
                        words.append(other)
                        missing -= {f for f, _ in other[1]}
        for pos, pairs in words:
            index = len(lemmas)
            lemmas.append([word, pos])
            stats[pos] += 1
            for form, tag in pairs:
                readings[form.lower()].add((index, tag))
        stats["forms without a tag"] += len(missing)
        for _ in missing:
            untagged[f"{flags}:{pos}"] += 1

    # Words the dictionary lists form by form, without endings (irregular verbs such as
    # държа, plural-only nouns such as данни). Consecutive entries with a common stem are
    # one word; each form is tagged by analogy with the words labelled above.
    model = suffix_model(readings, lemmas)
    for group in flagless_groups(load_dic(), closed_forms()):
        tagged = tag_by_analogy(group, model)
        if not tagged:
            stats["unlabelled loose forms"] += len(group)
            continue
        pos, base, pairs = tagged
        index = len(lemmas)
        lemmas.append([base, pos])
        stats["loose " + pos] += 1
        stats["loose forms tagged"] += len({f for f, _ in pairs})
        stats["loose forms left"] += len(set(group) - {f for f, _ in pairs})
        for form, tag in pairs:
            readings[form].add((index, tag))

    by_lemma: dict[tuple[str, str], int] = {}
    for line in CLOSED.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        form, lemma, tag = line.split("\t")
        pos = tag.split("|")[0]
        key = (lemma, pos)
        if key not in by_lemma:
            by_lemma[key] = len(lemmas)
            lemmas.append([lemma, pos])
            stats["closed " + pos] += 1
        readings[form].add((by_lemma[key], tag))

    tags = sorted({t for rs in readings.values() for _, t in rs})
    tag_index = {t: i for i, t in enumerate(tags)}
    keys = []
    by_lemma_forms: dict[int, set[str]] = collections.defaultdict(set)
    for form, rs in readings.items():
        for lemma, tag in rs:
            keys.append(f"{form}\x01{lemma:x}\x02{tag_index[tag]:x}")
            by_lemma_forms[lemma].add(form)
    trie = marisa_trie.Trie(keys)
    # Each lemma keeps the stem its forms share, so its forms are one prefix search; a
    # lemma whose forms share less than 2 letters (човек: хора) lists them instead.
    for lemma, entry in enumerate(lemmas):
        found = by_lemma_forms.get(lemma, set())
        stem = os.path.commonprefix(sorted(found)) if found else entry[0]
        entry.append(stem if len(stem) >= 2 else sorted(found))
    OUT.mkdir(parents=True, exist_ok=True)
    trie.save(str(OUT / "bg_morph.marisa"))
    marisa_trie.Trie(
        f"{i:x}{base}{pos}{stem if isinstance(stem, str) else chr(2) + chr(2).join(stem)}"
        for i, (base, pos, stem) in enumerate(lemmas)
    ).save(str(OUT / "bg_morph_lemmas.marisa"))
    (OUT / "bg_morph.json").write_text(
        json.dumps(
            {"source": "tools/morphology/hunspell_morph.py", "tags": tags},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    took = time.perf_counter() - started
    print(
        f"{len(lemmas):,} lemmas, {sum(len(r) for r in readings.values()):,} readings over "
        f"{len(readings):,} forms, {len(tags)} tags in {took:.0f}s"
    )
    print("by kind:", dict(stats.most_common()))
    print("most untagged (flags:pos -> forms):", untagged.most_common(15))
    return stats


if __name__ == "__main__":
    sys.exit(0 if build() else 1)
