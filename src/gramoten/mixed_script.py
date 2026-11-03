"""Latin letters hidden in Cyrillic words, and the reverse.

`пoлучавате` with a Latin o, `Виe`, `aко`, `ВMW` with a Cyrillic В. A reader
cannot see it; search, spelling and some fonts can. The fix maps each lookalike
letter to the majority script of its hyphen part; a part with letters that have
no lookalike, or with as many of one script as the other, gets no fix, only the
finding.
"""

from __future__ import annotations

from .tokenize import CYRILLIC, LATIN

LATIN_TO_CYRILLIC = dict(zip("aeopcxyAEOPCXYBKMHT", "аеорсхуАЕОРСХУВКМНТ", strict=True))
CYRILLIC_TO_LATIN = {cyr: lat for lat, cyr in LATIN_TO_CYRILLIC.items()}
_TO_CYRILLIC = str.maketrans(LATIN_TO_CYRILLIC)


def _fix_part(part: str) -> str | None:
    cyr = len(CYRILLIC.findall(part))
    lat = len(LATIN.findall(part))
    if not (cyr and lat):
        return part
    if cyr == lat:
        return None
    table = LATIN_TO_CYRILLIC if cyr > lat else CYRILLIC_TO_LATIN
    foreign = LATIN if cyr > lat else CYRILLIC
    out = []
    for ch in part:
        if foreign.match(ch):
            if ch not in table:
                return None
            out.append(table[ch])
        else:
            out.append(ch)
    return "".join(out)


def fix(word: str) -> str | None:
    """The word in one script per hyphen part, or None when that is not certain.

    Where the letters do not decide (`oт`, one of each; `пo-къснo`), the
    dictionary does: the all-Cyrillic reading is the fix when it is a word.
    """
    parts = [_fix_part(p) for p in word.split("-")]
    if any(p is None for p in parts):
        from . import spelling

        cyrillic = word.translate(_TO_CYRILLIC)
        if not LATIN.search(cyrillic) and spelling.is_correct(cyrillic):
            return cyrillic
        return None
    fixed = "-".join(parts)  # type: ignore[arg-type]
    return fixed if fixed != word else None
