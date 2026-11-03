"""The words of a text a reader sees, and the ranges no check may touch.

Every check in this package walks the same words, so the underline in the
editor, the badge on open and the line in the export manifest agree.

Protected, never checked or changed: `%%…%%` personalisation and AMPscript,
URLs, e-mail addresses. A token with a digit (`5G`, `S10`, `iPhone16`) is not a
word to spell; it is still read by the mixed-script check, since `ВMW` typed
with a Cyrillic В is exactly the mistake that check exists for.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

PROTECTED = re.compile(
    r"%%\[.*?\]%%"  # AMPscript block
    r"|%%=.*?=%%"  # AMPscript inline
    r"|%%[^%\s]+%%"  # personalisation string
    r"|\b(?:https?://|www\.)\S+"  # URL
    r"|[\w.+-]+@[\w-]+(?:\.[\w-]+)+",  # e-mail address
    re.S,
)

#: Characters that live inside a word without being letters: a soft hyphen and
#: zero-width marks pasted from Word or the web, and combining stress accents
#: (`ѝ` written as и + U+0300). They stay in the word's range, so offsets still
#: address the text as typed, and are dropped before the dictionary is asked.
INVISIBLE = "\u00ad\u200b\u200c\u200d\u2060\ufeff\u0300\u0301"
_STRIP = {ord(ch): None for ch in INVISIBLE}

#: A run of letters and digits, joined by inner hyphens: `е-Тикет`, `SIM-карта`.
_PIECE = rf"[^\W_](?:[^\W_]|[{INVISIBLE}])*"
TOKEN = re.compile(rf"{_PIECE}(?:-{_PIECE})*")

CYRILLIC = re.compile(r"[Ѐ-ӿ]")
LATIN = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class Word:
    text: str
    start: int
    end: int

    @property
    def clean(self) -> str:
        """The word without invisible characters: what the dictionary is asked about."""
        return self.text.translate(_STRIP)

    @property
    def parts(self) -> list[str]:
        return self.clean.split("-")

    @property
    def mixed_script(self) -> bool:
        """A hyphen part with Cyrillic and Latin letters in it (`пoлучавате`, `ВMW`)."""
        return any(CYRILLIC.search(p) and LATIN.search(p) for p in self.parts)

    @property
    def spellable(self) -> bool:
        """Cyrillic letters only: no digit, no Latin, no single letter."""
        word = self.clean
        return (
            len(word) > 1
            and not any(ch.isdigit() for ch in word)
            and not LATIN.search(word)
            and bool(CYRILLIC.search(word))
        )


#: How far back a rule looks for what comes before a word.
BEFORE = 200


def before(text: str, end: int) -> str:
    """What comes before `end`, for a search anchored at `$`: the last `BEFORE`
    characters, so a long text is not read again from its start at every word. A longer text's
    window starts with a letter, so `^` and `^\\W*` still only match at its start."""
    return text[:end] if end <= BEFORE else "x" + text[end - BEFORE : end]


def protected_ranges(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in PROTECTED.finditer(text)]


def tokens(text: str) -> Iterator[Word]:
    """Every letter/digit token outside the protected ranges."""
    ranges = protected_ranges(text)
    cursor = 0
    for start, end in [*ranges, (len(text), len(text))]:
        for m in TOKEN.finditer(text, cursor, start):
            yield Word(m.group(), m.start(), m.end())
        cursor = end


def words(text: str) -> Iterator[Word]:
    """The tokens a spelling check reads: Cyrillic words, and mixed-script ones to report."""
    for token in tokens(text):
        if token.spellable or token.mixed_script:
            yield token
